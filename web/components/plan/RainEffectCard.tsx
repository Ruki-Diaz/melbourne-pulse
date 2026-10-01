"use client";

import React from "react";
import { ChevronRight, CloudRain, Info } from "lucide-react";

import type { RainEffect } from "@/lib/plan";

import { CARD, FOCUS_RING, count, signedPct } from "./plan-utils";

interface RainEffectCardProps {
  rainEffect: RainEffect | null;
  /** The place the page is showing: "Whole CBD" or a sensor's name. */
  placeName: string;
  onOpenEvidence: () => void;
}

export function RainEffectCard({ rainEffect, placeName, onOpenEvidence }: RainEffectCardProps) {
  if (!rainEffect) return null;

  const cbdWide = rainEffect.scope === "cbd";
  const size = `${Math.abs(rainEffect.value)}%`;
  const direction = rainEffect.value < 0 ? "fewer" : "more";
  const interval =
    rainEffect.ciLow !== null && rainEffect.ciHigh !== null
      ? `95% interval ${signedPct(rainEffect.ciLow)} to ${signedPct(rainEffect.ciHigh)}, from `
      : "from ";

  return (
    <section aria-labelledby="rain-effect-title" className={`${CARD} p-5 sm:p-6 space-y-4`}>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex items-center justify-center w-9 h-9 rounded-xl bg-sky-500/10 border border-sky-500/30 text-sky-400 shrink-0">
            <CloudRain className="w-5 h-5" aria-hidden />
          </div>
          <div>
            <h2 id="rain-effect-title" className="text-base sm:text-lg font-bold text-white font-['Space_Grotesk',sans-serif]">
              How rain changes foot traffic {cbdWide ? "in the CBD" : "here"}
            </h2>
            <p className="text-xs text-slate-400">
              Measured over the last 12 months · {cbdWide ? "all CBD sensors" : placeName}
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={onOpenEvidence}
          aria-controls="evidence"
          className={`inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-semibold bg-white/5 hover:bg-white/10 text-teal-300 border border-teal-500/30 hover:border-teal-400 transition-colors self-start sm:self-center ${FOCUS_RING}`}
        >
          <span>See how we know</span>
          <ChevronRight className="w-3.5 h-3.5" aria-hidden />
        </button>
      </div>

      <p className="text-sm sm:text-base text-slate-200 leading-relaxed">
        {rainEffect.value === 0 ? (
          <>A wet hour makes <strong className="text-sky-300 font-semibold">no measurable difference</strong> to pedestrian counts</>
        ) : (
          <>
            A wet hour usually means{" "}
            <strong className="text-sky-300 font-semibold">
              {size} {direction} pedestrian counts
            </strong>
          </>
        )}{" "}
        {cbdWide ? "across the CBD" : "here"}{" "}
        <span className="text-slate-400">
          ({interval}
          {count(rainEffect.nWetHours)} wet hours)
        </span>
        .
      </p>

      {rainEffect.usedFallback && (
        <p className="flex items-start gap-2 text-xs sm:text-sm text-amber-200 bg-amber-950/40 border border-amber-500/30 rounded-lg p-2.5">
          <Info className="w-4 h-4 shrink-0 text-amber-400 mt-0.5" aria-hidden />
          <span>There isn&rsquo;t a reliable estimate for {placeName} on its own yet, so this is the CBD-wide effect.</span>
        </p>
      )}
      {!rainEffect.reliable && (
        <p className="flex items-start gap-2 text-xs sm:text-sm text-amber-200 bg-amber-950/40 border border-amber-500/30 rounded-lg p-2.5">
          <Info className="w-4 h-4 shrink-0 text-amber-400 mt-0.5" aria-hidden />
          <span>This estimate is uncertain: there are too few wet hours, or the interval includes zero.</span>
        </p>
      )}

      <p className="text-xs text-slate-400 flex items-start gap-1.5">
        <Info className="w-3.5 h-3.5 shrink-0 mt-0.5" aria-hidden />
        <span>
          The forecast above already takes the weather forecast into account. This figure only explains why; it is
          never applied to the forecast.
        </span>
      </p>
    </section>
  );
}
