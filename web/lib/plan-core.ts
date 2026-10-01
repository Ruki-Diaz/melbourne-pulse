/**
 * Pure logic for the Plan API: time windows, hour rows, recommendations and
 * turning one database snapshot into the API responses.
 * No imports and no I/O, so it runs anywhere, including the pytest check in
 * pipeline/tests/test_plan_recommendations.py (via scripts/plan-recommend.mjs).
 *
 * The forecast already includes the weather forecast. Nothing here scales a
 * count by rain; rain is only used to rank and to explain.
 */

export const HOUR_MS = 3_600_000;
/** A recommendation is a block of this many consecutive hours. */
export const BLOCK_HOURS = 2;
/** Blocks are picked from 7am-10pm local when the window has any; otherwise from every hour. */
export const ACTIVE_FROM_HOUR = 7;
export const ACTIVE_TO_HOUR = 22;
/** An hour counts as a rain risk from either of these. */
export const WET_PROB_PCT = 50;
export const WET_MM = 0.2;

export const PLAN_WINDOWS = ["12h", "today", "tomorrow", "36h"] as const;
export type PlanWindow = (typeof PLAN_WINDOWS)[number];

export type ForecastPoint = { sensorId: number; ms: number; predicted: number; baseline: number | null };

export type WeatherPoint = {
  ms: number;
  precipMm: number | null;
  precipProb: number | null;
  tempC: number | null;
  windKmh: number | null;
  weatherCode: number | null;
};

export type PlanHour = {
  /** Start of the hour in Melbourne time, with its UTC offset: "2026-10-02T14:00:00+10:00". */
  hourLocal: string;
  forecastCount: number;
  typicalCount: number | null;
  /** Forecast against typical, in percent; null without a typical. */
  deltaPct: number | null;
  precipMm: number | null;
  precipProb: number | null;
  tempC: number | null;
  windKmh: number | null;
  weatherCode: number | null;
};

export type Recommendation = {
  start: string;
  /** Exclusive: the block covers [start, end). */
  end: string;
  deltaPct: number | null;
  maxPrecipProb: number | null;
  reason: string;
};

export type RecommendationSet = {
  best: Recommendation | null;
  secondBest: Recommendation | null;
  avoid: Recommendation | null;
};

export type Recommendations = {
  mostTraffic: RecommendationSet;
  busyButDry: RecommendationSet;
  quietest: RecommendationSet;
  /**
   * The hours the blocks were chosen from: start of the first candidate block
   * to the end of the last. `daytimeOnly` is true when only 7am-10pm blocks
   * were offered. null when the window has no forecast hours.
   */
  hoursConsidered: { from: string; to: string; daytimeOnly: boolean } | null;
};

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
  /** Newest write to each table, whatever hours the rows are for. */
  forecastGeneratedAt: string | null;
  weatherFetchedAt: string | null;
  rainEffectComputedAt: string | null;
  /** When the website last read the database. Every number in a response comes from this one read. */
  snapshotAt: string;
};

export type PlanResponse = {
  generatedAt: string;
  dataFreshness: DataFreshness;
  sensor: PlanSensor | "cbd";
  /** Sensors behind every forecastCount and typicalCount in `hours`: the same ones in each hour. */
  sensorsUsed: number;
  /** The hours asked for. `complete` is false when the forecast doesn't reach the end of the window yet. */
  window: { key: PlanWindow; start: string; end: string; complete: boolean };
  hours: PlanHour[];
  rainEffect: RainEffect | null;
  recommendations: Recommendations;
};

