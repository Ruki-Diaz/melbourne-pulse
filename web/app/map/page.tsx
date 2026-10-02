import React from "react";
import { getAllLatest, getFeedAnomaly, getForecasts, getRecentPedestrianHistory, type SensorMeta } from "@/lib/db";
import { forDisplay, headline } from "@/lib/feed-anomaly";
import { buildTime } from "@/lib/freshness";
import { buildSeriesBySensor, floorHour, HOUR_MS } from "@/lib/series";
import { MapWrapper } from "@/components/map/MapWrapper";
import type { MapSensorItem, MapParkingItem } from "@/components/map/LiveLeafletMap";

export const revalidate = 3600;

export const metadata = {
  title: "Live Map · Melbourne Pulse",
  description: "Real-time interactive map of pedestrian congestion and on-street parking bays across Melbourne CBD.",
};

export default async function MapPage() {
  const [latestData, forecasts, history] = await Promise.all([
    getAllLatest(),
    getForecasts(),
    getRecentPedestrianHistory(24),
  ]);
  const { pedestrian, parking, sensors: sensorMetaList, summary } = latestData;

  // The pipeline flagged this hour as a fault in the city's feed: raw counts only, with a warning.
  const feedAnomaly = await getFeedAnomaly(pedestrian?.payload?.hour);

  const { now, renderedAt } = buildTime();

  const sensorLookup = new Map<number, SensorMeta>();
  sensorMetaList?.payload?.forEach((s) => sensorLookup.set(s.location_id, s));

  const liveSensors: MapSensorItem[] = forDisplay(pedestrian?.payload?.sensors ?? [], feedAnomaly)
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
        typical: s.typical,
      };
    })
    .filter((s): s is MapSensorItem => s !== null);

  const liveParking: MapParkingItem[] = (parking?.payload ?? []).map((p) => ({
    kerbsideid: p.kerbsideid,
    lat: p.lat,
    lon: p.lon,
    free: p.free,
    stale: p.stale,
  }));

  // Per-sensor chart: actual for the last 24 h, the model's forecast and each
  // hour's own typical from 24 h back to 24 h ahead.
  const seriesBySensor = buildSeriesBySensor(
    history,
    forecasts,
    floorHour(now) - 24 * HOUR_MS,
    floorHour(now) + 25 * HOUR_MS
  );

  return (
    <main className="relative w-full h-[calc(100vh-4rem)] overflow-hidden bg-[#05080D]">
      <MapWrapper
        sensors={liveSensors}
        parking={liveParking}
        summaryText={headline(summary?.payload?.text, feedAnomaly)}
        feedAnomaly={feedAnomaly !== null}
        updatedAt={pedestrian?.updatedAt.toISOString() ?? null}
        renderedAt={renderedAt}
        seriesBySensor={seriesBySensor}
      />
    </main>
  );
}
