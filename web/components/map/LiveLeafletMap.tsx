"use client";

import React, { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { SensorDetailSheet, type SensorDetailData } from "./SensorDetailSheet";
import { MapTopBar } from "./MapTopBar";
import type { SeriesPoint } from "@/lib/series";

export interface MapSensorItem {
  location_id: number;
  name: string;
  lat: number;
  lon: number;
  indoor: boolean;
  count: number;
  /** null = no 8-week baseline yet. */
  typical: number | null;
}

export interface MapParkingItem {
  kerbsideid: number;
  lat: number;
  lon: number;
  free: boolean;
  stale: boolean;
}

interface LiveLeafletMapProps {
  sensors: MapSensorItem[];
  parking: MapParkingItem[];
  summaryText?: string;
  updatedAt: string | null;
  renderedAt: string;
  /** Last 24 h actuals + next 24 h forecasts per sensor, keyed by real hour. */
  seriesBySensor: Record<number, SeriesPoint[]>;
}

export function LiveLeafletMap({
  sensors,
  parking,
  summaryText,
  updatedAt,
  renderedAt,
  seriesBySensor,
}: LiveLeafletMapProps) {
  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const parkingLayerRef = useRef<L.LayerGroup | null>(null);
  const sensorsLayerRef = useRef<L.LayerGroup | null>(null);

  const [parkingVisible, setParkingVisible] = useState(true);
  const [selectedSensor, setSelectedSensor] = useState<SensorDetailData | null>(null);

  // Parking stats
  const parkingStats = React.useMemo(() => {
    const nonStale = parking.filter((p) => !p.stale);
    const free = nonStale.filter((p) => p.free).length;
    return {
      free,
      total: nonStale.length,
      pct: nonStale.length > 0 ? Math.round((free / nonStale.length) * 100) : 0,
    };
  }, [parking]);

  useEffect(() => {
    if (!mapContainerRef.current || mapInstanceRef.current) return;

    // Melbourne CBD center
    const map = L.map(mapContainerRef.current, {
      center: [-37.8136, 144.9631],
      zoom: 15,
      minZoom: 12,
      maxZoom: 18,
      zoomControl: false,
    });

    // Zoom control in bottom right
    L.control.zoom({ position: "bottomright" }).addTo(map);

    // CARTO Dark Matter Tiles
    L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a> · City of Melbourne Open Data',
      subdomains: "abcd",
      maxZoom: 20,
    }).addTo(map);

    const sensorsLayer = L.layerGroup().addTo(map);
    const parkingLayer = L.layerGroup().addTo(map);

    sensorsLayerRef.current = sensorsLayer;
    parkingLayerRef.current = parkingLayer;
    mapInstanceRef.current = map;

    return () => {
      map.remove();
      mapInstanceRef.current = null;
    };
  }, []);

  // Render Pedestrian Sensors Layer
  useEffect(() => {
    const layer = sensorsLayerRef.current;
    if (!layer) return;
    layer.clearLayers();

    sensors.forEach((s) => {
      const delta = s.typical && s.typical > 0 ? ((s.count - s.typical) / s.typical) * 100 : null;
      let color = delta === null ? "#475569" : "#94A3B8"; // No baseline / Usual
      if (delta !== null && delta > 10) {
        color = "#00E5C7"; // Teal: Busier
      } else if (delta !== null && delta < -10) {
        color = "#2F6BFF"; // Blue: Quieter
      }

      // Radius in meters: scaled with foot traffic volume
      const radiusMeters = Math.max(18, Math.min(65, 15 + Math.sqrt(s.count) * 1.1));

      const circle = L.circle([s.lat, s.lon], {
        radius: radiusMeters,
        color: color,
        weight: 2,
        fillColor: color,
        fillOpacity: 0.4,
        className: "sensor-circle-marker",
      });

      // Hover tooltip
      const deltaText =
        delta === null ? "no baseline yet" : `${delta >= 0 ? "+" : ""}${delta.toFixed(0)}% vs usual`;
      circle.bindTooltip(
        `<strong>${s.name}</strong><br/>
         <span style="font-family:monospace;font-size:12px;">${s.count.toLocaleString()} people/hr</span>
         <span style="color:${color};font-weight:600;font-size:11px;"> (${deltaText})</span>`,
        { className: "dark-map-tooltip", direction: "top", offset: [0, -10] }
      );

      // On Click -> Open Detailed 24h Sensor Drawer
      circle.on("click", () => {
        setSelectedSensor({
          location_id: s.location_id,
          name: s.name,
          lat: s.lat,
          lon: s.lon,
          indoor: s.indoor,
          count: s.count,
          typical: s.typical,
          pctDelta: delta,
          series: seriesBySensor[s.location_id] ?? [],
        });
      });

      circle.addTo(layer);
    });
  }, [sensors, seriesBySensor]);

  // Render Parking Bays Layer
  useEffect(() => {
    const layer = parkingLayerRef.current;
    if (!layer) return;
    layer.clearLayers();

    if (!parkingVisible) return;

    parking.forEach((p) => {
      // Color coding: green free, red occupied, grey stale
      let color = "#64748B"; // Stale
      if (!p.stale) {
        color = p.free ? "#10B981" : "#F43F5E";
      }

      const marker = L.circleMarker([p.lat, p.lon], {
        radius: 3,
        weight: 1,
        color: color,
        fillColor: color,
        fillOpacity: 0.85,
      });

      marker.bindTooltip(
        `<div style="font-size:11px;font-family:monospace;">
          <strong>Bay #${p.kerbsideid}</strong><br/>
          Status: <span style="color:${color};font-weight:bold;">${
            p.stale ? "No recent report" : p.free ? "Free (Unoccupied)" : "Occupied"
          }</span>
        </div>`,
        { className: "dark-map-tooltip" }
      );

      marker.addTo(layer);
    });
  }, [parking, parkingVisible]);

  return (
    <div className="relative w-full h-[calc(100vh-4rem)] overflow-hidden bg-[#05080D]">
      {/* Top Map Control Bar */}
      <MapTopBar
        summaryText={summaryText}
        updatedAt={updatedAt}
        renderedAt={renderedAt}
        parkingVisible={parkingVisible}
        onToggleParking={() => setParkingVisible(!parkingVisible)}
        parkingStats={parkingStats}
      />

      {/* Leaflet Map Canvas */}
      <div ref={mapContainerRef} className="w-full h-full z-0" />

      {/* Floating Sensor Detail Drawer */}
      <SensorDetailSheet sensor={selectedSensor} onClose={() => setSelectedSensor(null)} />

      {/* Map Legend Overlay in Bottom Left */}
      <div className="absolute bottom-6 left-4 z-[900] p-3.5 rounded-2xl bg-[#05080D]/90 border border-white/10 backdrop-blur-xl shadow-2xl text-xs text-slate-300 space-y-2 max-w-xs">
        <div className="font-semibold text-white font-mono text-[11px] uppercase tracking-wider">
          Map Telemetry Layers
        </div>
        <div className="space-y-1.5 text-[11px]">
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-teal-400 border border-white/30" />
            <span>Pedestrians: Busier than typical (&gt;+10%)</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-blue-500 border border-white/30" />
            <span>Pedestrians: Quieter than typical (&lt;-10%)</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-slate-400 border border-white/30" />
            <span>Pedestrians: Usual (±10%)</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-slate-600 border border-white/30" />
            <span>Pedestrians: No baseline yet</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-400" />
            <span>Parking: Free Bay</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-rose-500" />
            <span>Parking: Occupied Bay</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-slate-500" />
            <span>Parking: Silent / Stale (&gt;24h)</span>
          </div>
        </div>
      </div>
    </div>
  );
}
