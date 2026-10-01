"use client";

import React from "react";
import { Clock, Hourglass, Info } from "lucide-react";

import type { PlanResponse } from "@/lib/plan";
import { LIVE_FOR_MS } from "@/lib/freshness";
import { HOUR_MS } from "@/lib/plan-core";

import { PlanIntro } from "./PlanIntro";
import { formatAge, formatHourLong } from "./plan-utils";

/** The forecast is rebuilt once a day, so it is only late after a full day plus some slack. */
const FORECAST_LATE_MS = 26 * HOUR_MS;

interface PlanHeaderProps {
  plan: PlanResponse | null;
  /** Browser clock in ms; 0 until the page has hydrated. */
  now: number;
  /** The plan could not be loaded. */
  failed?: boolean;
}

export function PlanHeader({ plan, now, failed = false }: PlanHeaderProps) {
  const freshness = plan?.dataFreshness ?? null;
  const forecastAge = formatAge(freshness?.forecastGeneratedAt ?? null, now);
  const weatherAge = formatAge(freshness?.weatherFetchedAt ?? null, now);
  const age = (iso: string | null | undefined) => (iso && now > 0 ? now - Date.parse(iso) : null);
  const late =
    (age(freshness?.forecastGeneratedAt) ?? 0) > FORECAST_LATE_MS || (age(freshness?.weatherFetchedAt) ?? 0) > LIVE_FOR_MS;

  const ages = [forecastAge && `Forecast updated ${forecastAge}`, weatherAge && `weather ${weatherAge}`].filter(Boolean).join(" · ");

  return (
    <header>
      <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-4">
        <PlanIntro>
          {plan?.sensor === "cbd" && plan.sensorsUsed > 0 && `Based on ${plan.sensorsUsed} sensors.`}
          {plan && plan.sensor !== "cbd" && plan.sensor.name}
        </PlanIntro>

        <p
          role="status"
          className={`self-start lg:self-auto inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full border text-xs sm:text-sm font-medium backdrop-blur-md ${
            !ages
              ? "bg-slate-900/70 border-slate-600/40 text-slate-300"
              : late
                ? "bg-amber-950/60 border-amber-500/40 text-amber-300"
                : "bg-teal-950/60 border-teal-500/30 text-teal-300 shadow-[0_0_20px_rgba(0,229,199,0.15)]"
          }`}
        >
          {!ages ? (
            <Hourglass className="w-3.5 h-3.5 shrink-0" aria-hidden />
          ) : late ? (
            <Clock className="w-3.5 h-3.5 shrink-0" aria-hidden />
          ) : (
            <span className="relative flex h-2 w-2 shrink-0" aria-hidden>
              <span className="animate-ping motion-reduce:animate-none absolute inline-flex h-full w-full rounded-full bg-teal-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-teal-400" />
            </span>
          )}
          <span>{ages || (failed ? "Forecast unavailable" : "Loading the forecast…")}</span>
        </p>
      </div>
    </header>
  );
}

/** Shown when the forecast doesn't reach the end of the chosen window yet. */
export function ShortWindowNote({ plan }: { plan: PlanResponse }) {
  const lastHour = plan.hours.at(-1)?.hourLocal;
  if (plan.window.complete || !lastHour) return null;
  const runsTo = formatHourLong(new Date(Date.parse(lastHour) + HOUR_MS).toISOString());
  return (
    <p className="flex items-start gap-2 px-1 text-xs text-slate-400">
      <Info className="w-3.5 h-3.5 text-teal-400 shrink-0 mt-0.5" aria-hidden />
      <span>
        The forecast currently runs to <strong className="text-slate-200 font-semibold">{runsTo}</strong>, so this window
        is shorter than usual. It is extended once a day, early in the morning.
      </span>
    </p>
  );
}
