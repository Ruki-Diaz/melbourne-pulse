import React from "react";
import { getAllLatest, getForecasts, getRecentPedestrianHistory, type SensorMeta } from "@/lib/db";
import { MapWrapper } from "@/components/map/MapWrapper";
import type { MapSensorItem, MapParkingItem } from "@/components/map/LiveLeafletMap";

export const revalidate = 3600;

export const metadata = {
  title: "Live Map · Melbourne Pulse",
  description: "Real-time interactive map of pedestrian congestion and on-street parking bays across Melbourne CBD.",
};

function getMinutesAgo(date: Date | string | undefined | null): number {
  if (!date) return 5;
  const target = new Date(date).getTime();
  const current = new Date().getTime();
  return Math.max(1, Math.round((current - target) / 60000));
}

export default async function MapPage() {
  const [latestData, forecasts, history] = await Promise.all([
    getAllLatest(),
    getForecasts(),
    getRecentPedestrianHistory(24),
  ]);

  const { pedestrian, parking, sensors: sensorMetaList, summary } = latestData;

  // Calculate staleness
  const latestTimestamp = pedestrian?.updatedAt ?? summary?.updatedAt;
  const updatedMinutesAgo = getMinutesAgo(latestTimestamp);
  const isStale = updatedMinutesAgo > 180; // Amber warning if older than 3 hours

  // Lookup for sensor metadata
  const sensorLookup = new Map<number, SensorMeta>();
  if (sensorMetaList?.payload) {
    sensorMetaList.payload.forEach((s) => sensorLookup.set(s.location_id, s));
  }

  // Build sensor items
  const liveSensors: MapSensorItem[] = (pedestrian?.payload?.sensors ?? [])
    .map((s) => {
      const meta = sensorLookup.get(s.location_id);
      if (!meta) return null;
      return {
        location_id: s.location_id,
        name: meta.name,
        lat: meta.lat,
        lon: meta.lon,
        indoor: meta.indoor,
        count: s.count,
        typical: s.typical || 1,
      };
    })
    .filter((s): s is MapSensorItem => s !== null);

  // Build parking items
  const liveParking: MapParkingItem[] = (parking?.payload ?? []).map((p) => ({
    kerbsideid: p.kerbsideid,
    lat: p.lat,
    lon: p.lon,
    free: p.free,
    stale: p.stale,
  }));

  // Group forecasts by sensor
  const forecastsBySensor: Record<number, Array<{ hourLabel: string; forecast: number; typical: number }>> = {};
  forecasts.forEach((f) => {
    const list = forecastsBySensor[f.sensor_id] || [];
    const dateObj = new Date(f.hour);
    const hourLabel = dateObj.toLocaleTimeString("en-AU", {
      hour: "numeric",
      hour12: true,
      timeZone: "Australia/Melbourne",
    });
    list.push({
      hourLabel,
      forecast: f.predicted_count,
      typical: f.baseline_count ?? f.predicted_count * 0.95,
    });
    forecastsBySensor[f.sensor_id] = list;
  });

  // Group history by sensor
  const historyBySensor: Record<number, Array<{ hourLabel: string; actual: number }>> = {};
  history.forEach((h) => {
    const list = historyBySensor[h.location_id] || [];
    const dateObj = new Date(h.hour);
    const hourLabel = dateObj.toLocaleTimeString("en-AU", {
      hour: "numeric",
      hour12: true,
      timeZone: "Australia/Melbourne",
    });
    list.push({ hourLabel, actual: h.count });
    historyBySensor[h.location_id] = list;
  });

  return (
    <main className="relative w-full h-[calc(100vh-4rem)] overflow-hidden bg-[#05080D]">
      <MapWrapper
        sensors={liveSensors}
        parking={liveParking}
        summaryText={summary?.payload?.text}
        updatedMinutesAgo={updatedMinutesAgo}
        isStale={isStale}
        forecastsBySensor={forecastsBySensor}
        historyBySensor={historyBySensor}
      />
    </main>
  );
}
