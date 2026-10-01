import type { ForecastRow, HourlyHistoryRow } from "./db";

export const HOUR_MS = 3_600_000;

/** Start of the hour. Melbourne's offset is a whole number of hours, so UTC flooring is exact. */
export function floorHour(ms: number): number {
  return Math.floor(ms / HOUR_MS) * HOUR_MS;
}

export function dayHourLabel(ms: number): string {
  const d = new Date(ms);
  const day = d.toLocaleDateString("en-AU", { weekday: "short", timeZone: "Australia/Melbourne" });
  const hour = d
    .toLocaleTimeString("en-AU", { hour: "numeric", hour12: true, timeZone: "Australia/Melbourne" })
    .replace(/\s/g, "")
    .toLowerCase();
  return `${day} ${hour}`;
}

export type SeriesPoint = {
  hourIso: string;
  hourLabel: string;
  /** Measured count; null for hours not yet complete or not measured. */
  actual: number | null;
  /** What the model predicted for that hour (also kept for past hours). */
  forecast: number | null;
  /** The 8-week typical for that exact hour, stored with each forecast row. */
  typical: number | null;
};

/**
 * Hour-by-hour series per sensor from `fromMs` up to (not including) `toMs`,
 * keyed by real timestamps, so "3pm today" and "3pm tomorrow" never merge.
 * Hours with no actual, forecast or typical are left out; nothing is invented.
 */
export function buildSeriesBySensor(
  history: HourlyHistoryRow[],
  forecasts: ForecastRow[],
  fromMs: number,
  toMs: number
): Record<number, SeriesPoint[]> {
  const actual = new Map<string, number>();
  for (const h of history) {
    if (!h.is_partial) actual.set(`${h.location_id}|${Date.parse(h.hour)}`, h.count);
  }
  const forecast = new Map<string, ForecastRow>();
  for (const f of forecasts) forecast.set(`${f.sensor_id}|${Date.parse(f.hour)}`, f);

  const sensors = new Set<number>([...history.map((h) => h.location_id), ...forecasts.map((f) => f.sensor_id)]);
  const out: Record<number, SeriesPoint[]> = {};
  for (const id of sensors) {
    const points: SeriesPoint[] = [];
    for (let t = floorHour(fromMs); t < toMs; t += HOUR_MS) {
      const key = `${id}|${t}`;
      const f = forecast.get(key);
      const point: SeriesPoint = {
        hourIso: new Date(t).toISOString(),
        hourLabel: dayHourLabel(t),
        actual: actual.get(key) ?? null,
        forecast: f ? Math.round(f.predicted_count) : null,
        typical: f?.baseline_count != null ? Math.round(f.baseline_count) : null,
      };
      if (point.actual !== null || point.forecast !== null || point.typical !== null) points.push(point);
    }
    out[id] = points;
  }
  return out;
}
