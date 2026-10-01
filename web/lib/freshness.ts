/**
 * One freshness rule for every page and the OG image:
 *   under 2 h old  -> "Live · updated X min ago"
 *   older          -> "Last updated X h ago" (shown in amber)
 *   no data        -> "Waiting for the next update"
 */

export const LIVE_FOR_MS = 2 * 60 * 60 * 1000;

export type FreshnessState = "live" | "stale" | "empty";

export interface Freshness {
  state: FreshnessState;
  label: string;
}

export function getFreshness(
  updatedAt: string | number | Date | null | undefined,
  now: number = Date.now()
): Freshness {
  if (updatedAt == null) return { state: "empty", label: "Waiting for the next update" };
  const ageMs = Math.max(0, now - new Date(updatedAt).getTime());
  if (ageMs < LIVE_FOR_MS) {
    const minutes = Math.floor(ageMs / 60_000);
    return { state: "live", label: minutes < 1 ? "Live · updated just now" : `Live · updated ${minutes} min ago` };
  }
  const hours = Math.floor(ageMs / 3_600_000);
  return {
    state: "stale",
    label: hours >= 48 ? `Last updated ${Math.floor(hours / 24)} days ago` : `Last updated ${hours} h ago`,
  };
}

/** "10am" in Melbourne time, for labelling the hour a count belongs to. */
export function melbourneHourLabel(iso: string): string {
  return new Date(iso)
    .toLocaleTimeString("en-AU", { hour: "numeric", hour12: true, timeZone: "Australia/Melbourne" })
    .replace(/\s/g, "")
    .toLowerCase();
}

/**
 * When the server is building this page. Reading the clock is deliberate:
 * pages are regenerated at most hourly, and the browser re-checks freshness
 * against its own clock (see useFreshness).
 */
export function buildTime(): { now: number; renderedAt: string } {
  const now = Date.now();
  return { now, renderedAt: new Date(now).toISOString() };
}
