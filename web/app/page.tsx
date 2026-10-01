import React from "react";
import {
  getAllLatest,
  getForecasts,
  getRecentPedestrianHistory,
  type SensorMeta,
} from "@/lib/db";
import { buildTime } from "@/lib/freshness";
import { buildSeriesBySensor, floorHour, HOUR_MS } from "@/lib/series";
import { HeroWrapper } from "@/components/landing/HeroWrapper";
import { StatStrip } from "@/components/landing/StatStrip";
import { CityRightNowMap, type SensorPoint } from "@/components/landing/CityRightNowMap";
import {
  BusiestSensorsSparklines,
  type SensorSparklineData,
} from "@/components/landing/BusiestSensorsSparklines";
import {
  CBDTomorrowForecast,
  type CBDHourlyForecastPoint,
} from "@/components/landing/CBDTomorrowForecast";
import { HowItWorksSection } from "@/components/landing/HowItWorksSection";
import { BuiltBySection } from "@/components/landing/BuiltBySection";

// Cached for 1 hour; revalidated on-demand by /api/revalidate after hourly ingest.
export const revalidate = 3600;

// Every number on this page comes from the database. When something is
// missing the components show "Waiting for the next update", never a guess.
export default async function HomePage() {
  const [latestData, forecasts, history] = await Promise.all([
    getAllLatest(),
    getForecasts(),
    getRecentPedestrianHistory(18),
  ]);
  const { pedestrian, parking, sensors: sensorMetaList, summary } = latestData;

  const { now, renderedAt } = buildTime();
  const updatedAt = pedestrian?.updatedAt.toISOString() ?? null;

  const sensorLookup = new Map<number, SensorMeta>();
  sensorMetaList?.payload?.forEach((s) => sensorLookup.set(s.location_id, s));

  // 1. Stat strip
  const liveSensors = pedestrian?.payload?.sensors ?? [];
  const totalPedestrians = liveSensors.length ? liveSensors.reduce((acc, s) => acc + (s.count || 0), 0) : null;

  let pctParkingFree: number | null = null;
  if (Array.isArray(parking?.payload)) {
    const reporting = parking.payload.filter((p) => !p.stale);
    if (reporting.length > 0) {
      pctParkingFree = Math.round((reporting.filter((p) => p.free).length / reporting.length) * 100);
    }
  }

  let busiestSpot: { name: string; count: number } | null = null;
  if (liveSensors.length > 0) {
    const top = [...liveSensors].sort((a, b) => (b.count || 0) - (a.count || 0))[0];
    busiestSpot = { name: sensorLookup.get(top.location_id)?.name ?? `Sensor #${top.location_id}`, count: top.count };
  }

  // 2. Sensor points for the SVG map
  const citySensors: SensorPoint[] = liveSensors
    .map((s) => {
      const meta = sensorLookup.get(s.location_id);
      if (!meta) return null;
      return { location_id: s.location_id, name: meta.name, lat: meta.lat, lon: meta.lon, count: s.count, typical: s.typical };
    })
    .filter((s): s is SensorPoint => s !== null);

  // 3. Sparklines for the 6 busiest sensors: the last 8 complete hours, each
  //    with that hour's own stored baseline.
  const recent = buildSeriesBySensor(history, forecasts, floorHour(now) - 8 * HOUR_MS, floorHour(now));
  const sparklineCards: SensorSparklineData[] = [...citySensors]
    .sort((a, b) => b.count - a.count)
    .slice(0, 6)
    .map((s) => ({
      location_id: s.location_id,
      name: s.name,
      count: s.count,
      typical: s.typical,
      pctDelta: s.typical && s.typical > 0 ? ((s.count - s.typical) / s.typical) * 100 : null,
      sparkline: (recent[s.location_id] ?? [])
        .filter((p) => p.actual !== null)
        .map((p) => ({ hour: p.hourLabel.split(" ")[1], actual: p.actual as number, typical: p.typical })),
    }));

  // 4. CBD-wide forecast for the next 24 hours
  const firstHour = floorHour(now) + HOUR_MS;
  const byHour = new Map<number, { predicted: number; typical: number; rows: number; baselines: number }>();
  for (const f of forecasts) {
    const t = Date.parse(f.hour);
    if (t < firstHour || t >= firstHour + 24 * HOUR_MS) continue;
    const agg = byHour.get(t) ?? { predicted: 0, typical: 0, rows: 0, baselines: 0 };
    agg.predicted += f.predicted_count;
    agg.rows += 1;
    if (f.baseline_count != null) {
      agg.typical += f.baseline_count;
      agg.baselines += 1;
    }
    byHour.set(t, agg);
  }
  const cbdForecastData: CBDHourlyForecastPoint[] = [...byHour.entries()]
    .sort(([a], [b]) => a - b)
    .map(([t, v]) => ({
      hourLabel: new Date(t)
        .toLocaleTimeString("en-AU", { hour: "numeric", hour12: true, timeZone: "Australia/Melbourne" })
        .replace(/\s/g, "")
        .toLowerCase(),
      hourIso: new Date(t).toISOString(),
      predicted: Math.round(v.predicted),
      // Only sum the baseline if every sensor in that hour has one.
      typical: v.baselines === v.rows ? Math.round(v.typical) : null,
    }));

  let forecastCallout: string | undefined;
  if (cbdForecastData.length > 0) {
    const peak = cbdForecastData.reduce((max, p) => (p.predicted > max.predicted ? p : max));
    const day = new Date(peak.hourIso).toLocaleDateString("en-AU", { weekday: "long", timeZone: "Australia/Melbourne" });
    forecastCallout = `Predicted peak at ${peak.hourLabel} on ${day}`;
    if (peak.typical) {
      const delta = ((peak.predicted - peak.typical) / peak.typical) * 100;
      forecastCallout += `, ${delta >= 0 ? "+" : ""}${delta.toFixed(0)}% relative to the 8-week baseline`;
    }
    forecastCallout += ".";
  }

  return (
    <div className="flex flex-col min-h-screen bg-[#05080D] text-slate-100 selection:bg-teal-500/30 selection:text-teal-200">
      {/* 1. WebGL2 Glass Headline Hero */}
      <HeroWrapper
        updatedAt={updatedAt}
        renderedAt={renderedAt}
        title="Melbourne, live."
        description={
          summary?.payload?.text ||
          "See how busy the CBD is right now, and what the next 24 hours look like."
        }
        primaryAction={{ label: "Open the live map", href: "/map" }}
        secondaryAction={{ label: "How it works", href: "#how" }}
        colors={["#05080D", "#00E5C7", "#2F6BFF", "#7C3AED", "#D6FFF7"]}
      />

      {/* 2. Glass Stat Strip overlapping Hero */}
      <StatStrip
        totalPedestrians={totalPedestrians}
        pctParkingFree={pctParkingFree}
        busiestSpot={busiestSpot}
        hourIso={pedestrian?.payload?.hour ?? null}
        updatedAt={updatedAt}
        renderedAt={renderedAt}
      />

      {/* 3. The City Right Now (SVG Real Coordinates) */}
      <CityRightNowMap sensors={citySensors} />

      {/* 4. Right Now vs Usual (6 Recharts Sparklines) */}
      <BusiestSensorsSparklines sensors={sparklineCards} />

      {/* 5. The next 24 hours, predicted (CBD-wide) */}
      <CBDTomorrowForecast data={cbdForecastData} calloutText={forecastCallout} />

      {/* 6. How it works (#how) */}
      <HowItWorksSection />

      {/* 7. Built By Section */}
      <BuiltBySection />
    </div>
  );
}
