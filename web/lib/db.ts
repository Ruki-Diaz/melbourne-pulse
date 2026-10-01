import "server-only";

import { neon } from "@neondatabase/serverless";

/**
 * Read-only Neon connection over HTTP, for server components only.
 * `server-only` makes the build fail if this is ever imported into client code,
 * so DATABASE_URL_READONLY can't leak to the browser.
 */
function sql() {
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
};

export type PedestrianLatestPayload = {
  hour: string;
  sensors: PedestrianSensorLatest[];
};

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
