import "server-only";

import { neon } from "@neondatabase/serverless";

import type { FeedAnomaly } from "./feed-anomaly";

/**
 * Read-only Neon connection over HTTP, for server components only.
 * `server-only` makes the build fail if this is ever imported into client code,
 * so DATABASE_URL_READONLY can't leak to the browser.
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
  try {
    const rows = await query`
      select sensors_judged, sensors_low, share_low from feed_quality
      where hour = ${hourIso} and anomaly`;
    const row = rows[0];
    return row
      ? { sensorsJudged: Number(row.sensors_judged), sensorsLow: Number(row.sensors_low), shareLow: row.share_low === null ? null : Number(row.share_low) }
      : null;
  } catch (error) {
    console.error("Error fetching feed quality:", error);
    return null;
  }
}

/** One `latest` row, or null if the database isn't configured or has no row yet. */
export async function getLatest<T>(source: "parking" | "pedestrian" | "sensors" | "summary") {
  const query = sql();
  if (!query) return null;
  try {
    const rows = await query`select updated_at, payload from latest where source = ${source}`;
    const row = rows[0];
    return row ? ({ updatedAt: new Date(row.updated_at), payload: row.payload as T } satisfies Latest<T>) : null;
  } catch (error) {
    console.error(`Error fetching latest.${source}:`, error);
    return null;
  }
}

/** Fetch all latest tables in parallel */
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

/** Fetch next-24-hour forecasts */
export async function getForecasts(): Promise<ForecastRow[]> {
  const query = sql();
  if (!query) return [];
  try {
    const rows = await query`
      select sensor_id, hour, predicted_count, baseline_count
      from forecasts
      order by hour asc
    `;
    return rows.map((r) => ({
      sensor_id: Number(r.sensor_id),
      hour: new Date(r.hour).toISOString(),
      predicted_count: Number(r.predicted_count),
      baseline_count: r.baseline_count !== null ? Number(r.baseline_count) : null,
    }));
  } catch (error) {
    console.error("Error fetching forecasts:", error);
    return [];
  }
}

/** Fetch recent 24-hour pedestrian history per sensor */
export async function getRecentPedestrianHistory(hours: number = 24): Promise<HourlyHistoryRow[]> {
  const query = sql();
  if (!query) return [];
  try {
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
  } catch (error) {
    console.error("Error fetching pedestrian history:", error);
    return [];
  }
}
