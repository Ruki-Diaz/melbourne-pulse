import "server-only";

import { unstable_cache } from "next/cache";

import { sql, type SensorMeta } from "./db";
import {
  buildHours,
  recommend,
  windowRange,
  type ForecastPoint,
  type PlanHour,
  type PlanWindow,
  type Recommendations,
  type WeatherPoint,
} from "./plan-core";

/**
 * Data for the Plan page, read from Neon as the read-only role.
 *
 * Everything comes from one cached snapshot (1 hour, tag "plan"), so a visitor
 * changing the sensor or the window never wakes the database: each response is
 * computed in memory from the snapshot. /api/revalidate drops the snapshot
 * after every hourly ingest. Shapes are documented in docs/plan-api.md.
 */

export const PLAN_CACHE_TAG = "plan";

export type PlanSensor = { id: number; name: string; lat: number; lon: number };

export type RainEffect = {
  /** Change in pedestrian counts in a wet hour, in percent (-18.5 = 18.5% fewer). */
  value: number;
  ciLow: number | null;
  ciHigh: number | null;
  nWetHours: number;
  reliable: boolean;
  /** true when the sensor's own estimate wasn't reliable and the CBD-wide one is shown instead. */
  usedFallback: boolean;
  scope: "sensor" | "cbd";
};

export type DataFreshness = {
  forecastGeneratedAt: string | null;
  weatherFetchedAt: string | null;
  rainEffectComputedAt: string | null;
};

export type PlanResponse = {
  generatedAt: string;
  dataFreshness: DataFreshness;
  sensor: PlanSensor | "cbd";
  /** The hours asked for. `complete` is false when the forecast doesn't reach the end of the window yet. */
  window: { key: PlanWindow; start: string; end: string; complete: boolean };
  hours: PlanHour[];
  rainEffect: RainEffect | null;
  recommendations: Recommendations;
};

export type EvidenceRow = {
  group: "overall" | "intensity" | "daytype" | "temperature";
  key: string;
  label: string;
  value: number;
  ciLow: number | null;
  ciHigh: number | null;
  nWetHours: number;
  reliable: boolean;
};

export type EvidenceResponse = {
  generatedAt: string;
  /** The 12 months the effects were measured over (local dates, inclusive). */
  window: { start: string; end: string } | null;
  computedAt: string | null;
  /** Overall first, then each breakdown: the rows of the forest plot. */
  forest: EvidenceRow[];
  /** Average CBD-wide count per wet hour of the day, next to matched dry hours. */
  profile: Array<{ hour: number; wet: number; dry: number; nWetHours: number }>;
  sensors: Array<{
    id: number;
    name: string;
    lat: number | null;
    lon: number | null;
    value: number;
    ciLow: number | null;
    ciHigh: number | null;
    nWetHours: number;
    reliable: boolean;
  }>;
};

type RainRow = {
  scope: string;
  key: string;
  effect: number | null;
  ciLow: number | null;
  ciHigh: number | null;
  nWetHours: number;
  reliable: boolean;
  detail: Array<{ hour: number; wet: number; dry: number; n_wet_hours: number }> | null;
};

type Snapshot = {
  forecasts: ForecastPoint[];
  forecastGeneratedAt: string | null;
  weather: WeatherPoint[];
  weatherFetchedAt: string | null;
  sensors: SensorMeta[];
  rain: RainRow[];
  rainWindow: { start: string; end: string } | null;
  rainComputedAt: string | null;
};

const num = (value: unknown) => (value === null || value === undefined ? null : Number(value));
const iso = (value: unknown) => (value ? new Date(value as string).toISOString() : null);
const day = (value: unknown) => (value instanceof Date ? value.toISOString().slice(0, 10) : String(value).slice(0, 10));
const pct = (fraction: number | null) => (fraction === null ? null : Math.round(fraction * 1000) / 10);

