import { ImageResponse } from "next/og";
import { getAllLatest } from "@/lib/db";
import { getFreshness } from "@/lib/freshness";
import metrics from "@/lib/model-metrics.json";

export const runtime = "nodejs";
export const revalidate = 3600;

export const alt = "Melbourne Pulse — Live Civic Pedestrian & Parking Telemetry";
export const size = {
  width: 1200,
  height: 630,
};
export const contentType = "image/png";

// Rendered at most hourly (and re-warmed by the hourly Action), so the badge is
// accurate to within the hour. Same freshness rule as the pages.
const BADGE = {
  live: { color: "#00E5C7", background: "rgba(0, 229, 199, 0.1)", border: "rgba(0, 229, 199, 0.3)" },
  stale: { color: "#FBBF24", background: "rgba(245, 158, 11, 0.12)", border: "rgba(245, 158, 11, 0.45)" },
  empty: { color: "#CBD5E1", background: "rgba(100, 116, 139, 0.15)", border: "rgba(100, 116, 139, 0.4)" },
} as const;

export default async function Image() {
  let totalPedestrians: number | null = null;
  let pctParking: number | null = null;
  let updatedAt: Date | null = null;
  let summaryText = "Live pedestrian counts and free parking bays across Melbourne CBD.";

  try {
    const data = await getAllLatest();
    updatedAt = data.pedestrian?.updatedAt ?? null;
    if (data.pedestrian?.payload?.sensors?.length) {
      totalPedestrians = data.pedestrian.payload.sensors.reduce(
        (acc, s) => acc + (s.count || 0),
        0
      );
    }
    if (data.summary?.payload?.text) {
      summaryText = data.summary.payload.text;
    }
    if (data.parking?.payload) {
      const nonStale = data.parking.payload.filter((p) => !p.stale);
      if (nonStale.length > 0) {
        const free = nonStale.filter((p) => p.free).length;
        pctParking = Math.round((free / nonStale.length) * 100);
      }
    }
  } catch (e) {
    console.error("OpenGraph image query fallback:", e);
  }
  const freshness = getFreshness(updatedAt);
  const badge = BADGE[freshness.state];
  const badgeText =
    freshness.state === "live" ? "● LIVE" : freshness.state === "stale" ? `◷ ${freshness.label.toUpperCase()}` : "WAITING FOR THE NEXT UPDATE";

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
        {/* Top Header */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
            <div
              style={{
                width: "20px",
                height: "20px",
                borderRadius: "50%",
                backgroundColor: "#00E5C7",
                boxShadow: "0 0 20px #00E5C7",
              }}
            />
            <span
              style={{
                fontSize: "24px",
                fontWeight: 800,
                letterSpacing: "2px",
                color: "#FFFFFF",
              }}
            >
              MELBOURNE<span style={{ color: "#00E5C7" }}>PULSE</span>
            </span>
          </div>

          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              padding: "8px 20px",
              borderRadius: "999px",
              backgroundColor: badge.background,
              border: `1px solid ${badge.border}`,
              color: badge.color,
              fontSize: "16px",
              fontFamily: "monospace",
              fontWeight: 600,
            }}
          >
            {badgeText}
          </div>
        </div>

        {/* Center Main Title */}
        <div style={{ display: "flex", flexDirection: "column", gap: "16px", maxWidth: "900px" }}>
          <h1
            style={{
              fontSize: "68px",
              fontWeight: 900,
              lineHeight: 1.05,
              letterSpacing: "-2px",
              color: "#FFFFFF",
              margin: 0,
            }}
          >
            Melbourne, live.
          </h1>
          <p
            style={{
              fontSize: "24px",
              color: "#94A3B8",
              lineHeight: 1.4,
              margin: 0,
            }}
          >
            {summaryText}
          </p>
        </div>

        {/* Bottom Metrics Bar */}
        <div
          style={{
            display: "flex",
            gap: "24px",
          }}
        >
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              padding: "20px 32px",
              backgroundColor: "rgba(13, 20, 36, 0.8)",
              borderRadius: "20px",
              border: "1px solid rgba(255, 255, 255, 0.1)",
              minWidth: "240px",
            }}
          >
            <span style={{ fontSize: "14px", color: "#94A3B8", textTransform: "uppercase", letterSpacing: "1px" }}>
              CBD Walking Traffic
            </span>
            <span style={{ fontSize: "38px", fontWeight: 800, color: "#00E5C7", fontFamily: "monospace" }}>
              {totalPedestrians === null ? "—" : totalPedestrians.toLocaleString()}
            </span>
            <span style={{ fontSize: "12px", color: "#64748B" }}>
              {totalPedestrians === null ? "waiting for data" : "pedestrian counts in the latest hour"}
            </span>
          </div>

          <div
            style={{
              display: "flex",
              flexDirection: "column",
              padding: "20px 32px",
              backgroundColor: "rgba(13, 20, 36, 0.8)",
              borderRadius: "20px",
              border: "1px solid rgba(255, 255, 255, 0.1)",
              minWidth: "240px",
            }}
          >
            <span style={{ fontSize: "14px", color: "#94A3B8", textTransform: "uppercase", letterSpacing: "1px" }}>
              Street Parking Free
            </span>
            <span style={{ fontSize: "38px", fontWeight: 800, color: "#10B981", fontFamily: "monospace" }}>
              {pctParking === null ? "—" : `${pctParking}%`}
            </span>
            <span style={{ fontSize: "12px", color: "#64748B" }}>
              {pctParking === null ? "waiting for data" : "bays reporting in the last 24 h"}
            </span>
          </div>

          <div
            style={{
              display: "flex",
              flexDirection: "column",
              padding: "20px 32px",
              backgroundColor: "rgba(13, 20, 36, 0.8)",
              borderRadius: "20px",
              border: "1px solid rgba(255, 255, 255, 0.1)",
              minWidth: "240px",
            }}
          >
            <span style={{ fontSize: "14px", color: "#94A3B8", textTransform: "uppercase", letterSpacing: "1px" }}>
              Forecast Engine
            </span>
            <span style={{ fontSize: "38px", fontWeight: 800, color: "#A855F7", fontFamily: "monospace" }}>
              LightGBM
            </span>
            <span style={{ fontSize: "12px", color: "#64748B" }}>{`${metrics.improvementPct}% lower MAE`}</span>
          </div>
        </div>
      </div>
    ),
    {
      ...size,
    }
  );
}
