"use client";

import React from "react";
import { Ban, Clock, CloudRain, Sparkles, ThumbsUp } from "lucide-react";

import {
  ACTIVE_FROM_HOUR,
  ACTIVE_TO_HOUR,
  BLOCK_HOURS,
  type Recommendation,
  type Recommendations,
  type RecommendationSet,
} from "@/lib/plan-core";

import { CARD, clockHour, formatBlock, formatDelta, formatRange, rainChip } from "./plan-utils";

interface AnswerCardProps {
  recommendations: RecommendationSet;
  hoursConsidered: Recommendations["hoursConsidered"];
  goalLabel: string;
  /** Number of forecast hours in the window, to explain an empty answer. */
  hoursInWindow: number;
  isLoading?: boolean;
}

function RainChip({ maxPrecipProb }: { maxPrecipProb: number | null }) {
  const chip = rainChip(maxPrecipProb);
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold border whitespace-nowrap ${chip.chip}`}>
      <CloudRain className="w-3 h-3" aria-hidden />
      <span>{chip.text}</span>
    </span>
  );
}

function Alternative({ kind, block }: { kind: "also" | "avoid"; block: Recommendation }) {
  const avoid = kind === "avoid";
  const Icon = avoid ? Ban : ThumbsUp;
  return (
    <div
      className={`flex items-start gap-3 rounded-xl p-3.5 border ${
        avoid ? "bg-rose-950/20 border-rose-500/25" : "bg-slate-900/50 border-white/10"
      }`}
    >
      <Icon className={`w-4 h-4 shrink-0 mt-0.5 ${avoid ? "text-rose-400" : "text-teal-400"}`} aria-hidden />
      <div className="space-y-1.5 min-w-0">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <span className={`text-xs font-mono uppercase tracking-wider font-semibold ${avoid ? "text-rose-300" : "text-teal-300"}`}>
            {avoid ? "Avoid" : "Also good"}
          </span>
          <span className="text-sm font-semibold text-white">{formatBlock(block.start, block.end)}</span>
          <RainChip maxPrecipProb={block.maxPrecipProb} />
        </div>
        <p className="text-xs sm:text-sm text-slate-300 leading-relaxed">{block.reason}</p>
      </div>
    </div>
  );
}

export function AnswerCard({ recommendations, hoursConsidered, goalLabel, hoursInWindow, isLoading = false }: AnswerCardProps) {
  const { best, secondBest, avoid } = recommendations;

  if (!best) {
    return (
      <section aria-label="Recommendation" className={`${CARD} p-6 sm:p-8 text-center`}>
        <Clock className="w-8 h-8 text-slate-400 mx-auto mb-2" aria-hidden />
        <h2 className="text-base font-semibold text-white font-['Space_Grotesk',sans-serif]">
          {hoursInWindow === 0 ? "No forecast hours in this window yet" : "Not enough hours to recommend a time"}
        </h2>
        <p className="text-sm text-slate-300 mt-1 max-w-md mx-auto">
          Try a different window: &ldquo;Next 12h&rdquo; and &ldquo;Next 36h&rdquo; start from the coming hour.
        </p>
      </section>
    );
  }

  const delta = formatDelta(best.deltaPct, best.start);

  return (
    <div className="space-y-2">
      <section
        aria-label={`Recommendation for ${goalLabel}`}
        aria-busy={isLoading}
        className={`relative overflow-hidden rounded-2xl border border-teal-500/30 bg-gradient-to-br from-[#0D1829]/90 via-[#0A111F]/95 to-[#05080D]/90 p-5 sm:p-7 backdrop-blur-xl shadow-[0_0_30px_rgba(0,229,199,0.08)] transition-opacity duration-200 ${
          isLoading ? "opacity-60" : "opacity-100"
        }`}
      >
        <div className="absolute top-0 right-0 -mt-8 -mr-8 w-64 h-64 bg-teal-500/10 rounded-full blur-3xl pointer-events-none" aria-hidden />

        <p className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-mono uppercase tracking-wider font-semibold bg-teal-500/15 text-teal-300 border border-teal-500/40 mb-3">
          <Sparkles className="w-3 h-3" aria-hidden />
          <span>Best time for: {goalLabel}</span>
        </p>

        <div className="space-y-2.5">
          <h2 className="text-3xl sm:text-4xl md:text-5xl font-bold tracking-tight text-teal-300 font-['Space_Grotesk',sans-serif]">
            {formatBlock(best.start, best.end)}
          </h2>
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
            {delta && <span className="text-sm sm:text-base font-medium text-slate-200">{delta}</span>}
            <RainChip maxPrecipProb={best.maxPrecipProb} />
          </div>
          <p className="text-sm sm:text-base text-slate-300 leading-relaxed max-w-3xl">{best.reason}</p>
        </div>

        {(secondBest || avoid) && (
          <div className="relative mt-5 pt-5 border-t border-white/10 grid grid-cols-1 md:grid-cols-2 gap-3">
            {secondBest && <Alternative kind="also" block={secondBest} />}
            {avoid && <Alternative kind="avoid" block={avoid} />}
          </div>
        )}
      </section>

      {hoursConsidered && (
        <p className="px-1 text-xs text-slate-400">
          Considering {formatRange(hoursConsidered.from, hoursConsidered.to)}
          {hoursConsidered.daytimeOnly && `, between ${clockHour(ACTIVE_FROM_HOUR)} and ${clockHour(ACTIVE_TO_HOUR)}`}
          {`, in ${BLOCK_HOURS}-hour blocks.`}
        </p>
      )}
    </div>
  );
}
