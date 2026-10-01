import React from "react";
import { CalendarClock } from "lucide-react";

/**
 * The page title and one-line explanation. No hooks, so the server can put it
 * in the first HTML (app/plan/page.tsx) and the browser draws the same thing.
 */
export function PlanIntro({ children }: { children?: React.ReactNode }) {
  return (
    <div>
      <div className="flex items-center gap-2 text-teal-400 font-mono text-xs font-semibold uppercase tracking-wider mb-2">
        <CalendarClock className="w-4 h-4" aria-hidden />
        <span>Plan ahead</span>
      </div>
      <h1 className="text-3xl sm:text-4xl md:text-5xl font-bold tracking-tight text-white font-['Space_Grotesk',sans-serif]">
        Plan your next 36 hours
      </h1>
      <p className="mt-2 text-sm sm:text-base text-slate-300 max-w-2xl">
        Forecast foot traffic and the chance of rain, hour by hour, so you can pick your time in the CBD.
      </p>
      {/* Reserved line, so the page doesn't move when the sensor count arrives. */}
      <p className="mt-1 min-h-5 text-sm text-slate-400">{children}</p>
    </div>
  );
}
