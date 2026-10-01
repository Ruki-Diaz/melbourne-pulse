"use client";

import React, { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { Activity, MapPin } from "lucide-react";
import Link from "next/link";

export interface SensorPoint {
  location_id: number;
  name: string;
  lat: number;
  lon: number;
  count: number;
  typical: number;
}

export interface ProjectedSensorPoint extends SensorPoint {
  x: number;
  y: number;
  delta: number;
  status: "busier" | "quieter" | "usual";
  radius: number;
}

interface CityRightNowMapProps {
  sensors: SensorPoint[];
}

export function CityRightNowMap({ sensors }: CityRightNowMapProps) {
  const [hoveredSensor, setHoveredSensor] = useState<ProjectedSensorPoint | null>(null);

  // Map sensor coordinates to SVG viewBox (width 900, height 600)
  const viewBoxWidth = 900;
  const viewBoxHeight = 600;
  const padding = 60;

  const { projectedSensors } = useMemo(() => {
    if (!sensors.length) return { projectedSensors: [] };

    let minLat = Infinity,
      maxLat = -Infinity,
      minLon = Infinity,
      maxLon = -Infinity;

    sensors.forEach((s) => {
      if (s.lat < minLat) minLat = s.lat;
      if (s.lat > maxLat) maxLat = s.lat;
      if (s.lon < minLon) minLon = s.lon;
      if (s.lon > maxLon) maxLon = s.lon;
    });

    if (maxLat === minLat) {
      maxLat += 0.01;
      minLat -= 0.01;
    }
    if (maxLon === minLon) {
      maxLon += 0.01;
      minLon -= 0.01;
    }

    const projected: ProjectedSensorPoint[] = sensors.map((s) => {
      const x = padding + ((s.lon - minLon) / (maxLon - minLon)) * (viewBoxWidth - padding * 2);
      const y = padding + ((maxLat - s.lat) / (maxLat - minLat)) * (viewBoxHeight - padding * 2);

      const delta = s.typical > 0 ? ((s.count - s.typical) / s.typical) * 100 : 0;
      let status: "busier" | "quieter" | "usual" = "usual";
      if (delta > 10) status = "busier";
      else if (delta < -10) status = "quieter";

      const radius = Math.max(3.5, Math.min(14, 4 + Math.sqrt(s.count) * 0.22));

      return {
        ...s,
        x,
        y,
        delta,
        status,
        radius,
      };
    });

    return {
      projectedSensors: projected,
    };
  }, [sensors]);

  return (
    <section className="py-20 max-w-6xl mx-auto px-4 sm:px-6">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-8 gap-4">
        <div>
          <div className="flex items-center gap-2 text-teal-400 font-mono text-xs font-semibold uppercase tracking-wider mb-2">
            <Activity className="w-4 h-4" />
            <span>Spatial Footprint</span>
          </div>
          <h2 className="text-2xl sm:text-3xl font-bold text-white font-['Space_Grotesk',sans-serif]">
            The City Right Now
          </h2>
          <p className="text-sm text-slate-400 mt-1 max-w-xl">
            Real sensor coordinates across Melbourne CBD. Dot size reflects current pedestrian volume; colour indicates activity relative to typical.
          </p>
        </div>

        {/* Legend */}
        <div className="flex items-center gap-4 bg-[#0d1424]/90 border border-white/10 px-4 py-2 rounded-xl backdrop-blur-md text-xs font-medium text-slate-300">
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-full bg-teal-400 shadow-[0_0_8px_rgba(0,229,199,0.8)]" />
            <span>Busier (&gt;+10%)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-slate-400" />
            <span>Usual (±10%)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-blue-500 shadow-[0_0_8px_rgba(47,107,255,0.8)]" />
            <span>Quieter (&lt;-10%)</span>
          </div>
        </div>
      </div>

      {/* SVG Canvas Container */}
      <div className="relative rounded-2xl bg-gradient-to-b from-[#080d18] to-[#04060a] border border-white/10 p-4 sm:p-6 overflow-hidden shadow-2xl">
        {/* Subtle grid background */}
        <div
          aria-hidden="true"
          className="absolute inset-0 bg-[linear-gradient(to_right,#ffffff05_1px,transparent_1px),linear-gradient(to_bottom,#ffffff05_1px,transparent_1px)] bg-[size:40px_40px] pointer-events-none"
        />

        {/* SVG Visualization */}
        <div className="relative w-full aspect-[4/3] sm:aspect-[16/10] max-h-[560px]">
          <svg
            viewBox={`0 0 ${viewBoxWidth} ${viewBoxHeight}`}
            className="w-full h-full"
            aria-label="Interactive map of Melbourne CBD pedestrian sensors"
          >
            <defs>
              <radialGradient id="tealGlow" cx="50%" cy="50%" r="50%">
                <stop offset="0%" stopColor="#00E5C7" stopOpacity="0.8" />
                <stop offset="50%" stopColor="#00E5C7" stopOpacity="0.25" />
                <stop offset="100%" stopColor="#00E5C7" stopOpacity="0" />
              </radialGradient>
              <radialGradient id="blueGlow" cx="50%" cy="50%" r="50%">
                <stop offset="0%" stopColor="#2F6BFF" stopOpacity="0.8" />
                <stop offset="50%" stopColor="#2F6BFF" stopOpacity="0.25" />
                <stop offset="100%" stopColor="#2F6BFF" stopOpacity="0" />
              </radialGradient>
            </defs>

            {/* Connecting web lines */}
            <g opacity="0.15" stroke="#00E5C7" strokeWidth="0.5" strokeDasharray="3 3">
              {projectedSensors.slice(0, 15).map((s, idx) => {
                const next = projectedSensors[(idx + 1) % 15];
                return <line key={`line-${idx}`} x1={s.x} y1={s.y} x2={next.x} y2={next.y} />;
              })}
            </g>

            {/* Sensor Dots */}
            {projectedSensors.map((s) => {
              const isTeal = s.status === "busier";
              const isBlue = s.status === "quieter";
              const color = isTeal ? "#00E5C7" : isBlue ? "#2F6BFF" : "#94A3B8";

              return (
                <g
                  key={s.location_id}
                  className="cursor-pointer transition-transform duration-200"
                  onMouseEnter={() => setHoveredSensor(s)}
                  onMouseLeave={() => setHoveredSensor(null)}
                >
                  {/* Outer pulse for busy sensors */}
                  {isTeal && (
                    <circle
                      cx={s.x}
                      cy={s.y}
                      r={s.radius * 2.4}
                      fill="url(#tealGlow)"
                      className="animate-pulse"
                      opacity="0.7"
                    />
                  )}
                  {isBlue && (
                    <circle
                      cx={s.x}
                      cy={s.y}
                      r={s.radius * 1.8}
                      fill="url(#blueGlow)"
                      opacity="0.5"
                    />
                  )}

                  {/* Core Sensor Circle */}
                  <circle
                    cx={s.x}
                    cy={s.y}
                    r={s.radius}
                    fill={color}
                    stroke="#05080D"
                    strokeWidth="1.5"
                    className="hover:stroke-white transition-all duration-150"
                  />
                </g>
              );
            })}
          </svg>

          {/* Interactive Hover Tooltip */}
          {hoveredSensor && (
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: -8 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              className="absolute z-30 pointer-events-none p-3 rounded-xl bg-[#0d1424]/95 border border-teal-500/40 backdrop-blur-xl shadow-[0_10px_30px_rgba(0,0,0,0.8)] text-xs text-white max-w-xs"
              style={{
                left: `${(hoveredSensor.x / viewBoxWidth) * 100}%`,
                top: `${(hoveredSensor.y / viewBoxHeight) * 100}%`,
                transform: "translate(-50%, -120%)",
              }}
            >
              <div className="font-semibold text-sm text-slate-100 flex items-center gap-1.5 mb-1">
                <MapPin className="w-3.5 h-3.5 text-teal-400 shrink-0" />
                <span className="truncate">{hoveredSensor.name}</span>
              </div>
              <div className="flex items-baseline gap-2 font-mono">
                <span className="text-lg font-bold text-white">
                  {hoveredSensor.count.toLocaleString()}
                </span>
                <span className="text-slate-400">pedestrians/hr</span>
              </div>
              <div className="mt-1 pt-1.5 border-t border-white/10 flex items-center justify-between text-[11px]">
                <span className="text-slate-400">Typical: {hoveredSensor.typical.toLocaleString()}</span>
                <span
                  className={`font-semibold font-mono ${
                    hoveredSensor.delta > 0
                      ? "text-teal-400"
                      : hoveredSensor.delta < 0
                      ? "text-blue-400"
                      : "text-slate-300"
                  }`}
                >
                  {hoveredSensor.delta > 0 ? `+${hoveredSensor.delta.toFixed(0)}%` : `${hoveredSensor.delta.toFixed(0)}%`}
                  {" vs usual"}
                </span>
              </div>
            </motion.div>
          )}
        </div>

        {/* Action Link to Full Leaflet Map */}
        <div className="mt-4 pt-4 border-t border-white/10 flex items-center justify-between">
          <span className="text-xs text-slate-400">
            Plotting {sensors.length} live pedestrian counting stations in Melbourne CBD.
          </span>
          <Link
            href="/map"
            className="text-xs font-semibold text-teal-400 hover:text-teal-300 flex items-center gap-1 transition-colors"
          >
            <span>Explore full interactive map &amp; parking</span>
            <span>&rarr;</span>
          </Link>
        </div>
      </div>
    </section>
  );
}
