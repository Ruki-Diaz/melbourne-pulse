"use client";

import React from "react";
import Link from "next/link";
import { ArrowLeft, AlertTriangle, Sparkles, Layers } from "lucide-react";

import { FreshnessBadge } from "@/components/ui/FreshnessBadge";
import { FEED_ANOMALY_TEXT } from "@/lib/feed-anomaly";
import { useFreshness } from "@/lib/useFreshness";

interface MapTopBarProps {
  summaryText?: string;
  /** The pipeline flagged this hour as a fault in the city's feed. */
  feedAnomaly?: boolean;
  updatedAt: string | null;
  renderedAt: string;
  parkingVisible: boolean;
  onToggleParking: () => void;
  parkingStats: { free: number; total: number; pct: number };
}

export function MapTopBar({
  summaryText,
  feedAnomaly = false,
  updatedAt,
  renderedAt,
  parkingVisible,
  onToggleParking,
  parkingStats,
}: MapTopBarProps) {
  const freshness = useFreshness(updatedAt, renderedAt);
  return (
    <div className="absolute top-4 left-4 right-4 z-[1000] pointer-events-none flex flex-col gap-2 max-w-5xl mx-auto">
      {/* Amber notice once data is 2 h old (same rule as the home page and OG image) */}
      {freshness.state !== "live" && (
        <div className="pointer-events-auto flex items-center gap-2 px-4 py-2.5 rounded-xl bg-amber-500/20 border border-amber-500/40 text-amber-200 text-xs sm:text-sm backdrop-blur-xl shadow-lg">
          <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
          <span>
            {freshness.state === "stale"
              ? `${freshness.label}. The hourly update is running late, so these counts aren't live.`
              : "Waiting for the next update."}
          </span>
        </div>
      )}

      {/* The hour is flagged: say so on every screen size (the summary line below is desktop only) */}
      {feedAnomaly && (
        <div
          role="status"
          className="pointer-events-auto flex items-center gap-2 px-4 py-2.5 rounded-xl bg-amber-500/20 border border-amber-500/40 text-amber-200 text-xs sm:text-sm backdrop-blur-xl shadow-lg"
        >
          <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
          <span>{FEED_ANOMALY_TEXT} Comparisons with typical are paused.</span>
        </div>
      )}

      {/* Main Glass Control Bar */}
      <div className="pointer-events-auto flex flex-wrap items-center justify-between gap-3 p-3 sm:p-4 rounded-2xl bg-[#05080D]/90 border border-white/10 backdrop-blur-2xl shadow-2xl">
        {/* Left: Brand & Back */}
        <div className="flex items-center gap-3">
          <Link
            href="/"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-white/5 hover:bg-white/10 text-slate-300 hover:text-white text-xs font-medium border border-white/10 transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Home</span>
          </Link>

          <FreshnessBadge freshness={freshness} className="hidden sm:inline-flex !text-xs !py-1" />
        </div>

        {/* Center: Live Summary Sentence (the banner above already carries it while the hour is flagged) */}
        {!feedAnomaly && (
          <div className="hidden lg:flex items-center gap-2 text-xs text-slate-300 max-w-lg truncate">
            <Sparkles className="w-3.5 h-3.5 text-teal-400 shrink-0" />
            <span className="truncate">{summaryText || "Waiting for the next update."}</span>
          </div>
        )}

        {/* Right: Parking Layer Toggle */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onToggleParking}
            className={`flex items-center gap-2 px-3.5 py-1.5 rounded-xl text-xs font-semibold transition-all border ${
              parkingVisible
                ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/40 shadow-[0_0_15px_rgba(16,185,129,0.2)]"
                : "bg-white/5 text-slate-400 border-white/10 hover:text-slate-200"
            }`}
          >
            <Layers className="w-3.5 h-3.5" />
            <span>
              {parkingStats.total > 0 ? `Parking (${parkingStats.free} free / ${parkingStats.pct}%)` : "Parking (no data yet)"}
            </span>
            <span
              className={`w-2 h-2 rounded-full ${
                parkingVisible ? "bg-emerald-400" : "bg-slate-600"
              }`}
            />
          </button>
        </div>
      </div>
    </div>
  );
}
