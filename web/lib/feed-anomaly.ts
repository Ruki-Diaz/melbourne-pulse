/**
 * What the site says when the pipeline has flagged the current hour: most
 * sensors read far below their typical at once (pipeline/feed_quality.py,
 * table feed_quality). The cause isn't known at that point. It may be severe
 * weather, a major event or a fault in the city's feed, and the wording says so.
 *
 * In that state nothing may claim the CBD is "X% quieter" or "busier": the
 * headline becomes the notice below, the raw count is still shown, and every
 * comparison with typical is paused. No imports, so pytest can run it
 * (pipeline/tests/test_quality.py via scripts/feed-anomaly-check.mjs).
 */

/** The same sentence pipeline/summary.py writes (FEED_ANOMALY_TEXT). */
export const FEED_ANOMALY_TEXT =
  "Foot traffic is far below normal across most sensors. This may be severe weather, a major event, or a sensor feed issue.";

/** Under the raw count on the stat card: the same sentence. */
export const FEED_ANOMALY_COUNT_NOTE = FEED_ANOMALY_TEXT;

/** Shown where a sensor's comparison with typical would be, while a flagged hour is on screen. */
export const COMPARISON_PAUSED = "Comparison paused";

/**
 * The label for a sensor with no comparison to show. A sensor that simply has
 * no 8-week baseline keeps its usual label; one withheld because the hour is
 * flagged says the comparison is paused, since its baseline exists.
 */
export function noComparisonLabel(paused: boolean, noBaseline: string): string {
  if (!paused) return noBaseline;
  // Match the case of the label being replaced ("no baseline yet" sits mid-sentence).
  return noBaseline[0] === noBaseline[0].toLowerCase() ? COMPARISON_PAUSED.toLowerCase() : COMPARISON_PAUSED;
}

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
