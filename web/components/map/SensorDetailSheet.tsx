"use client";

import React from "react";
import { X, MapPin, TrendingUp, TrendingDown, Clock, Activity } from "lucide-react";
import {
  ResponsiveContainer,
  ComposedChart,
  Line,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
} from "recharts";
import { motion, AnimatePresence } from "framer-motion";

import type { SeriesPoint } from "@/lib/series";
import { noComparisonLabel } from "@/lib/feed-anomaly";

export interface SensorDetailData {
  location_id: number;
  name: string;
  lat: number;
  lon: number;
  indoor: boolean;
  count: number;
  /** null = no 8-week baseline yet. */
  typical: number | null;
  pctDelta: number | null;
  /** Last 24 h actuals + next 24 h forecasts, keyed by real hour. */
  series: SeriesPoint[];
}

interface SensorDetailSheetProps {
  sensor: SensorDetailData | null;
  onClose: () => void;
  /** The hour is flagged (lib/feed-anomaly.ts): comparisons are withheld on purpose, not missing. */
  comparisonPaused?: boolean;
}

export function SensorDetailSheet({ sensor, onClose, comparisonPaused = false }: SensorDetailSheetProps) {
  if (!sensor) return null;

  const hasDelta = sensor.pctDelta !== null;
  const isBusier = hasDelta && (sensor.pctDelta as number) >= 0;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, x: 300 }}
        animate={{ opacity: 1, x: 0 }}
        exit={{ opacity: 0, x: 300 }}
        transition={{ type: "spring", damping: 25, stiffness: 200 }}
        className="fixed inset-y-0 right-0 z-[1100] w-full md:w-[460px] bg-[#05080D]/95 backdrop-blur-2xl border-l border-white/10 p-6 shadow-2xl flex flex-col justify-between overflow-y-auto"
      >
        {/* Header */}
        <div>
          <div className="flex items-start justify-between gap-4 mb-4">
            <div className="flex items-center gap-2 text-teal-400 font-mono text-xs font-semibold uppercase tracking-wider">
              <Activity className="w-4 h-4" />
              <span>Sensor Detail · #{sensor.location_id}</span>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="p-2 rounded-xl bg-white/5 hover:bg-white/10 text-slate-400 hover:text-white transition-colors"
              aria-label="Close sensor details"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          <h2 className="text-xl sm:text-2xl font-bold text-white font-['Space_Grotesk',sans-serif] mb-1">
            {sensor.name}
          </h2>
          <p className="text-xs text-slate-400 flex items-center gap-1.5 mb-6">
            <MapPin className="w-3.5 h-3.5 text-teal-400 shrink-0" />
            <span>
              {sensor.indoor ? "Indoor counting station" : "Outdoor street sensor"} ·{" "}
              {sensor.lat.toFixed(4)}, {sensor.lon.toFixed(4)}
            </span>
          </p>

          {/* Quick Metrics Cards */}
          <div className="grid grid-cols-2 gap-3 mb-6">
            <div className="p-4 rounded-xl bg-[#0d1424] border border-white/10">
              <span className="text-[11px] text-slate-400 uppercase tracking-wider font-medium block mb-1">
                Latest hour
              </span>
              <div className="text-2xl font-bold text-white font-mono">
                {sensor.count.toLocaleString()}
              </div>
              <span className="text-[10px] text-slate-400">pedestrians / hour</span>
            </div>

            <div className="p-4 rounded-xl bg-[#0d1424] border border-white/10">
              <span className="text-[11px] text-slate-400 uppercase tracking-wider font-medium block mb-1">
                vs 8-wk Typical
              </span>
              {hasDelta ? (
                <div
                  className={`text-2xl font-bold font-mono flex items-center gap-1 ${
                    isBusier ? "text-teal-400" : "text-blue-400"
                  }`}
                >
                  {isBusier ? <TrendingUp className="w-5 h-5" /> : <TrendingDown className="w-5 h-5" />}
                  {isBusier ? `+${(sensor.pctDelta as number).toFixed(0)}%` : `${(sensor.pctDelta as number).toFixed(0)}%`}
                </div>
              ) : (
                <div className="text-2xl font-bold font-mono text-slate-500">—</div>
              )}
              <span className="text-[10px] text-slate-400">
                typical: {sensor.typical === null ? noComparisonLabel(comparisonPaused, "no baseline yet") : sensor.typical.toLocaleString()}
              </span>
            </div>
          </div>

          {/* 24h Telemetry Chart */}
          <div className="p-4 rounded-xl bg-[#0d1424]/80 border border-white/10">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-semibold text-slate-200 flex items-center gap-1.5">
                <Clock className="w-3.5 h-3.5 text-teal-400" />
                Last 24 h and next 24 h
              </span>
              <span className="text-[10px] font-mono text-purple-400 bg-purple-950/60 px-2 py-0.5 rounded border border-purple-500/30">
                Actual · Forecast · Baseline
              </span>
            </div>

            <div className="h-56 w-full mt-2">
              {sensor.series.length === 0 ? (
                <div className="h-full flex items-center justify-center text-xs text-slate-500">
                  Waiting for the next update
                </div>
              ) : (
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={sensor.series} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#ffffff08" vertical={false} />
                  <XAxis
                    dataKey="hourLabel"
                    stroke="#64748B"
                    tick={{ fontSize: 9, fill: "#94A3B8" }}
                    interval={5}
                    tickLine={false}
                  />
                  <YAxis
                    stroke="#64748B"
                    tick={{ fontSize: 9, fill: "#94A3B8" }}
                    tickLine={false}
                  />
                  <Tooltip
                    content={({ active, payload, label }) => {
                      if (active && payload && payload.length) {
                        return (
                          <div className="rounded-xl bg-[#05080D]/95 border border-white/15 p-3 text-xs backdrop-blur-xl shadow-xl space-y-1 font-mono">
                            <p className="font-bold text-slate-100 font-sans mb-1">{label}</p>
                            {payload.map((item) => (
                              <div
                                key={item.name}
                                className="flex items-center justify-between gap-3 text-[11px]"
                                style={{ color: item.color }}
                              >
                                <span>{item.name}:</span>
                                <span className="font-bold text-white">
                                  {item.value !== null && item.value !== undefined
                                    ? Math.round(Number(item.value)).toLocaleString()
                                    : "—"}
                                </span>
                              </div>
                            ))}
                          </div>
                        );
                      }
                      return null;
                    }}
                  />
                  <Legend
                    verticalAlign="top"
                    align="right"
                    wrapperStyle={{ fontSize: "10px", paddingBottom: "6px" }}
                  />
                  <Line
                    type="monotone"
                    dataKey="typical"
                    name="Typical"
                    stroke="#3B82F6"
                    strokeWidth={1.5}
                    strokeDasharray="3 3"
                    dot={false}
                  />
                  <Line
                    type="monotone"
                    dataKey="forecast"
                    name="LightGBM"
                    stroke="#A855F7"
                    strokeWidth={2}
                    dot={false}
                  />
                  <Area
                    type="monotone"
                    dataKey="actual"
                    name="Actual"
                    stroke="#00E5C7"
                    strokeWidth={2.5}
                    fill="#00E5C7"
                    fillOpacity={0.15}
                    dot={{ r: 2.5, fill: "#00E5C7" }}
                  />
                </ComposedChart>
              </ResponsiveContainer>
              )}
            </div>
          </div>
        </div>

        {/* Footer Note */}
        <div className="pt-4 mt-6 border-t border-white/10 text-[11px] text-slate-500">
          Sensor data provided under CC BY by City of Melbourne Open Data. Forecasts produced daily by LightGBM.
        </div>
      </motion.div>
    </AnimatePresence>
  );
}