/** Throws if the database isn't configured or a query fails, so a failure is never cached. */
async function readSnapshot(): Promise<Snapshot> {
  const query = sql();
  if (!query) throw new Error("DATABASE_URL_READONLY is not set");
  const [forecasts, weather, sensors, rain] = await Promise.all([
    query`select sensor_id, hour, predicted_count, baseline_count, generated_at
          from forecasts where hour >= now() - interval '1 hour' order by hour`,
    query`select hour, precipitation, precipitation_probability, temperature, wind_speed, weather_code, fetched_at
          from weather_forecast where hour >= now() - interval '1 hour' order by hour`,
    query`select payload from latest where source = 'sensors'`,
    query`select scope, key, effect, ci_low, ci_high, n_wet_hours, reliable, detail,
                 window_start::text as window_start, window_end::text as window_end, computed_at
          from rain_effect`,
  ]);
  const newest = (rows: Record<string, unknown>[], field: string) =>
    rows.reduce<string | null>((max, r) => {
      const at = iso(r[field]);
      return at && (!max || at > max) ? at : max;
    }, null);
  return {
    forecasts: forecasts.map((r) => ({
      sensorId: Number(r.sensor_id),
      ms: new Date(r.hour).getTime(),
      predicted: Number(r.predicted_count),
      baseline: num(r.baseline_count),
    })),
    forecastGeneratedAt: newest(forecasts, "generated_at"),
    weather: weather.map((r) => ({
      ms: new Date(r.hour).getTime(),
      precipMm: num(r.precipitation),
      precipProb: num(r.precipitation_probability),
      tempC: num(r.temperature),
      windKmh: num(r.wind_speed),
      weatherCode: num(r.weather_code),
    })),
    weatherFetchedAt: newest(weather, "fetched_at"),
    sensors: (sensors[0]?.payload as SensorMeta[] | undefined) ?? [],
    rain: rain.map((r) => ({
      scope: String(r.scope),
      key: String(r.key),
      effect: num(r.effect),
      ciLow: num(r.ci_low),
      ciHigh: num(r.ci_high),
      nWetHours: Number(r.n_wet_hours),
      reliable: Boolean(r.reliable),
      detail: (r.detail as RainRow["detail"]) ?? null,
    })),
    rainWindow: rain[0] ? { start: day(rain[0].window_start), end: day(rain[0].window_end) } : null,
    rainComputedAt: newest(rain, "computed_at"),
  };
}

const getSnapshot = unstable_cache(readSnapshot, ["plan-snapshot-v1"], { revalidate: 3600, tags: [PLAN_CACHE_TAG] });

function sensorsWithForecasts(snapshot: Snapshot): PlanSensor[] {
  const active = new Set(snapshot.forecasts.map((f) => f.sensorId));
  return snapshot.sensors
    .filter((s) => active.has(s.location_id))
    .map((s) => ({ id: s.location_id, name: s.name, lat: s.lat, lon: s.lon }))
    .sort((a, b) => a.name.localeCompare(b.name));
}

/** Sensors that currently have a forecast, by name: the options for the sensor picker. */
export async function getPlanSensors(): Promise<PlanSensor[]> {
  return sensorsWithForecasts(await getSnapshot());
}

function rainEffectFor(snapshot: Snapshot, sensor: number | "cbd"): RainEffect | null {
  const shape = (row: RainRow, scope: "sensor" | "cbd", usedFallback: boolean): RainEffect => ({
    value: pct(row.effect) as number,
    ciLow: pct(row.ciLow),
    ciHigh: pct(row.ciHigh),
    nWetHours: row.nWetHours,
    reliable: row.reliable,
    usedFallback,
    scope,
  });
  const overall = snapshot.rain.find((r) => r.scope === "overall" && r.effect !== null);
  if (sensor !== "cbd") {
    const own = snapshot.rain.find((r) => r.scope === "sensor" && r.key === String(sensor) && r.effect !== null);
    if (own?.reliable) return shape(own, "sensor", false);
    // Not enough evidence at this sensor: show the CBD-wide effect instead.
    if (overall) return shape(overall, "cbd", true);
    return own ? shape(own, "sensor", false) : null;
  }
  return overall ? shape(overall, "cbd", false) : null;
}

