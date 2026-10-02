/**
 * What the site says when the pipeline has flagged the current hour as a fault
 * in the city's sensor feed (pipeline/feed_quality.py, table feed_quality).
 *
 * In that state nothing may claim the CBD is "X% quieter" or "busier": the
 * headline becomes the warning below, the raw count is still shown, and every
 * comparison with typical is withheld. No imports, so pytest can run it
 * (pipeline/tests/test_quality.py via scripts/feed-anomaly-check.mjs).
 */

/** The same sentence pipeline/summary.py writes (FEED_ANOMALY_TEXT). */
export const FEED_ANOMALY_TEXT = "The city's sensor feed looks unusual right now. Counts may be incomplete.";

/** Under the raw count on the stat card. */
export const FEED_ANOMALY_COUNT_NOTE = "Raw count. The feed looks unusual, so it may be incomplete.";

export type FeedAnomaly = { sensorsJudged: number; sensorsLow: number; shareLow: number | null };

/** The headline sentence: the stored summary, or the warning whenever the hour is flagged. */
export function headline(summaryText: string | null | undefined, anomaly: FeedAnomaly | null): string | undefined {
  return anomaly ? FEED_ANOMALY_TEXT : (summaryText ?? undefined);
}

/**
 * Sensors as the page should show them. During an anomaly each keeps its raw
 * count but loses its typical, so no component can draw or word a comparison.
 */
export function forDisplay<T extends { typical: number | null }>(sensors: T[], anomaly: FeedAnomaly | null): T[] {
  return anomaly ? sensors.map((s) => ({ ...s, typical: null })) : sensors;
}
