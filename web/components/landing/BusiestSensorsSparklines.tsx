"use client";

import React from "react";
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { motion } from "framer-motion";
import { TrendingUp, TrendingDown, Clock } from "lucide-react";

export interface SensorSparklineData {
  location_id: number;
  name: string;
  count: number;
  typical: number;
  pctDelta: number;
  sparkline: Array<{
    hour: string;
    actual: number;
    typical: number;
  }>;
}

interface BusiestSensorsSparklinesProps {
  sensors: SensorSparklineData[];
}

export function BusiestSensorsSparklines({ sensors }: BusiestSensorsSparklinesProps) {
  if (!sensors || sensors.length === 0) return null;

  return (
    <section className="py-20 max-w-6xl mx-auto px-4 sm:px-6">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-8 gap-4">
        <div>
          <div className="flex items-center gap-2 text-teal-400 font-mono text-xs font-semibold uppercase tracking-wider mb-2">
            <Clock className="w-4 h-4" />
            <span>Real-time Dynamics</span>
          </div>
          <h2 className="text-2xl sm:text-3xl font-bold text-white font-['Space_Grotesk',sans-serif]">
            Right Now vs Usual
          </h2>
          <p className="text-sm text-slate-400 mt-1 max-w-xl">
            Today&apos;s actual foot traffic compared with the 8-week typical baseline across the top 6 busiest corridors.
          </p>
        </div>
      </div>

      {/* Grid of 6 Sparkline Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {sensors.slice(0, 6).map((sensor, idx) => {
          const isBusier = sensor.pctDelta >= 0;
          const deltaSign = isBusier ? "+" : "";
          const badgeText = `${deltaSign}${sensor.pctDelta.toFixed(0)}% ${
            isBusier ? "busier" : "quieter"
          }`;

          return (
            <motion.div
              key={sensor.location_id}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.4, delay: idx * 0.08 }}
              className="p-5 rounded-2xl bg-[#0d1424]/80 border border-white/10 hover:border-white/20 backdrop-blur-xl transition-all duration-200 flex flex-col justify-between group"
            >
              {/* Header */}
              <div>
                <div className="flex items-start justify-between gap-2 mb-2">
                  <h3 className="font-semibold text-sm sm:text-base text-slate-100 truncate flex-1 group-hover:text-teal-300 transition-colors">
                    {sensor.name}
                  </h3>
                  <span
                    className={`inline-flex items-center gap-1 text-[11px] font-mono font-semibold px-2 py-0.5 rounded-full shrink-0 ${
                      isBusier
                        ? "bg-teal-500/10 text-teal-300 border border-teal-500/30"
                        : "bg-blue-500/10 text-blue-300 border border-blue-500/30"
                    }`}
                  >
                    {isBusier ? (
                      <TrendingUp className="w-3 h-3" />
                    ) : (
                      <TrendingDown className="w-3 h-3" />
                    )}
                    {badgeText}
                  </span>
                </div>

                <div className="flex items-baseline gap-2 mb-4 font-mono">
                  <span className="text-2xl font-bold text-white">
                    {sensor.count.toLocaleString()}
                  </span>
                  <span className="text-xs text-slate-400">
                    /hr (typical: {sensor.typical.toLocaleString()})
                  </span>
                </div>
              </div>

              {/* Recharts Sparkline */}
              <div className="h-28 w-full mt-2">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={sensor.sparkline} margin={{ top: 5, right: 0, left: -20, bottom: 0 }}>
                    <defs>
                      <linearGradient id={`grad-actual-${sensor.location_id}`} x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#00E5C7" stopOpacity={0.4} />
                        <stop offset="95%" stopColor="#00E5C7" stopOpacity={0.0} />
                      </linearGradient>
                      <linearGradient id={`grad-typical-${sensor.location_id}`} x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#2F6BFF" stopOpacity={0.25} />
                        <stop offset="95%" stopColor="#2F6BFF" stopOpacity={0.0} />
                      </linearGradient>
                    </defs>
                    <XAxis
                      dataKey="hour"
                      stroke="#475569"
                      tick={{ fontSize: 9, fill: "#64748B" }}
                      interval="preserveStartEnd"
                      axisLine={false}
                      tickLine={false}
                    />
                    <YAxis hide domain={["auto", "auto"]} />
                    <Tooltip
                      content={({ active, payload, label }) => {
                        if (active && payload && payload.length) {
                          return (
                            <div className="rounded-lg bg-[#05080D]/95 border border-white/10 p-2 text-xs backdrop-blur-md shadow-lg">
                              <p className="font-semibold text-slate-200 mb-1">{label}</p>
                              <div className="flex items-center gap-2 text-teal-300">
                                <span className="w-2 h-2 rounded-full bg-teal-400" />
                                <span>Actual: {payload[0]?.value?.toLocaleString()}</span>
                              </div>
                              <div className="flex items-center gap-2 text-blue-300">
                                <span className="w-2 h-2 rounded-full bg-blue-400" />
                                <span>Typical: {payload[1]?.value?.toLocaleString()}</span>
                              </div>
                            </div>
                          );
                        }
                        return null;
                      }}
                    />
                    <Area
                      type="monotone"
                      dataKey="typical"
                      stroke="#3B82F6"
                      strokeWidth={1.5}
                      strokeDasharray="3 3"
                      fillOpacity={1}
                      fill={`url(#grad-typical-${sensor.location_id})`}
                      name="Typical"
                    />
                    <Area
                      type="monotone"
                      dataKey="actual"
                      stroke="#00E5C7"
                      strokeWidth={2}
                      fillOpacity={1}
                      fill={`url(#grad-actual-${sensor.location_id})`}
                      name="Actual"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>

              {/* Sparkline Legend */}
              <div className="flex items-center justify-between text-[10px] text-slate-500 pt-2 border-t border-white/5">
                <span className="flex items-center gap-1.5">
                  <span className="w-2 h-0.5 bg-teal-400 inline-block" /> Actual
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="w-2 h-0.5 bg-blue-400 border-b border-dashed inline-block" /> 8-week Typical
                </span>
              </div>
            </motion.div>
          );
        })}
      </div>
    </section>
  );
}
