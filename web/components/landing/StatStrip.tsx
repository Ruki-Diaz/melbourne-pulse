"use client";

import React, { useEffect, useRef, useState } from "react";
import { Users, Car, Flame, TrendingUp } from "lucide-react";
import { motion, useInView, useReducedMotion } from "framer-motion";

interface StatStripProps {
  totalPedestrians: number;
  pctParkingFree: number;
  busiestSpot: {
    name: string;
    count: number;
  } | null;
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

export function StatStrip({ totalPedestrians, pctParkingFree, busiestSpot }: StatStripProps) {
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
              CBD Pedestrians Now
            </span>
            <div className="p-2 rounded-lg bg-teal-500/10 text-teal-400 border border-teal-500/20">
              <Users className="w-4 h-4" />
            </div>
          </div>
          <div className="text-3xl sm:text-4xl text-white font-['Space_Grotesk',sans-serif] mb-1">
            <AnimatedCounter value={totalPedestrians} />
          </div>
          <p className="text-xs text-slate-400 flex items-center gap-1.5">
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-teal-400" />
            Live pedestrians walking in the CBD this hour
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
            <AnimatedCounter value={pctParkingFree} suffix="%" />
          </div>
          <p className="text-xs text-slate-400 flex items-center gap-1.5">
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-emerald-400" />
            Non-stale in-ground sensors only
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
              Busiest Spot Right Now
            </span>
            <div className="p-2 rounded-lg bg-amber-500/10 text-amber-400 border border-amber-500/20">
              <Flame className="w-4 h-4" />
            </div>
          </div>
          <div className="text-xl sm:text-2xl font-bold text-white tracking-tight truncate mb-1">
            {busiestSpot ? busiestSpot.name : "Melbourne Central"}
          </div>
          <div className="text-xs text-amber-400 font-mono flex items-center gap-1.5">
            <TrendingUp className="w-3.5 h-3.5" />
            {busiestSpot ? (
              <>
                <AnimatedCounter value={busiestSpot.count} /> people/hour
              </>
            ) : (
              "Calculating peak..."
            )}
          </div>
        </motion.div>
      </div>
    </div>
  );
}
