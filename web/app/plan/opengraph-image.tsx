import { ImageResponse } from "next/og";

import { formatBlock, rainChip } from "@/components/plan/plan-utils";
import { getPlan } from "@/lib/plan";
import type { Recommendation } from "@/lib/plan-core";

export const runtime = "nodejs";
export const revalidate = 3600;

export const alt = "Plan your CBD visit: the best time by forecast foot traffic and rain";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

const CARD = {
  display: "flex",
  flexDirection: "column",
  padding: "20px 32px",
  backgroundColor: "rgba(13, 20, 36, 0.8)",
  borderRadius: "20px",
  border: "1px solid rgba(255, 255, 255, 0.1)",
  minWidth: "300px",
} as const;

/**
 * Share card for /plan, in the same style as the site's main card. It shows
 * the "busy but dry" pick for the whole CBD: for the rest of today if there is
 * one, otherwise for the next 36 hours. Rebuilt at most hourly; with no data it
 * shows the title alone rather than a guess.
 */
export default async function Image() {
  let best: Recommendation | null = null;
  let avoid: Recommendation | null = null;
  let scope = "today";
  let sensorsUsed = 0;
  try {
    for (const [window, label] of [["today", "today"], ["36h", "in the next 36 hours"]] as const) {
      const plan = await getPlan("cbd", window);
      if (plan?.recommendations.busyButDry.best) {
        ({ best, avoid } = plan.recommendations.busyButDry);
        scope = label;
        sensorsUsed = plan.sensorsUsed;
        break;
      }
    }
  } catch (error) {
    console.error("plan share card: no data:", error);
  }

  return new ImageResponse(
    (
      <div
        style={{
          height: "100%",
          width: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          backgroundColor: "#05080D",
          backgroundImage:
            "radial-gradient(circle at 25% 25%, rgba(0, 229, 199, 0.15), transparent 45%), radial-gradient(circle at 75% 75%, rgba(47, 107, 255, 0.15), transparent 45%)",
          padding: "60px 80px",
          fontFamily: "sans-serif",
          color: "#F8FAFC",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
            <div style={{ width: "20px", height: "20px", borderRadius: "50%", backgroundColor: "#00E5C7", boxShadow: "0 0 20px #00E5C7" }} />
            <span style={{ fontSize: "24px", fontWeight: 800, letterSpacing: "2px", color: "#FFFFFF" }}>
              MELBOURNE<span style={{ color: "#00E5C7" }}>PULSE</span>
            </span>
          </div>
          <div
            style={{
              display: "flex",
              padding: "8px 20px",
              borderRadius: "999px",
              backgroundColor: "rgba(0, 229, 199, 0.1)",
              border: "1px solid rgba(0, 229, 199, 0.3)",
              color: "#00E5C7",
              fontSize: "16px",
              fontFamily: "monospace",
              fontWeight: 600,
            }}
          >
            PLAN AHEAD
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: "16px", maxWidth: "980px" }}>
          <h1 style={{ fontSize: "68px", fontWeight: 900, lineHeight: 1.05, letterSpacing: "-2px", color: "#FFFFFF", margin: 0 }}>
            Plan your CBD visit
          </h1>
          <p style={{ fontSize: "24px", color: "#94A3B8", lineHeight: 1.4, margin: 0 }}>
            {best ? best.reason : "Forecast foot traffic and the chance of rain, hour by hour, for Melbourne's CBD."}
          </p>
        </div>

        <div style={{ display: "flex", gap: "24px" }}>
          <div style={CARD}>
            <span style={{ fontSize: "14px", color: "#94A3B8", textTransform: "uppercase", letterSpacing: "1px" }}>
              {`Best time ${scope}`}
            </span>
            <span style={{ fontSize: "38px", fontWeight: 800, color: "#00E5C7", fontFamily: "monospace" }}>
              {best ? formatBlock(best.start, best.end) : "—"}
            </span>
            <span style={{ fontSize: "12px", color: "#94A3B8" }}>
              {best ? `busy but dry · ${rainChip(best.maxPrecipProb).text.toLowerCase()}` : "waiting for the forecast"}
            </span>
          </div>

          {avoid && (
            <div style={CARD}>
              <span style={{ fontSize: "14px", color: "#94A3B8", textTransform: "uppercase", letterSpacing: "1px" }}>Avoid</span>
              <span style={{ fontSize: "38px", fontWeight: 800, color: "#F43F5E", fontFamily: "monospace" }}>
                {formatBlock(avoid.start, avoid.end)}
              </span>
              <span style={{ fontSize: "12px", color: "#94A3B8" }}>{rainChip(avoid.maxPrecipProb).text.toLowerCase()}</span>
            </div>
          )}

          {sensorsUsed > 0 && (
            <div style={{ ...CARD, minWidth: "200px" }}>
              <span style={{ fontSize: "14px", color: "#94A3B8", textTransform: "uppercase", letterSpacing: "1px" }}>Whole CBD</span>
              <span style={{ fontSize: "38px", fontWeight: 800, color: "#A855F7", fontFamily: "monospace" }}>{sensorsUsed}</span>
              <span style={{ fontSize: "12px", color: "#94A3B8" }}>sensors in the forecast</span>
            </div>
          )}
        </div>
      </div>
    ),
    { ...size }
  );
}
