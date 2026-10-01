"use client";

import React, { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "maplibre-gl/dist/maplibre-gl.css";

import type { EvidenceResponse } from "@/lib/plan";

import { createCbdMap } from "./map-base";
import { count, escapeHtml, signedPct } from "./plan-utils";

type Sensor = EvidenceResponse["sensors"][number];

/** Display bands for the dots (percent change in a wet hour). Presentation only. */
const STRONG_DROP_PCT = -30;
const DROP_PCT = -15;

export const SENSITIVITY_LEGEND = [
  { color: "#F43F5E", label: `Drops by more than ${Math.abs(STRONG_DROP_PCT)}%` },
  { color: "#38BDF8", label: `Drops by ${Math.abs(DROP_PCT)}% to ${Math.abs(STRONG_DROP_PCT)}%` },
  { color: "#00E5C7", label: `Drops by less than ${Math.abs(DROP_PCT)}%` },
  { color: "#F59E0B", label: "Rises" },
  { color: "#94A3B8", label: "Not a reliable estimate" },
];

function colorFor(s: Sensor): string {
  if (!s.reliable) return "#94A3B8";
  if (s.value > 0) return "#F59E0B";
  if (s.value <= STRONG_DROP_PCT) return "#F43F5E";
  return s.value <= DROP_PCT ? "#38BDF8" : "#00E5C7";
}

/** Every sensor's own rain effect on a map. The same figures are in the table below it. */
export function SensorSensitivityMap({ sensors }: { sensors: Sensor[] }) {
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    const map = createCbdMap(containerRef.current);
    const group = L.layerGroup().addTo(map);

    for (const s of sensors) {
      if (s.lat === null || s.lon === null) continue;
      const color = colorFor(s);
      const interval = s.ciLow !== null && s.ciHigh !== null ? `, 95% interval ${signedPct(s.ciLow)} to ${signedPct(s.ciHigh)}` : "";
      L.circleMarker([s.lat, s.lon], {
        radius: s.reliable ? 7 : 5,
        fillColor: color,
        color: "#ffffff",
        weight: 1,
        opacity: 0.8,
        fillOpacity: s.reliable ? 0.9 : 0.5,
      })
        .bindTooltip(
          `<div style="font-size:12px;max-width:220px;white-space:normal">
            <div style="font-weight:600">${escapeHtml(s.name)}</div>
            <div style="color:${color};font-family:monospace;margin-top:2px">${signedPct(s.value)} in a wet hour</div>
            <div style="color:#cbd5e1;font-size:11px;margin-top:2px">${count(s.nWetHours)} wet hours${interval}</div>
            ${s.reliable ? "" : `<div style="color:#fcd34d;font-size:11px;margin-top:2px">Not a reliable estimate</div>`}
          </div>`,
          { className: "dark-map-tooltip", direction: "top", offset: [0, -6] }
        )
        .addTo(group);
    }
    return () => {
      map.remove();
    };
  }, [sensors]);

  return (
    <div className="space-y-2">
      <div className="relative w-full h-80 sm:h-96 rounded-xl overflow-hidden border border-white/10 bg-[#05080D]">
        <div ref={containerRef} className="plan-map w-full h-full" role="application" aria-label="Map of each sensor's rain effect. The table below lists the same figures." />
      </div>
      <ul className="flex flex-wrap gap-x-4 gap-y-1.5 text-xs text-slate-300">
        {SENSITIVITY_LEGEND.map((item) => (
          <li key={item.label} className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: item.color }} aria-hidden />
            <span>{item.label}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
