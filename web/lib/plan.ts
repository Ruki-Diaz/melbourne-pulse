import "server-only";

import { unstable_cache } from "next/cache";

import { sql } from "./db";
import {
  assembleEvidence,
  assemblePlan,
  planSensors,
  rainOutlook,
  type EvidenceResponse,
  type PlanResponse,
  type PlanSensor,
  type PlanWindow,
  type RainOutlook,
  type RainMethod,
  type Snapshot,
} from "./plan-core";

export type {
  DataFreshness,
  EvidenceResponse,
  EvidenceRow,
  PlanResponse,
  PlanSensor,
  RainEffect,
  RainMethod,
} from "./plan-core";

/**
 * Data for the Plan page, read from Neon as the read-only role.
 *
 * Everything comes from one cached snapshot (1 hour, tag "plan"), so a visitor
 * changing the sensor or the window never wakes the database: each response is
 * computed in memory from the snapshot (lib/plan-core.ts). /api/revalidate
 * drops the snapshot after every hourly ingest. Shapes: docs/plan-api.md.
 */

export const PLAN_CACHE_TAG = "plan";

/**
 * Next serves an expired cache entry once more while it refreshes it, however
 * old the entry is. Past this age the database is read directly instead, so a
 * first visitor after a quiet spell never gets yesterday's snapshot.
 */
const MAX_SNAPSHOT_AGE_MS = 90 * 60_000;

const num = (value: unknown) => (value === null || value === undefined ? null : Number(value));
const iso = (value: unknown) => (value ? new Date(value as string).toISOString() : null);

type StoredMethod = Partial<Record<
  "wet_mm" | "heavy_mm" | "min_dry_hours" | "bootstrap_reps" | "min_wet_hours" | "cold_below_c" | "warm_above_c",
  number
>>;

function methodFrom(detail: unknown): RainMethod | null {
  const m = (detail as { method?: StoredMethod } | null)?.method;
  if (!m || [m.wet_mm, m.heavy_mm, m.min_dry_hours, m.bootstrap_reps, m.min_wet_hours, m.cold_below_c, m.warm_above_c]
    .some((v) => typeof v !== "number")) return null;
  return {
    wetMm: m.wet_mm as number,
    heavyMm: m.heavy_mm as number,
    minDryHours: m.min_dry_hours as number,
    bootstrapReps: m.bootstrap_reps as number,
    minWetHours: m.min_wet_hours as number,
    coldBelowC: m.cold_below_c as number,
    warmAboveC: m.warm_above_c as number,
  };
}

/** Throws if the database isn't configured or a query fails, so a failure is never cached. */
async function readSnapshot(): Promise<Snapshot> {
  const query = sql();
  if (!query) throw new Error("DATABASE_URL_READONLY is not set");
  const [forecasts, weather, sensors, rain, latest] = await Promise.all([
    query`select sensor_id, hour, predicted_count, baseline_count
          from forecasts where hour >= now() - interval '1 hour' order by hour`,
    query`select hour, precipitation, precipitation_probability, temperature, wind_speed, weather_code
          from weather_forecast where hour >= now() - interval '1 hour' order by hour`,
    query`select payload from latest where source = 'sensors'`,
    query`select scope, key, effect, ci_low, ci_high, n_wet_hours, reliable, detail,
                 window_start::text as window_start, window_end::text as window_end
          from rain_effect`,
    // Each table's newest write, over the whole table: a row for a past hour counts too.
    query`select (select max(generated_at) from forecasts) as forecasts,
                 (select max(fetched_at) from weather_forecast) as weather,
                 (select max(computed_at) from rain_effect) as rain_effect`,
  ]);
  const profile = rain.find((r) => r.scope === "profile");
  return {
    readAt: new Date().toISOString(),
    forecasts: forecasts.map((r) => ({
      sensorId: Number(r.sensor_id),
      ms: new Date(r.hour).getTime(),
      predicted: Number(r.predicted_count),
      baseline: num(r.baseline_count),
    })),
    weather: weather.map((r) => ({
      ms: new Date(r.hour).getTime(),
      precipMm: num(r.precipitation),
      precipProb: num(r.precipitation_probability),
      tempC: num(r.temperature),
      windKmh: num(r.wind_speed),
      weatherCode: num(r.weather_code),
    })),
    sensors: ((sensors[0]?.payload as Snapshot["sensors"] | undefined) ?? []).map((s) => ({
      location_id: s.location_id,
      name: s.name,
      lat: s.lat,
      lon: s.lon,
    })),
    rain: rain
      .filter((r) => r.scope !== "profile")
      .map((r) => ({
        scope: String(r.scope),
        key: String(r.key),
        effect: num(r.effect),
        ciLow: num(r.ci_low),
        ciHigh: num(r.ci_high),
        nWetHours: Number(r.n_wet_hours),
        reliable: Boolean(r.reliable),
      })),
    rainProfile: Array.isArray(profile?.detail) ? (profile.detail as Snapshot["rainProfile"]) : [],
    rainMethod: methodFrom(rain.find((r) => r.scope === "overall")?.detail),
    rainWindow: rain[0] ? { start: String(rain[0].window_start).slice(0, 10), end: String(rain[0].window_end).slice(0, 10) } : null,
    latestWrite: {
      forecasts: iso(latest[0]?.forecasts),
      weather: iso(latest[0]?.weather),
      rainEffect: iso(latest[0]?.rain_effect),
    },
  };
}

const cachedSnapshot = unstable_cache(readSnapshot, ["plan-snapshot-v2"], { revalidate: 3600, tags: [PLAN_CACHE_TAG] });

async function getSnapshot(): Promise<Snapshot> {
  const cached = await cachedSnapshot();
  if (Date.now() - Date.parse(cached.readAt) <= MAX_SNAPSHOT_AGE_MS) return cached;
  try {
    return await readSnapshot();
  } catch (error) {
    console.error("plan snapshot is stale and the database could not be read:", error);
    return cached;
  }
}

/** Sensors that currently have a forecast, by name: the options for the sensor picker. */
export async function getPlanSensors(): Promise<PlanSensor[]> {
  return planSensors(await getSnapshot());
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
  return assemblePlan(await getSnapshot(), sensor, window, nowMs);
}

/** Everything behind the rain-effect claim: forest-plot rows, the hourly profile and every sensor. */
export async function getPlanEvidence(nowMs: number = Date.now()): Promise<EvidenceResponse> {
  return assembleEvidence(await getSnapshot(), nowMs);
}

/** A weather forecast older than this is not quoted on the landing page. */
const WEATHER_MAX_AGE_MS = 3 * 3_600_000;

/**
 * Rain in the next `hours`, for the landing page's link to /plan. null when
 * none is forecast, the stored forecast is too old to quote, or the database
 * can't be read: the page then shows its plain link instead of a guess.
 */
export async function getRainOutlook(hours: number, nowMs: number = Date.now()): Promise<RainOutlook | null> {
  try {
    const snapshot = await getSnapshot();
    const fetchedAt = snapshot.latestWrite.weather;
    if (!fetchedAt || nowMs - Date.parse(fetchedAt) > WEATHER_MAX_AGE_MS) return null;
    return rainOutlook(snapshot.weather, nowMs, hours);
  } catch (error) {
    console.error("rain outlook unavailable:", error);
    return null;
  }
}