/**
 * The plan for one sensor (or the whole CBD) over a window.
 * Returns null for a sensor id that has no forecast. Throws if the database can't be read.
 */
export async function getPlan(
  sensor: number | "cbd",
  window: PlanWindow,
  nowMs: number = Date.now()
): Promise<PlanResponse | null> {
  const snapshot = await getSnapshot();
  const meta = sensor === "cbd" ? "cbd" : sensorsWithForecasts(snapshot).find((s) => s.id === sensor);
  if (!meta) return null;

  const range = windowRange(nowMs, window);
  const hours = buildHours(snapshot.forecasts, snapshot.weather, sensor, range);
  const wanted = Math.round((range.endMs - range.startMs) / 3_600_000);
  return {
    generatedAt: new Date(nowMs).toISOString(),
    dataFreshness: {
      forecastGeneratedAt: snapshot.forecastGeneratedAt,
      weatherFetchedAt: snapshot.weatherFetchedAt,
      rainEffectComputedAt: snapshot.rainComputedAt,
    },
    sensor: meta,
    window: {
      key: window,
      start: new Date(range.startMs).toISOString(),
      end: new Date(range.endMs).toISOString(),
      complete: hours.length === wanted,
    },
    hours,
    rainEffect: rainEffectFor(snapshot, sensor),
    recommendations: recommend(hours),
  };
}

const FOREST: Array<{ group: EvidenceRow["group"]; key: string; label: string }> = [
  { group: "overall", key: "all", label: "All wet hours" },
  { group: "intensity", key: "light", label: "Light rain (0.2 to 2 mm an hour)" },
  { group: "intensity", key: "heavy", label: "Heavy rain (2 mm an hour or more)" },
  { group: "daytype", key: "weekday", label: "Weekdays" },
  { group: "daytype", key: "weekend", label: "Weekends and public holidays" },
  { group: "temperature", key: "cold", label: "Cold (below 12 °C)" },
  { group: "temperature", key: "mild", label: "Mild (12 to 20 °C)" },
  { group: "temperature", key: "warm", label: "Warm (above 20 °C)" },
];

/** Everything behind the rain-effect claim: forest-plot rows, the hourly profile and every sensor. */
export async function getPlanEvidence(nowMs: number = Date.now()): Promise<EvidenceResponse> {
  const snapshot = await getSnapshot();
  const find = (scope: string, key: string) => snapshot.rain.find((r) => r.scope === scope && r.key === key);
  const meta = new Map(snapshot.sensors.map((s) => [s.location_id, s]));
  return {
    generatedAt: new Date(nowMs).toISOString(),
    window: snapshot.rainWindow,
    computedAt: snapshot.rainComputedAt,
    forest: FOREST.flatMap(({ group, key, label }) => {
      const row = find(group, key);
      return row && row.effect !== null
        ? [{ group, key, label, value: pct(row.effect) as number, ciLow: pct(row.ciLow), ciHigh: pct(row.ciHigh),
             nWetHours: row.nWetHours, reliable: row.reliable }]
        : [];
    }),
    profile: (find("profile", "cbd")?.detail ?? []).map((p) => ({
      hour: p.hour,
      wet: Math.round(p.wet),
      dry: Math.round(p.dry),
      nWetHours: p.n_wet_hours,
    })),
    sensors: snapshot.rain
      .filter((r) => r.scope === "sensor" && r.effect !== null)
      .map((r) => {
        const id = Number(r.key);
        const s = meta.get(id);
        return {
          id,
          name: s?.name ?? `Sensor ${id}`,
          lat: s?.lat ?? null,
          lon: s?.lon ?? null,
          value: pct(r.effect) as number,
          ciLow: pct(r.ciLow),
          ciHigh: pct(r.ciHigh),
          nWetHours: r.nWetHours,
          reliable: r.reliable,
        };
      })
      .sort((a, b) => a.value - b.value),
  };
}
