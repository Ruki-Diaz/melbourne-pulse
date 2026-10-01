"use client";

import React from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Legend,
} from "recharts";
import { motion } from "framer-motion";
import { Sparkles, Brain, ArrowUpRight, CheckCircle2 } from "lucide-react";
import Link from "next/link";

export interface CBDHourlyForecastPoint {
  hourLabel: string;
  hourIso: string;
  predicted: number;
  typical: number;
}

interface CBDTomorrowForecastProps {
  data: CBDHourlyForecastPoint[];
  calloutText?: string;
}

export function CBDTomorrowForecast({ data, calloutText }: CBDTomorrowForecastProps) {
  // Compute fallback callout if not provided
  const peakCallout = React.useMemo(() => {
    if (calloutText) return calloutText;
    if (!data || data.length === 0) {
      return "Next 24h CBD prediction: Expected peak around 5pm with steady pedestrian density.";
    }

    let maxPred = -1;
    let peakPoint: CBDHourlyForecastPoint | null = null;
    data.forEach((p) => {
      if (p.predicted > maxPred) {
        maxPred = p.predicted;
        peakPoint = p;
      }
    });

    if (peakPoint) {
      const diffPct =
        (peakPoint as CBDHourlyForecastPoint).typical > 0
          ? (((peakPoint as CBDHourlyForecastPoint).predicted - (peakPoint as CBDHourlyForecastPoint).typical) /
              (peakPoint as CBDHourlyForecastPoint).typical) *
            100
          : 0;
      const sign = diffPct >= 0 ? "+" : "";
      return `Peak predicted at ${(peakPoint as CBDHourlyForecastPoint).hourLabel}, ${sign}${diffPct.toFixed(0)}% relative to the 8-week typical.`;
    }

    return "Pedestrian activity expected to track typical diurnal patterns.";
  }, [data, calloutText]);

  return (
    <section className="py-20 max-w-6xl mx-auto px-4 sm:px-6">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-8 gap-4">
        <div>
          <div className="flex items-center gap-2 text-purple-400 font-mono text-xs font-semibold uppercase tracking-wider mb-2">
            <Brain className="w-4 h-4" />
            <span>Machine Learning Forecast</span>
          </div>
          <h2 className="text-2xl sm:text-3xl font-bold text-white font-['Space_Grotesk',sans-serif]">
            Tomorrow, Predicted
          </h2>
          <p className="text-sm text-slate-400 mt-1 max-w-xl">
            CBD-wide hourly foot traffic for the next 24 hours produced by our LightGBM model versus the 8-week historical median.
          </p>
        </div>

        {/* Model Accuracy Badge */}
        <Link
          href="https://github.com/Ruki-Diaz/melbourne-pulse/blob/main/model/REPORT.md"
          target="_blank"
          rel="noreferrer"
          className="group inline-flex items-center gap-2 px-3.5 py-2 rounded-xl bg-purple-950/40 border border-purple-500/30 hover:border-purple-400/60 text-purple-300 text-xs font-mono transition-all backdrop-blur-md hover:shadow-[0_0_20px_rgba(124,58,237,0.25)]"
        >
          <CheckCircle2 className="w-4 h-4 text-purple-400 shrink-0" />
          <span className="truncate">
            10% more accurate than the 8-week typical · tested on 132,696 unseen sensor-hours
          </span>
          <ArrowUpRight className="w-3.5 h-3.5 text-purple-400 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-transform shrink-0" />
        </Link>
      </div>

      {/* Main Forecast Card */}
      <motion.div
        initial={{ opacity: 0, y: 25 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.5 }}
        className="p-6 sm:p-8 rounded-2xl bg-gradient-to-b from-[#0d1424]/90 to-[#070b14]/95 border border-white/10 backdrop-blur-xl shadow-2xl"
      >
        {/* Plain English AI / Calculated Callout Banner */}
        <div className="mb-6 p-4 rounded-xl bg-purple-500/10 border border-purple-500/25 flex items-center gap-3">
          <div className="p-2 rounded-lg bg-purple-500/20 text-purple-300 shrink-0">
            <Sparkles className="w-4 h-4" />
          </div>
          <p className="text-sm sm:text-base font-medium text-purple-200">{peakCallout}</p>
        </div>

        {/* Recharts 24h Area/Line Chart */}
        <div className="h-72 sm:h-80 w-full mt-4">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#ffffff0a" vertical={false} />
              <XAxis
                dataKey="hourLabel"
                stroke="#64748B"
                tick={{ fontSize: 11, fill: "#94A3B8" }}
                interval={2}
                axisLine={{ stroke: "#ffffff1a" }}
                tickLine={false}
              />
              <YAxis
                stroke="#64748B"
                tick={{ fontSize: 11, fill: "#94A3B8" }}
                axisLine={{ stroke: "#ffffff1a" }}
                tickLine={false}
                tickFormatter={(val) => `${(val / 1000).toFixed(0)}k`}
              />
              <Tooltip
                content={({ active, payload, label }) => {
                  if (active && payload && payload.length) {
                    const pred = payload.find((p) => p.dataKey === "predicted")?.value as number;
                    const typ = payload.find((p) => p.dataKey === "typical")?.value as number;
                    const diff = typ > 0 ? ((pred - typ) / typ) * 100 : 0;
                    return (
                      <div className="rounded-xl bg-[#05080D]/95 border border-purple-500/30 p-3.5 text-xs backdrop-blur-xl shadow-xl space-y-1.5 font-mono">
                        <p className="font-bold text-slate-100 font-sans text-sm mb-1">{label}</p>
                        <div className="flex items-center justify-between gap-4 text-purple-300">
                          <span className="flex items-center gap-1.5">
                            <span className="w-2 h-2 rounded-full bg-purple-400" />
                            LightGBM Forecast:
                          </span>
                          <span className="font-bold text-white">{pred?.toLocaleString()}</span>
                        </div>
                        <div className="flex items-center justify-between gap-4 text-blue-300">
                          <span className="flex items-center gap-1.5">
                            <span className="w-2 h-2 rounded-full bg-blue-400" />
                            8-Week Typical:
                          </span>
                          <span className="font-bold text-white">{typ?.toLocaleString()}</span>
                        </div>
                        <div className="pt-1.5 border-t border-white/10 text-[11px] text-slate-300 flex justify-between">
                          <span>Model vs Typical:</span>
                          <span className={diff >= 0 ? "text-teal-400 font-bold" : "text-blue-400 font-bold"}>
                            {diff >= 0 ? `+${diff.toFixed(1)}%` : `${diff.toFixed(1)}%`}
                          </span>
                        </div>
                      </div>
                    );
                  }
                  return null;
                }}
              />
              <Legend
                verticalAlign="top"
                align="right"
                wrapperStyle={{ paddingBottom: "12px", fontSize: "12px" }}
                formatter={(value) => <span className="text-slate-300 font-medium">{value}</span>}
              />
              <Line
                type="monotone"
                dataKey="typical"
                name="8-Week Typical"
                stroke="#3B82F6"
                strokeWidth={2}
                strokeDasharray="4 4"
                dot={false}
                activeDot={{ r: 4, fill: "#3B82F6" }}
              />
              <Line
                type="monotone"
                dataKey="predicted"
                name="LightGBM Predicted"
                stroke="#A855F7"
                strokeWidth={2.5}
                dot={false}
                activeDot={{ r: 5, fill: "#A855F7", stroke: "#ffffff", strokeWidth: 2 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </motion.div>
    </section>
  );
}
