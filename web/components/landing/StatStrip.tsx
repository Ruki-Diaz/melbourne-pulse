"use client";

import React, { useEffect, useRef, useState } from "react";
import { Users, Car, Flame, TrendingUp } from "lucide-react";
import { motion, useInView, useReducedMotion } from "framer-motion";

import { melbourneHourLabel } from "@/lib/freshness";
import { useFreshness } from "@/lib/useFreshness";

interface StatStripProps {
  /** null = no data yet: the card shows an empty state, never a made-up number. */
  totalPedestrians: number | null;
  /** Sensors behind that total: those that have finished reporting the hour. */
  sensorCount: number;
  /** Sensors seen in the last 24 hours. More than sensorCount means some are still reporting. */
  sensorsActive: number;
  pctParkingFree: number | null;
  busiestSpot: {
    name: string;
    count: number;
  } | null;
  /** The hour the pedestrian counts belong to (ISO). */
  hourIso: string | null;
  updatedAt: string | null;
  renderedAt: string;
}

const WAITING = "Waiting for the next update";

function Empty() {
  return <span className="text-slate-500" aria-label="No data">—</span>;
}

function AnimatedCounter({ value, suffix = "", duration = 1.2 }: { value: number; suffix?: string; duration?: number }) {
  const ref = useRef<HTMLSpanElement | null>(null);
  const isInView = useInView(ref, { once: true, margin: "-20px" });
  const shouldReduceMotion = useReducedMotion();
  const [displayValue, setDisplayValue] = useState(0);

  useEffect(() => {
    if (shouldReduceMotion) {
      return;
    }
    if (!isInView) return;

    const start = 0;
    const startTime = performance.now();
    let animationFrame: number;

    const frame = (now: number) => {
      const progress = Math.min((now - startTime) / (duration * 1000), 1);
      // easeOutExpo
      const eased = progress === 1 ? 1 : 1 - Math.pow(2, -10 * progress);
      const current = Math.round(start + (value - start) * eased);
      setDisplayValue(current);

      if (progress < 1) {
        animationFrame = requestAnimationFrame(frame);
      } else {
        setDisplayValue(value);
      }
    };

    animationFrame = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(animationFrame);
  }, [isInView, value, duration, shouldReduceMotion]);

  const finalValue = shouldReduceMotion ? value : isInView ? displayValue : 0;

  return (
    <span ref={ref} className="tabular-nums font-bold tracking-tight">
      {finalValue.toLocaleString()}
      {suffix}
    </span>
  );
}

export function StatStrip({
  totalPedestrians,
  sensorCount,
  sensorsActive,
  pctParkingFree,
  busiestSpot,
  hourIso,
  updatedAt,
  renderedAt,
}: StatStripProps) {
  const live = useFreshness(updatedAt, renderedAt).state === "live";
  const hour = hourIso ? melbourneHourLabel(hourIso) : null;
  return (
    <div className="relative z-20 -mt-10 md:-mt-14 max-w-6xl mx-auto px-4 sm:px-6">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Card 1: Pedestrian Volume */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, delay: 0.1 }}
          className="relative group p-5 sm:p-6 rounded-2xl bg-[#0d1424]/80 backdrop-blur-xl border border-white/10 hover:border-teal-500/40 transition-all duration-300 shadow-[0_8px_30px_rgba(0,0,0,0.4)] hover:shadow-[0_8px_30px_rgba(0,229,199,0.15)]"
        >
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs uppercase tracking-wider font-semibold text-slate-400">
              {live ? "Pedestrian counts this hour" : totalPedestrians === null ? "Pedestrian counts" : "Pedestrian counts (last update)"}
            </span>
            <div className="p-2 rounded-lg bg-teal-500/10 text-teal-400 border border-teal-500/20">
              <Users className="w-4 h-4" />
            </div>
          </div>
          <div className="text-3xl sm:text-4xl text-white font-['Space_Grotesk',sans-serif] mb-1">
            {totalPedestrians === null ? <Empty /> : <AnimatedCounter value={totalPedestrians} />}
          </div>
          <p className="text-xs text-slate-400 flex items-center gap-1.5">
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-teal-400" />
            {totalPedestrians === null || !hour ? WAITING : `Across ${sensorCount < sensorsActive * 0.8 ? `${sensorCount} of ${sensorsActive} sensors so far` : `${sensorCount} sensors`}, in the hour from ${hour}`}
          </p>
        </motion.div>

        {/* Card 2: Parking Availability */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, delay: 0.2 }}
          className="relative group p-5 sm:p-6 rounded-2xl bg-[#0d1424]/80 backdrop-blur-xl border border-white/10 hover:border-emerald-500/40 transition-all duration-300 shadow-[0_8px_30px_rgba(0,0,0,0.4)] hover:shadow-[0_8px_30px_rgba(16,185,129,0.15)]"
        >
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs uppercase tracking-wider font-semibold text-slate-400">
              Street Parking Free
            </span>
            <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <Car className="w-4 h-4" />
            </div>
          </div>
          <div className="text-3xl sm:text-4xl text-white font-['Space_Grotesk',sans-serif] mb-1">
            {pctParkingFree === null ? <Empty /> : <AnimatedCounter value={pctParkingFree} suffix="%" />}
          </div>
          <p className="text-xs text-slate-400 flex items-center gap-1.5">
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-emerald-400" />
            {pctParkingFree === null ? WAITING : "Bays whose sensor reported in the last 24 h"}
          </p>
        </motion.div>

        {/* Card 3: Busiest Location */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, delay: 0.3 }}
          className="relative group p-5 sm:p-6 rounded-2xl bg-[#0d1424]/80 backdrop-blur-xl border border-white/10 hover:border-amber-500/40 transition-all duration-300 shadow-[0_8px_30px_rgba(0,0,0,0.4)] hover:shadow-[0_8px_30px_rgba(245,158,11,0.15)]"
        >
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs uppercase tracking-wider font-semibold text-slate-400">
              {live ? "Busiest spot right now" : busiestSpot === null ? "Busiest spot" : "Busiest spot (last update)"}
            </span>
            <div className="p-2 rounded-lg bg-amber-500/10 text-amber-400 border border-amber-500/20">
              <Flame className="w-4 h-4" />
            </div>
          </div>
          <div className="text-xl sm:text-2xl font-bold text-white tracking-tight truncate mb-1">
            {busiestSpot ? busiestSpot.name : <Empty />}
          </div>
          <div className="text-xs text-amber-400 font-mono flex items-center gap-1.5">
            <TrendingUp className="w-3.5 h-3.5" />
            {busiestSpot ? (
              <>
                <AnimatedCounter value={busiestSpot.count} /> pedestrian counts/hour
              </>
            ) : (
              WAITING
            )}
          </div>
        </motion.div>
      </div>
    </div>
  );
}