/** How the rain effect was measured, as stored with it by pipeline/rain_effect.py. */
export type RainMethod = {
  wetMm: number;
  heavyMm: number;
  minDryHours: number;
  bootstrapReps: number;
  minWetHours: number;
  coldBelowC: number;
  warmAboveC: number;
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
  method: RainMethod | null;
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

export type RainRow = {
  scope: string;
  key: string;
  effect: number | null;
  ciLow: number | null;
  ciHigh: number | null;
  nWetHours: number;
  reliable: boolean;
};

/** One read of the database: everything a response is computed from. */
export type Snapshot = {
  readAt: string;
  forecasts: ForecastPoint[];
  weather: WeatherPoint[];
  sensors: Array<{ location_id: number; name: string; lat: number; lon: number }>;
  rain: RainRow[];
  rainProfile: Array<{ hour: number; wet: number; dry: number; n_wet_hours: number }>;
  rainMethod: RainMethod | null;
  rainWindow: { start: string; end: string } | null;
  /** max() over each whole table, not just the rows in this snapshot. */
  latestWrite: { forecasts: string | null; weather: string | null; rainEffect: string | null };
};

const MELBOURNE = new Intl.DateTimeFormat("en-CA", {
  timeZone: "Australia/Melbourne",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

function localParts(ms: number) {
  const parts: Record<string, string> = {};
  for (const p of MELBOURNE.formatToParts(new Date(ms))) parts[p.type] = p.value;
  return { date: `${parts.year}-${parts.month}-${parts.day}`, hour: Number(parts.hour), minute: parts.minute };
}

/** Melbourne wall-clock time with its real offset (+10:00 or +11:00), DST-safe. */
export function localIso(ms: number): string {
  const { date, hour, minute } = localParts(ms);
  const wall = Date.parse(`${date}T${String(hour).padStart(2, "0")}:${minute}:00Z`);
  const offsetMin = Math.round((wall - Math.floor(ms / 60_000) * 60_000) / 60_000);
  const hh = String(Math.floor(Math.abs(offsetMin) / 60)).padStart(2, "0");
  const mm = String(Math.abs(offsetMin) % 60).padStart(2, "0");
  return `${date}T${String(hour).padStart(2, "0")}:${minute}:00${offsetMin < 0 ? "-" : "+"}${hh}:${mm}`;
}

function floorHour(ms: number): number {
  return Math.floor(ms / HOUR_MS) * HOUR_MS;
}

/** The first hour start after `hourMs` that begins a new Melbourne day. */
function nextLocalMidnight(hourMs: number): number {
  const day = localParts(hourMs).date;
  let t = hourMs + HOUR_MS;
  while (localParts(t).date === day) t += HOUR_MS; // at most 25 steps
  return t;
}

/**
 * [startMs, endMs) for a window, stepping in real hours.
 *   12h / 36h  from the next full hour
 *   today      from the next full hour to local midnight (empty after 11pm)
 *   tomorrow   local midnight to local midnight (23 or 25 hours on a DST change)
 */
export function windowRange(nowMs: number, window: PlanWindow): { startMs: number; endMs: number } {
  const first = floorHour(nowMs) + HOUR_MS;
  if (window === "12h") return { startMs: first, endMs: first + 12 * HOUR_MS };
  if (window === "36h") return { startMs: first, endMs: first + 36 * HOUR_MS };
  const midnight = nextLocalMidnight(floorHour(nowMs));
  if (window === "today") return { startMs: first, endMs: midnight };
  return { startMs: midnight, endMs: nextLocalMidnight(midnight) };
}

function round1(value: number): number {
  return Math.round(value * 10) / 10;
}

/**
 * One row per hour in the range, plus how many sensors are behind the counts.
 *
 * For "cbd", forecastCount and typicalCount are sums over the SAME sensors in
 * every hour: the sensors that have both a forecast and a typical in all of
 * the hours returned. So the two columns are always comparable, hour to hour
 * and with each other, and one sensor missing a value can't move the total.
 * (If no sensor has a typical at all, the forecast alone is summed and
 * typicalCount is null.) Hours covered by fewer than half the sensors, such as
 * leftovers from an old forecast run, are left out rather than shrinking the set.
 */
export function buildHours(
  forecasts: ForecastPoint[],
  weather: WeatherPoint[],
  sensor: number | "cbd",
  range: { startMs: number; endMs: number }
): { hours: PlanHour[]; sensorsUsed: number } {
  const inRange = forecasts.filter(
    (f) => f.ms >= range.startMs && f.ms < range.endMs && (sensor === "cbd" || f.sensorId === sensor)
  );
  const paired = inRange.some((f) => f.baseline !== null);
  const usable = paired && sensor === "cbd" ? inRange.filter((f) => f.baseline !== null) : inRange;

  const byHour = new Map<number, Map<number, ForecastPoint>>();
  for (const f of usable) {
    if (!byHour.has(f.ms)) byHour.set(f.ms, new Map());
    (byHour.get(f.ms) as Map<number, ForecastPoint>).set(f.sensorId, f);
  }
  const fullest = Math.max(0, ...[...byHour.values()].map((rows) => rows.size));
  const kept = [...byHour.entries()].filter(([, rows]) => rows.size * 2 >= fullest).sort(([a], [b]) => a - b);
  // Sensors present in every kept hour.
  const sensors = kept.reduce<number[] | null>(
    (used, [, rows]) => (used === null ? [...rows.keys()] : used.filter((id) => rows.has(id))),
    null
  ) ?? [];

  const weatherAt = new Map(weather.map((w) => [w.ms, w]));
  const hours = sensors.length === 0 ? [] : kept.map(([ms, rows]) => {
    const points = sensors.map((id) => rows.get(id) as ForecastPoint);
    const predicted = points.reduce((sum, p) => sum + p.predicted, 0);
    const typical = points.every((p) => p.baseline !== null)
      ? points.reduce((sum, p) => sum + (p.baseline as number), 0)
      : null;
    const w = weatherAt.get(ms);
    return {
      hourLocal: localIso(ms),
      forecastCount: Math.round(predicted),
      typicalCount: typical === null ? null : Math.round(typical),
      deltaPct: typical !== null && typical > 0 ? round1((predicted / typical - 1) * 100) : null,
      precipMm: w?.precipMm ?? null,
      precipProb: w?.precipProb ?? null,
      tempC: w?.tempC ?? null,
      windKmh: w?.windKmh ?? null,
      weatherCode: w?.weatherCode ?? null,
    };
  });
  return { hours, sensorsUsed: hours.length ? sensors.length : 0 };
}

export function isRainRisk(hour: PlanHour): boolean {
  return (hour.precipProb ?? 0) >= WET_PROB_PCT || (hour.precipMm ?? 0) >= WET_MM;
}

/** Rain wording by the highest chance of rain: under 30%, 30-49%, 50% and over. */
export const RAIN_SOME_PCT = 30;
export const RAIN_LIKELY_PCT = WET_PROB_PCT;
export type RainTier = "low" | "some" | "likely";

export function rainTier(maxPrecipProb: number): RainTier {
  const pct = Math.round(maxPrecipProb);
  return pct >= RAIN_LIKELY_PCT ? "likely" : pct >= RAIN_SOME_PCT ? "some" : "low";
}

const RAIN_PHRASE: Record<RainTier, string> = { low: "low rain risk", some: "some rain risk", likely: "rain likely" };

/** "low rain risk (12%)" / "some rain risk (41%)" / "rain likely (76%)"; null without a rain forecast. */
export function rainPhrase(maxPrecipProb: number | null): string | null {
  return maxPrecipProb === null ? null : `${RAIN_PHRASE[rainTier(maxPrecipProb)]} (${Math.round(maxPrecipProb)}%)`;
}

type Block = {
  startMs: number;
  endMs: number;
  meanForecast: number;
  deltaPct: number | null;
  maxPrecipProb: number | null;
  rainRiskHours: number;
  hasWeather: boolean;
  active: boolean;
};

function blocksOf(hours: PlanHour[]): Block[] {
  const out: Block[] = [];
  const size = Math.min(BLOCK_HOURS, hours.length);
  for (let i = 0; size > 0 && i + size <= hours.length; i++) {
    const slice = hours.slice(i, i + size);
    const times = slice.map((h) => Date.parse(h.hourLocal));
    if (times.some((t, k) => t !== times[0] + k * HOUR_MS)) continue; // a gap in the forecast
    const typical = slice.every((h) => h.typicalCount !== null)
      ? slice.reduce((sum, h) => sum + (h.typicalCount as number), 0)
      : 0;
    const forecast = slice.reduce((sum, h) => sum + h.forecastCount, 0);
    const probs = slice.map((h) => h.precipProb).filter((p): p is number => p !== null);
    const localHours = slice.map((h) => Number(h.hourLocal.slice(11, 13)));
    out.push({
      startMs: times[0],
      endMs: times[0] + size * HOUR_MS,
      meanForecast: forecast / size,
      deltaPct: typical > 0 ? round1((forecast / typical - 1) * 100) : null,
      maxPrecipProb: probs.length ? Math.max(...probs) : null,
      rainRiskHours: slice.filter(isRainRisk).length,
      hasWeather: slice.every((h) => h.precipProb !== null || h.precipMm !== null),
      active: localHours.every((h) => h >= ACTIVE_FROM_HOUR && h < ACTIVE_TO_HOUR),
    });
  }
  return out;
}

type Preset = "mostTraffic" | "busyButDry" | "quietest";
type Role = keyof RecommendationSet;

/** Best first. Ties always go to the earlier block, so the result is deterministic. */
const ORDER: Record<Preset, (a: Block, b: Block) => number> = {
  mostTraffic: (a, b) => b.meanForecast - a.meanForecast || a.startMs - b.startMs,
  // Rain-risk hours decide first, so a dry block always beats a wet one however busy the wet one is.
  busyButDry: (a, b) => a.rainRiskHours - b.rainRiskHours || b.meanForecast - a.meanForecast || a.startMs - b.startMs,
  quietest: (a, b) => a.meanForecast - b.meanForecast || a.startMs - b.startMs,
};

function lead(preset: Preset, role: Role, block: Block): string {
  if (preset === "mostTraffic") {
    return { best: "Highest", secondBest: "Next-highest", avoid: "Lowest" }[role] + " forecast foot traffic";
  }
  if (preset === "quietest") {
    return { best: "Lowest", secondBest: "Next-lowest", avoid: "Highest" }[role] + " forecast foot traffic";
  }
  if (!block.hasWeather) return { best: "Busiest", secondBest: "Next-busiest", avoid: "Quietest" }[role] + " hours";
  if (role === "avoid") {
    return block.rainRiskHours > 0 ? "Most likely to be wet" : "Rain isn't likely, but the lowest forecast foot traffic";
  }
  if (block.rainRiskHours > 0) return "Rain is likely in every option; the busiest of the least rainy hours";
  return `${role === "best" ? "Busiest" : "Next-busiest"} hours where rain isn't likely`;
}

function reason(preset: Preset, role: Role, block: Block): string {
  const count = Math.round(block.meanForecast).toLocaleString("en-AU");
  const delta =
    block.deltaPct === null
      ? ""
      : Math.abs(block.deltaPct) < 5
        ? ", about typical for these hours"
        : `, ${Math.abs(Math.round(block.deltaPct))}% ${block.deltaPct > 0 ? "above" : "below"} typical`;
  const phrase = block.hasWeather ? rainPhrase(block.maxPrecipProb) : null;
  const rain = phrase === null ? "No rain forecast for these hours." : `${phrase[0].toUpperCase()}${phrase.slice(1)}.`;
  return `${lead(preset, role, block)}: about ${count} pedestrian counts an hour${delta}. ${rain}`;
}

function overlaps(a: Block, b: Block): boolean {
  return a.startMs < b.endMs && b.startMs < a.endMs;
}

function pick(preset: Preset, blocks: Block[]): RecommendationSet {
  const ranked = [...blocks].sort(ORDER[preset]);
  const best = ranked[0] ?? null;
  const secondBest = best ? (ranked.find((b) => !overlaps(b, best)) ?? null) : null;
  const taken = [best, secondBest].filter((b): b is Block => b !== null);
  const avoid = [...ranked].reverse().find((b) => taken.every((t) => !overlaps(b, t))) ?? null;
  const shape = (role: Role, block: Block | null): Recommendation | null =>
    block && {
      start: localIso(block.startMs),
      end: localIso(block.endMs),
      deltaPct: block.deltaPct,
      maxPrecipProb: block.maxPrecipProb,
      reason: reason(preset, role, block),
    };
  return { best: shape("best", best), secondBest: shape("secondBest", secondBest), avoid: shape("avoid", avoid) };
}

/**
 * Three presets, each with a best, a second-best (never overlapping the best)
 * and a block to avoid (never overlapping either). Entries are null when the
 * window has too few hours. No randomness and no model: same input, same output.
 */
export function recommend(hours: PlanHour[]): Recommendations {
  const all = blocksOf(hours);
  const active = all.filter((b) => b.active);
  const blocks = active.length ? active : all;
  return {
    mostTraffic: pick("mostTraffic", blocks),
    busyButDry: pick("busyButDry", blocks),
    quietest: pick("quietest", blocks),
    hoursConsidered: blocks.length
      ? {
          from: localIso(Math.min(...blocks.map((b) => b.startMs))),
          to: localIso(Math.max(...blocks.map((b) => b.endMs))),
          daytimeOnly: active.length > 0,
        }
      : null,
  };
}

const pct = (fraction: number | null) => (fraction === null ? null : Math.round(fraction * 1000) / 10);

function sensorsWithForecasts(snapshot: Snapshot): PlanSensor[] {
  const active = new Set(snapshot.forecasts.map((f) => f.sensorId));
  return snapshot.sensors
    .filter((s) => active.has(s.location_id))
    .map((s) => ({ id: s.location_id, name: s.name, lat: s.lat, lon: s.lon }))
    .sort((a, b) => a.name.localeCompare(b.name));
}

/** Sensors that currently have a forecast, by name: the options for the sensor picker. */
export function planSensors(snapshot: Snapshot): PlanSensor[] {
  return sensorsWithForecasts(snapshot);
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

/** The whole /api/plan response from one snapshot. null for a sensor id that has no forecast. */
export function assemblePlan(
  snapshot: Snapshot,
  sensor: number | "cbd",
  window: PlanWindow,
  nowMs: number
): PlanResponse | null {
  const meta = sensor === "cbd" ? "cbd" : sensorsWithForecasts(snapshot).find((s) => s.id === sensor);
  if (!meta) return null;

  const range = windowRange(nowMs, window);
  const { hours, sensorsUsed } = buildHours(snapshot.forecasts, snapshot.weather, sensor, range);
  const wanted = Math.round((range.endMs - range.startMs) / HOUR_MS);
  return {
    generatedAt: new Date(nowMs).toISOString(),
    dataFreshness: {
      forecastGeneratedAt: snapshot.latestWrite.forecasts,
      weatherFetchedAt: snapshot.latestWrite.weather,
      rainEffectComputedAt: snapshot.latestWrite.rainEffect,
      snapshotAt: snapshot.readAt,
    },
    sensor: meta,
    sensorsUsed,
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

function forestRows(method: RainMethod | null): Array<{ group: EvidenceRow["group"]; key: string; label: string }> {
  const m = method;
  return [
    { group: "overall", key: "all", label: "All wet hours" },
    { group: "intensity", key: "light", label: m ? `Light rain (${m.wetMm} to ${m.heavyMm} mm an hour)` : "Light rain" },
    { group: "intensity", key: "heavy", label: m ? `Heavy rain (${m.heavyMm} mm an hour or more)` : "Heavy rain" },
    { group: "daytype", key: "weekday", label: "Weekdays" },
    { group: "daytype", key: "weekend", label: "Weekends and public holidays" },
    { group: "temperature", key: "cold", label: m ? `Cold (below ${m.coldBelowC} °C)` : "Cold" },
    { group: "temperature", key: "mild", label: m ? `Mild (${m.coldBelowC} to ${m.warmAboveC} °C)` : "Mild" },
    { group: "temperature", key: "warm", label: m ? `Warm (above ${m.warmAboveC} °C)` : "Warm" },
  ];
}

/** Everything behind the rain-effect claim: forest-plot rows, the hourly profile and every sensor. */
export function assembleEvidence(snapshot: Snapshot, nowMs: number): EvidenceResponse {
  const find = (scope: string, key: string) => snapshot.rain.find((r) => r.scope === scope && r.key === key);
  const meta = new Map(snapshot.sensors.map((s) => [s.location_id, s]));
  return {
    generatedAt: new Date(nowMs).toISOString(),
    window: snapshot.rainWindow,
    computedAt: snapshot.latestWrite.rainEffect,
    method: snapshot.rainMethod,
    forest: forestRows(snapshot.rainMethod).flatMap(({ group, key, label }) => {
      const row = find(group, key);
      return row && row.effect !== null
        ? [{ group, key, label, value: pct(row.effect) as number, ciLow: pct(row.ciLow), ciHigh: pct(row.ciHigh),
             nWetHours: row.nWetHours, reliable: row.reliable }]
        : [];
    }),
    profile: snapshot.rainProfile.map((p) => ({
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
