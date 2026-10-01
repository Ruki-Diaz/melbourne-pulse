"use client";

import React from "react";
import { Clock, Hourglass } from "lucide-react";

import type { Freshness } from "@/lib/freshness";

const STYLES = {
  live: "bg-teal-950/60 border-teal-500/30 text-teal-300 shadow-[0_0_20px_rgba(0,229,199,0.15)]",
  stale: "bg-amber-950/60 border-amber-500/40 text-amber-300",
  empty: "bg-slate-900/70 border-slate-600/40 text-slate-300",
} as const;

/** Pill showing whether the data is live, late (amber) or not there yet. */
export function FreshnessBadge({ freshness, className = "" }: { freshness: Freshness; className?: string }) {
  return (
    <span
      role="status"
      className={`inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full border text-xs sm:text-sm font-medium tracking-wide backdrop-blur-md ${STYLES[freshness.state]} ${className}`}
    >
      {freshness.state === "live" && (
        <span className="relative flex h-2 w-2" aria-hidden>
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-teal-400 opacity-75" />
          <span className="relative inline-flex rounded-full h-2 w-2 bg-teal-400" />
        </span>
      )}
      {freshness.state === "stale" && <Clock className="w-3.5 h-3.5" aria-hidden />}
      {freshness.state === "empty" && <Hourglass className="w-3.5 h-3.5" aria-hidden />}
      <span>{freshness.label}</span>
    </span>
  );
}
