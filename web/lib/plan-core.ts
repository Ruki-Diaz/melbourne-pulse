/**
 * Pure logic for the Plan API: time windows, hour rows and recommendations.
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
 * One row per hour in the range that has a forecast. For "cbd" the counts are
 * summed over sensors; typicalCount is only given when every sensor in that
 * hour has one, and deltaPct compares like with like (sensors that have both).
 */
export function buildHours(
  forecasts: ForecastPoint[],
  weather: WeatherPoint[],
  sensor: number | "cbd",
  range: { startMs: number; endMs: number }
): PlanHour[] {
  type Sum = { predicted: number; rows: number; typical: number; withTypical: number; predictedWithTypical: number };
  const byHour = new Map<number, Sum>();
  for (const f of forecasts) {
    if (f.ms < range.startMs || f.ms >= range.endMs) continue;
    if (sensor !== "cbd" && f.sensorId !== sensor) continue;
    const sum = byHour.get(f.ms) ?? { predicted: 0, rows: 0, typical: 0, withTypical: 0, predictedWithTypical: 0 };
    sum.predicted += f.predicted;
    sum.rows += 1;
    if (f.baseline !== null) {
      sum.typical += f.baseline;
      sum.withTypical += 1;
      sum.predictedWithTypical += f.predicted;
    }
    byHour.set(f.ms, sum);
  }
  const weatherAt = new Map(weather.map((w) => [w.ms, w]));
  return [...byHour.entries()]
    .sort(([a], [b]) => a - b)
    .map(([ms, sum]) => {
      const w = weatherAt.get(ms);
      return {
        hourLocal: localIso(ms),
        forecastCount: Math.round(sum.predicted),
        typicalCount: sum.withTypical === sum.rows ? Math.round(sum.typical) : null,
        deltaPct: sum.typical > 0 ? round1((sum.predictedWithTypical / sum.typical - 1) * 100) : null,
        precipMm: w?.precipMm ?? null,
        precipProb: w?.precipProb ?? null,
        tempC: w?.tempC ?? null,
        windKmh: w?.windKmh ?? null,
        weatherCode: w?.weatherCode ?? null,
      };
    });
}

export function isRainRisk(hour: PlanHour): boolean {
  return (hour.precipProb ?? 0) >= WET_PROB_PCT || (hour.precipMm ?? 0) >= WET_MM;
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

type Preset = keyof Recommendations;
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
  if (role === "avoid") return block.rainRiskHours > 0 ? "Most likely to be wet" : "Dry, but the lowest forecast foot traffic";
  if (block.rainRiskHours > 0) return "No fully dry option here; the busiest of the least rainy hours";
  return role === "best" ? "Busiest dry hours" : "Next-busiest dry hours";
}

function reason(preset: Preset, role: Role, block: Block): string {
  const count = Math.round(block.meanForecast).toLocaleString("en-AU");
  const delta =
    block.deltaPct === null
      ? ""
      : Math.abs(block.deltaPct) < 5
        ? ", about typical for these hours"
        : `, ${Math.abs(Math.round(block.deltaPct))}% ${block.deltaPct > 0 ? "above" : "below"} typical`;
  const rain = !block.hasWeather || block.maxPrecipProb === null
    ? "No weather forecast for these hours."
    : `Rain ${block.rainRiskHours > 0 ? "likely" : "unlikely"} (up to ${Math.round(block.maxPrecipProb)}% chance).`;
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
  };
}
