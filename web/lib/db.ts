import "server-only";

import { neon } from "@neondatabase/serverless";

import type { FeedAnomaly } from "./feed-anomaly";

/**
 * Read-only Neon connection over HTTP, for server components only.
 * `server-only` makes the build fail if this is ever imported into client code,
 * so DATABASE_URL_READONLY can't leak to the browser.
 *
 * Two rules keep the site inside Neon's free 5 GB/month of transfer and keep it
 * honest when the database is down:
 * - Read only what the page shows. Every byte returned here counts against the
 *   allowance, and pages are re-rendered every hour (docs/MAINTENANCE.md).
 * - A failed query throws. Next.js then keeps serving the last good page (with
 *   its "Last updated X h ago" badge) instead of caching an empty one. Only a
 *   database that isn't configured at all (local builds, CI) returns null or [].
 */
export function sql() {
  const url = process.env.DATABASE_URL_READONLY;
  return url ? neon(url, { readOnly: true }) : null;
}

export type Latest<T> = { updatedAt: Date; payload: T };

export type Summary = {
  text: string;
  source: "gemini" | "template";
  hour: string | null;
  /** Field names exactly as pipeline/summary.py writes them. */
  stats?: {
    hour?: string;
    day?: string;
    hour_label?: string;
    pedestrians?: number;
    sensors?: number;
    vs_typical_pct?: number | null;
    busiest?: Array<{ name: string; count: number }>;
    pct_bays_free?: number;
    bays_reporting?: number;
  };
};

export type PedestrianSensorLatest = {
  location_id: number;
  count: number;
  /** null until the sensor has an 8-week baseline. */
  typical: number | null;
  /**
   * Has this sensor finished reporting the hour? false = still uploading, so its
   * count is a part-hour and is left out of totals. Missing on older rows (= true).
   */
  settled?: boolean;
};

export type PedestrianLatestPayload = {
  hour: string;
  sensors: PedestrianSensorLatest[];
  /** Sensors that have finished reporting the hour, out of those seen in the last 24 h. */
  coverage?: { reporting: number; active: number };
};

/** The sensors whose count for the hour is complete: the only ones totals and comparisons may use. */
export function settledSensors(payload: PedestrianLatestPayload | undefined | null): PedestrianSensorLatest[] {
  return (payload?.sensors ?? []).filter((s) => s.settled !== false);
}

export type ParkingBayLatest = {
  kerbsideid: number;
  lat: number;
  lon: number;
  free: boolean;
  stale: boolean;
};

export type SensorMeta = {
  location_id: number;
  name: string;
  lat: number;
  lon: number;
  indoor: boolean;
};

export type ForecastRow = {
  sensor_id: number;
  hour: string;
  predicted_count: number;
  baseline_count: number | null;
};

export type HourlyHistoryRow = {
  location_id: number;
  hour: string;
  count: number;
  is_partial: boolean;
};

/**
 * The feed-quality flag for one hour: set if the pipeline flagged it (most
 * sensors under half their typical at once, cause unknown), else null.
 */
export async function getFeedAnomaly(hourIso: string | null | undefined): Promise<FeedAnomaly | null> {
  const query = sql();
  if (!query || !hourIso) return null;
  const rows = await query`
    select sensors_judged, sensors_low, share_low from feed_quality
    where hour = ${hourIso} and anomaly`;
  const row = rows[0];
  return row
    ? { sensorsJudged: Number(row.sensors_judged), sensorsLow: Number(row.sensors_low), shareLow: row.share_low === null ? null : Number(row.share_low) }
    : null;
}

/** One `latest` row, or null if the database isn't configured or has no row yet. */
export async function getLatest<T>(source: "parking" | "pedestrian" | "sensors" | "summary") {
  const query = sql();
  if (!query) return null;
  const rows = await query`select updated_at, payload from latest where source = ${source}`;
  const row = rows[0];
  return row ? ({ updatedAt: new Date(row.updated_at), payload: row.payload as T } satisfies Latest<T>) : null;
}

/** Fetch all latest tables in parallel. Includes all 6,324 parking bays (~0.6 MB): only /map needs them. */
export async function getAllLatest() {
  const [pedestrian, parking, sensors, summary] = await Promise.all([
    getLatest<PedestrianLatestPayload>("pedestrian"),
    getLatest<ParkingBayLatest[]>("parking"),
    getLatest<SensorMeta[]>("sensors"),
    getLatest<Summary>("summary"),
  ]);

  return {
    pedestrian,
    parking,
    sensors,
    summary,
  };
}

/** Bays reporting (not stale) and free among them, counted in the database from the same `latest` row /map draws. */
export type ParkingShare = { updatedAt: Date; reporting: number; free: number };

/** Percent of reporting bays that are free, rounded, or null if none are reporting. */
export function pctFree(share: ParkingShare | null): number | null {
  return share && share.reporting > 0 ? Math.round((share.free / share.reporting) * 100) : null;
}

/**
 * Everything except the parking bay list: pedestrian, sensors and summary, plus
 * the parking share counted in SQL. The same numbers as getAllLatest() at a
 * hundredth of the transfer.
 */
export async function getLatestSummaryData() {
  const query = sql();
  const [pedestrian, sensors, summary, parkingRows] = await Promise.all([
    getLatest<PedestrianLatestPayload>("pedestrian"),
    getLatest<SensorMeta[]>("sensors"),
    getLatest<Summary>("summary"),
    query
      ? query`
          select l.updated_at,
                 count(*) filter (where not coalesce((b->>'stale')::boolean, false)) as reporting,
                 count(*) filter (where not coalesce((b->>'stale')::boolean, false)
                                    and coalesce((b->>'free')::boolean, false)) as free
          from latest l cross join lateral jsonb_array_elements(l.payload) b
          where l.source = 'parking'
          group by l.updated_at`
      : Promise.resolve([]),
  ]);
  const row = parkingRows[0];
  const parking: ParkingShare | null = row
    ? { updatedAt: new Date(row.updated_at), reporting: Number(row.reporting), free: Number(row.free) }
    : null;
  return { pedestrian, sensors, summary, parking };
}

/**
 * Stored forecasts from `hoursBack` hours before the current hour onwards (the
 * table holds about 2 days back and 24 h ahead). Pass the furthest back the page
 * charts, plus one hour of slack for clock differences.
 */
export async function getForecasts(hoursBack: number): Promise<ForecastRow[]> {
  const query = sql();
  if (!query) return [];
  const rows = await query`
    select sensor_id, hour, predicted_count, baseline_count
    from forecasts
    where hour >= date_trunc('hour', now()) - make_interval(hours => ${hoursBack})
    order by hour asc
  `;
  return rows.map((r) => ({
    sensor_id: Number(r.sensor_id),
    hour: new Date(r.hour).toISOString(),
    predicted_count: Number(r.predicted_count),
    baseline_count: r.baseline_count !== null ? Number(r.baseline_count) : null,
  }));
}

/** Fetch recent 24-hour pedestrian history per sensor */
export async function getRecentPedestrianHistory(hours: number = 24): Promise<HourlyHistoryRow[]> {
  const query = sql();
  if (!query) return [];
  const rows = await query`
    select location_id, hour, count, is_partial
    from pedestrian_hourly
    where hour >= now() - (${hours} || ' hours')::interval
    order by hour asc
  `;
  return rows.map((r) => ({
    location_id: Number(r.location_id),
    hour: new Date(r.hour).toISOString(),
    count: Number(r.count),
    is_partial: Boolean(r.is_partial),
  }));
}
