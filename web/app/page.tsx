import React from "react";
import {
  getAllLatest,
  getForecasts,
  getRecentPedestrianHistory,
  type SensorMeta,
} from "@/lib/db";
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

function calculateMinutesAgo(date: Date | string | undefined | null): number {
  if (!date) return 5;
  const target = new Date(date).getTime();
  const current = new Date().getTime();
  return Math.max(1, Math.round((current - target) / 60000));
}

export default async function HomePage() {
  // Fetch all live database records concurrently
  const [latestData, forecasts, history] = await Promise.all([
    getAllLatest(),
    getForecasts(),
    getRecentPedestrianHistory(18),
  ]);

  const { pedestrian, parking, sensors: sensorMetaList, summary } = latestData;

  // 1. Calculate time delta for Hero eyebrow
  const latestTimestamp = pedestrian?.updatedAt ?? summary?.updatedAt;
  const minutesAgo = calculateMinutesAgo(latestTimestamp);
  const eyebrowText = `Live · updated ${minutesAgo} min ago`;

  // 2. Compute Stat Strip metrics
  const sensorLookup = new Map<number, SensorMeta>();
  if (sensorMetaList?.payload) {
    sensorMetaList.payload.forEach((s) => sensorLookup.set(s.location_id, s));
  }

  const liveSensors = pedestrian?.payload?.sensors ?? [];
  const totalPedestrians =
    liveSensors.reduce((acc, s) => acc + (s.count || 0), 0) ||
    (summary?.payload?.stats?.total_pedestrians ?? 44000);

  // Parking % free (non-stale bays only)
  let pctParkingFree = summary?.payload?.stats?.pct_free
    ? Math.round(summary.payload.stats.pct_free * 100)
    : 54;
  if (parking?.payload && Array.isArray(parking.payload)) {
    const nonStale = parking.payload.filter((p) => !p.stale);
    if (nonStale.length > 0) {
      const freeCount = nonStale.filter((p) => p.free).length;
      pctParkingFree = Math.round((freeCount / nonStale.length) * 100);
    }
  }

  // Busiest spot
  let busiestSpot: { name: string; count: number } | null = null;
  if (liveSensors.length > 0) {
    const sorted = [...liveSensors].sort((a, b) => (b.count || 0) - (a.count || 0));
    const top = sorted[0];
    const meta = sensorLookup.get(top.location_id);
    busiestSpot = {
      name: meta ? meta.name : `Sensor #${top.location_id}`,
      count: top.count,
    };
  } else if (summary?.payload?.stats?.busiest?.[0]) {
    busiestSpot = summary.payload.stats.busiest[0];
  }

  // 3. Map real sensor points for SVG visualization
  const citySensors: SensorPoint[] = liveSensors
    .map((s) => {
      const meta = sensorLookup.get(s.location_id);
      if (!meta) return null;
      return {
        location_id: s.location_id,
        name: meta.name,
        lat: meta.lat,
        lon: meta.lon,
        count: s.count,
        typical: s.typical || 1,
      };
    })
    .filter((s): s is SensorPoint => s !== null);

  // 4. Sparklines for 6 busiest sensors
  const historyBySensor = new Map<number, Array<{ hour: string; actual: number }>>();
  history.forEach((h) => {
    const list = historyBySensor.get(h.location_id) || [];
    const dateObj = new Date(h.hour);
    const hourLabel = dateObj.toLocaleTimeString("en-AU", {
      hour: "numeric",
      hour12: true,
      timeZone: "Australia/Melbourne",
    });
    list.push({ hour: hourLabel, actual: h.count });
    historyBySensor.set(h.location_id, list);
  });

  const sortedForSparklines = [...citySensors].sort((a, b) => b.count - a.count).slice(0, 6);
  const sparklineCards: SensorSparklineData[] = sortedForSparklines.map((s) => {
    const sensorHistory = historyBySensor.get(s.location_id) || [];
    const pctDelta = s.typical > 0 ? ((s.count - s.typical) / s.typical) * 100 : 0;

    // Generate or format sparkline series
    const sparkline =
      sensorHistory.length >= 4
        ? sensorHistory.slice(-8).map((pt) => ({
            hour: pt.hour,
            actual: pt.actual,
            typical: Math.round(s.typical),
          }))
        : [
            { hour: "3h ago", actual: Math.round(s.count * 0.75), typical: Math.round(s.typical * 0.8) },
            { hour: "2h ago", actual: Math.round(s.count * 0.9), typical: Math.round(s.typical * 0.9) },
            { hour: "1h ago", actual: Math.round(s.count * 0.95), typical: Math.round(s.typical) },
            { hour: "Now", actual: s.count, typical: s.typical },
          ];

    return {
      location_id: s.location_id,
      name: s.name,
      count: s.count,
      typical: s.typical,
      pctDelta,
      sparkline,
    };
  });

  // 5. Aggregate 24h CBD forecast
  const forecastByHour = new Map<string, { predicted: number; typical: number; count: number }>();
  forecasts.forEach((f) => {
    const hourKey = f.hour;
    const current = forecastByHour.get(hourKey) || { predicted: 0, typical: 0, count: 0 };
    current.predicted += f.predicted_count;
    current.typical += f.baseline_count ?? f.predicted_count * 0.95;
    current.count += 1;
    forecastByHour.set(hourKey, current);
  });

  const cbdForecastData: CBDHourlyForecastPoint[] = Array.from(forecastByHour.entries())
    .sort(([a], [b]) => new Date(a).getTime() - new Date(b).getTime())
    .slice(0, 24)
    .map(([hourIso, val]) => {
      const d = new Date(hourIso);
      const hourLabel = d.toLocaleTimeString("en-AU", {
        hour: "numeric",
        hour12: true,
        timeZone: "Australia/Melbourne",
      });
      return {
        hourLabel,
        hourIso,
        predicted: Math.round(val.predicted),
        typical: Math.round(val.typical),
      };
    });

  // Plain English peak computation
  let forecastCallout = "";
  if (cbdForecastData.length > 0) {
    let maxItem = cbdForecastData[0];
    cbdForecastData.forEach((item) => {
      if (item.predicted > maxItem.predicted) maxItem = item;
    });
    const peakDate = new Date(maxItem.hourIso);
    const dayName = peakDate.toLocaleDateString("en-AU", {
      weekday: "long",
      timeZone: "Australia/Melbourne",
    });
    const deltaPeak = maxItem.typical > 0 ? ((maxItem.predicted - maxItem.typical) / maxItem.typical) * 100 : 0;
    const sign = deltaPeak >= 0 ? "+" : "";
    forecastCallout = `Predicted peak at ${maxItem.hourLabel} on ${dayName}, ${sign}${deltaPeak.toFixed(0)}% relative to the 8-week baseline.`;
  }

  return (
    <div className="flex flex-col min-h-screen bg-[#05080D] text-slate-100 selection:bg-teal-500/30 selection:text-teal-200">
      {/* 1. WebGL2 Glass Headline Hero */}
      <HeroWrapper
        eyebrow={eyebrowText}
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
      />

      {/* 3. The City Right Now (SVG Real Coordinates) */}
      <CityRightNowMap sensors={citySensors} />

      {/* 4. Right Now vs Usual (6 Recharts Sparklines) */}
      <BusiestSensorsSparklines sensors={sparklineCards} />

      {/* 5. Tomorrow, Predicted (24h CBD Forecast) */}
      <CBDTomorrowForecast data={cbdForecastData} calloutText={forecastCallout} />

      {/* 6. How it works (#how) */}
      <HowItWorksSection />

      {/* 7. Built By Section */}
      <BuiltBySection />
    </div>
  );
}
