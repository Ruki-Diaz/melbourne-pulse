"use client";

import React from "react";
import Link from "next/link";
import { ArrowLeft, AlertTriangle, Sparkles, Layers } from "lucide-react";

interface MapTopBarProps {
  summaryText?: string;
  updatedMinutesAgo: number;
  isStale: boolean;
  parkingVisible: boolean;
  onToggleParking: () => void;
  parkingStats: { free: number; total: number; pct: number };
}

export function MapTopBar({
  summaryText,
  updatedMinutesAgo,
  isStale,
  parkingVisible,
  onToggleParking,
  parkingStats,
}: MapTopBarProps) {
  return (
    <div className="absolute top-4 left-4 right-4 z-[1000] pointer-events-none flex flex-col gap-2 max-w-5xl mx-auto">
      {/* Amber warning if data > 3 hours old */}
      {isStale && (
        <div className="pointer-events-auto flex items-center gap-2 px-4 py-2.5 rounded-xl bg-amber-500/20 border border-amber-500/40 text-amber-200 text-xs sm:text-sm backdrop-blur-xl shadow-lg">
          <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
          <span>
            <strong>Data Delayed:</strong> Ingest pipeline is running behind; data shown was updated {updatedMinutesAgo} minutes ago.
          </span>
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

          <div className="hidden sm:flex items-center gap-2">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-teal-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-teal-400"></span>
            </span>
            <span className="text-xs font-mono text-teal-400 font-semibold">
              Updated {updatedMinutesAgo}m ago
            </span>
          </div>
        </div>

        {/* Center: Live Summary Sentence */}
        <div className="hidden lg:flex items-center gap-2 text-xs text-slate-300 max-w-lg truncate">
          <Sparkles className="w-3.5 h-3.5 text-teal-400 shrink-0" />
          <span className="truncate">{summaryText || "Live Melbourne CBD pedestrian and parking sensor telemetry."}</span>
        </div>

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
            <span>Parking ({parkingStats.free} free / {parkingStats.pct}%)</span>
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
