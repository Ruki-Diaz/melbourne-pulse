"use client";

import React, { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "maplibre-gl/dist/maplibre-gl.css";

import type { PlanSensor } from "@/lib/plan";

import { createCbdMap } from "./map-base";
import { escapeHtml } from "./plan-utils";

interface MiniSensorPickerMapProps {
  sensors: PlanSensor[];
  selectedSensor: number | "cbd";
  onSelectSensor: (sensorId: number | "cbd") => void;
}

/** A pointer shortcut for choosing a sensor. The Location list offers the same sensors by keyboard. */
export function MiniSensorPickerMap({ sensors, selectedSensor, onSelectSensor }: MiniSensorPickerMapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<L.Map | null>(null);
  const markersRef = useRef<L.LayerGroup | null>(null);
  const onSelectRef = useRef(onSelectSensor);

  useEffect(() => {
    onSelectRef.current = onSelectSensor;
  }, [onSelectSensor]);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = createCbdMap(containerRef.current);
    markersRef.current = L.layerGroup().addTo(map);
    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
      markersRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    const group = markersRef.current;
    if (!map || !group) return;
    group.clearLayers();

    for (const s of sensors) {
      const isSelected = selectedSensor === s.id;
      const marker = L.circleMarker([s.lat, s.lon], {
        radius: isSelected ? 9 : 6,
        fillColor: isSelected ? "#00E5C7" : "#3b82f6",
        color: isSelected ? "#ffffff" : "rgba(255, 255, 255, 0.5)",
        weight: isSelected ? 2.5 : 1,
        opacity: 1,
        fillOpacity: isSelected ? 1 : 0.8,
      });
      marker.bindTooltip(
        `<div style="font-size:12px;font-weight:500">${escapeHtml(s.name)}${isSelected ? " (selected)" : ""}</div>`,
        { className: "dark-map-tooltip", direction: "top", offset: [0, -6] }
      );
      marker.on("click", () => onSelectRef.current(s.id));
      marker.addTo(group);
      if (isSelected) {
        marker.bringToFront();
        map.panTo([s.lat, s.lon], { animate: true, duration: 0.5 });
      }
    }
  }, [sensors, selectedSensor]);

  return (
    <div className="relative w-full h-64 sm:h-72 rounded-xl overflow-hidden border border-white/10 bg-[#05080D]">
      <div ref={containerRef} className="plan-map w-full h-full" role="application" aria-label="Map of pedestrian sensors. Use the Location list to choose a sensor by keyboard." />
      <div className="absolute top-2 right-2 z-[400] bg-slate-950/90 backdrop-blur-md px-2.5 py-1 rounded-md border border-white/10 text-[11px] text-slate-200 flex items-center gap-2 pointer-events-none">
        <span className="inline-block w-2.5 h-2.5 rounded-full bg-teal-400" aria-hidden />
        <span>Selected</span>
        <span className="inline-block w-2.5 h-2.5 rounded-full bg-blue-500 ml-2" aria-hidden />
        <span>Sensor</span>
      </div>
    </div>
  );
}
