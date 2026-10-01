/**
 * Formatting helpers for the Plan page. Nothing here produces a number of its
 * own: every value shown comes from the API (docs/plan-api.md).
 */

import { rainTier, type RainTier } from "@/lib/plan-core";

const TZ = "Australia/Melbourne";

/** Keyboard focus ring shared by every control on the page. */
export const FOCUS_RING =
  "focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-400 focus-visible:ring-offset-2 focus-visible:ring-offset-[#05080D]";

export const CARD = "rounded-2xl border border-white/10 bg-[#0d1424]/80 backdrop-blur-xl shadow-[0_8px_30px_rgba(0,0,0,0.4)]";

/** WMO weather codes, as Open-Meteo reports them. */
const WEATHER: Record<number, string> = {
  0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
  45: "Fog", 48: "Fog",
  51: "Light drizzle", 53: "Drizzle", 55: "Heavy drizzle", 56: "Freezing drizzle", 57: "Freezing drizzle",
  61: "Light rain", 63: "Rain", 65: "Heavy rain", 66: "Freezing rain", 67: "Freezing rain",
  71: "Light snow", 73: "Snow", 75: "Heavy snow", 77: "Snow grains",
  80: "Light showers", 81: "Showers", 82: "Heavy showers", 85: "Snow showers", 86: "Snow showers",
  95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Thunderstorm with hail",
};

export function weatherLabel(code: number | null): string | null {
  if (code === null) return null;
  return WEATHER[code] ?? `Weather code ${code}`;
}

const TIER_STYLE: Record<RainTier, { label: string; chip: string; dot: string }> = {
  low: { label: "Low rain risk", chip: "bg-emerald-950/60 border-emerald-500/30 text-emerald-300", dot: "bg-emerald-400" },
  some: { label: "Some rain risk", chip: "bg-amber-950/60 border-amber-500/40 text-amber-300", dot: "bg-amber-400" },
  likely: { label: "Rain likely", chip: "bg-sky-950/60 border-sky-500/40 text-sky-300", dot: "bg-sky-400" },
};

/** The rain chip: the same three tiers the API uses in its reasons, always with the percentage. */
export function rainChip(maxPrecipProb: number | null): { text: string; chip: string; dot: string } {
  if (maxPrecipProb === null) {
    return { text: "No rain forecast", chip: "bg-slate-800/80 border-slate-600/60 text-slate-300", dot: "bg-slate-400" };
  }
  const style = TIER_STYLE[rainTier(maxPrecipProb)];
  return { text: `${style.label} (${Math.round(maxPrecipProb)}%)`, chip: style.chip, dot: style.dot };
}

function hourLabel(iso: string): string {
  return new Date(iso)
    .toLocaleTimeString("en-AU", { hour: "numeric", hour12: true, timeZone: TZ })
    .replace(/\s/g, "")
    .toLowerCase();
}

function weekday(iso: string, style: "short" | "long" = "short"): string {
  return new Date(iso).toLocaleDateString("en-AU", { weekday: style, timeZone: TZ });
}

/** "Fri 6pm–8pm". The end is exclusive, so a block ending at midnight reads "12am". */
export function formatBlock(startIso: string, endIso: string): string {
  return `${weekday(startIso)} ${hourLabel(startIso)}–${hourLabel(endIso)}`;
}

/** "Fri 7am – Sat 12pm", or "Fri 7am – 6pm" when both ends fall on one day. */
export function formatRange(fromIso: string, toIso: string): string {
  const lastHourIso = new Date(Date.parse(toIso) - 1).toISOString();
  const sameDay = weekday(fromIso) === weekday(lastHourIso) && Date.parse(toIso) - Date.parse(fromIso) <= 24 * 3_600_000;
  return `${weekday(fromIso)} ${hourLabel(fromIso)} – ${sameDay ? "" : `${weekday(toIso)} `}${hourLabel(toIso)}`;
}

/** "9am" for a 0-23 hour of the day. */
export function clockHour(hour: number): string {
  return `${hour % 12 || 12}${hour < 12 ? "am" : "pm"}`;
}

/** "6% below a usual Friday"; null when there is no typical to compare with. */
export function formatDelta(deltaPct: number | null, startIso: string): string | null {
  if (deltaPct === null) return null;
  const day = weekday(startIso, "long");
  const rounded = Math.round(Math.abs(deltaPct));
  if (rounded < 5) return `About typical for a ${day}`;
  return `${rounded}% ${deltaPct > 0 ? "above" : "below"} a usual ${day}`;
}

/** Axis label: "3pm", with the weekday on the first hour and at each midnight. */
export function axisHour(iso: string, first: boolean): string {
  const label = hourLabel(iso);
  return first || label === "12am" ? `${weekday(iso)} ${label}` : label;
}

/** "Fri 2 Oct, 6pm" */
export function formatHourLong(iso: string): string {
  const date = new Date(iso).toLocaleDateString("en-AU", { weekday: "short", day: "numeric", month: "short", timeZone: TZ });
  return `${date}, ${hourLabel(iso)}`;
}

/** "2 Oct 2026" for a YYYY-MM-DD date. */
export function formatDay(day: string): string {
  return new Date(`${day}T00:00:00Z`).toLocaleDateString("en-AU", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
}

/** "18 min ago" / "3 h ago" / "2 days ago"; null if the time is unknown. */
export function formatAge(iso: string | null, nowMs: number): string | null {
  if (!iso || nowMs <= 0) return null;
  const mins = Math.floor(Math.max(0, nowMs - Date.parse(iso)) / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  const hours = Math.floor(mins / 60);
  return hours < 48 ? `${hours} h ago` : `${Math.floor(hours / 24)} days ago`;
}

/** "−18.5%" / "+4.2%", with a real minus sign. */
export function signedPct(value: number): string {
  return `${value > 0 ? "+" : value < 0 ? "−" : ""}${Math.abs(value)}%`;
}

export function count(value: number): string {
  return value.toLocaleString("en-AU");
}

export function escapeHtml(text: string): string {
  return text.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c] as string);
}
