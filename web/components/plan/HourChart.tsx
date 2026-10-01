"use client";

import React from "react";
import {
  Area,
  Bar,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceArea,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { CloudRain, Thermometer, Wind } from "lucide-react";

import type { PlanHour, Recommendation } from "@/lib/plan-core";

import { CARD, FOCUS_RING, axisHour, count, formatHourLong, signedPct, weatherLabel } from "./plan-utils";

interface HourChartProps {
  hours: PlanHour[];
  bestBlock: Recommendation | null;
  avoidBlock: Recommendation | null;
  placeName: string;
  isLoading?: boolean;
}

function HourTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: PlanHour }> }) {
  if (!active || !payload?.length) return null;
  const hour = payload[0].payload;
  const weather = weatherLabel(hour.weatherCode);
  const deltaColor =
    hour.deltaPct === null ? "" : hour.deltaPct >= 5 ? "text-teal-300" : hour.deltaPct <= -5 ? "text-blue-300" : "text-slate-200";

  return (
    <div className="bg-[#0A0F1A]/95 backdrop-blur-xl border border-white/15 rounded-xl p-3.5 shadow-2xl text-xs space-y-2 min-w-[220px]">
      <div className="border-b border-white/10 pb-1.5 flex items-center justify-between gap-3">
        <span className="font-semibold text-white">{formatHourLong(hour.hourLocal)}</span>
        {weather && <span className="text-[11px] text-teal-300">{weather}</span>}
      </div>
      <dl className="space-y-1.5">
        <div className="flex items-center justify-between gap-4">
          <dt className="text-slate-300">Forecast pedestrian counts</dt>
          <dd className="font-mono font-bold text-white text-sm">{count(hour.forecastCount)}</dd>
        </div>
        {hour.typicalCount !== null && (
          <div className="flex items-center justify-between gap-4">
            <dt className="text-slate-300">Typical</dt>
            <dd className="font-mono text-slate-200">{count(hour.typicalCount)}</dd>
          </div>
        )}
        {hour.deltaPct !== null && (
          <div className="flex items-center justify-between gap-4">
            <dt className="text-slate-300">Against typical</dt>
            <dd className={`font-mono font-semibold ${deltaColor}`}>{signedPct(hour.deltaPct)}</dd>
          </div>
        )}
      </dl>
      <div className="border-t border-white/10 pt-1.5 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-slate-200">
        <span className="flex items-center gap-1">
          <CloudRain className="w-3.5 h-3.5 text-sky-400" aria-hidden />
          {hour.precipProb === null && hour.precipMm === null
            ? "No rain forecast"
            : [hour.precipProb !== null && `${Math.round(hour.precipProb)}% chance`, hour.precipMm !== null && `${hour.precipMm} mm`]
                .filter(Boolean)
                .join(", ")}
        </span>
        {hour.tempC !== null && (
          <span className="flex items-center gap-1">
            <Thermometer className="w-3.5 h-3.5 text-amber-400" aria-hidden />
            {Math.round(hour.tempC)}°C
          </span>
        )}
        {hour.windKmh !== null && (
          <span className="flex items-center gap-1">
            <Wind className="w-3.5 h-3.5 text-slate-300" aria-hidden />
            {Math.round(hour.windKmh)} km/h
          </span>
        )}
      </div>
    </div>
  );
}

/** First and last chart categories a block covers, or null if it lies outside the hours shown. */
function span(hours: PlanHour[], block: Recommendation | null): [string, string] | null {
  if (!block) return null;
  const start = Date.parse(block.start);
  const end = Date.parse(block.end);
  const inside = hours.filter((h) => {
    const t = Date.parse(h.hourLocal);
    return t >= start && t < end;
  });
  return inside.length ? [inside[0].hourLocal, inside[inside.length - 1].hourLocal] : null;
}

export function HourChart({ hours, bestBlock, avoidBlock, placeName, isLoading = false }: HourChartProps) {
  if (hours.length === 0) {
    return (
      <section aria-label="Hour-by-hour forecast" className={`${CARD} p-8 text-center text-sm text-slate-300`}>
        There are no forecast hours in this window yet.
      </section>
    );
  }

  const best = span(hours, bestBlock);
  const avoid = span(hours, avoidBlock);
  const hasTypical = hours.some((h) => h.typicalCount !== null);
  const hasRain = hours.some((h) => h.precipProb !== null);
  const first = hours[0].hourLocal;
  // About 18 px a bar is the least that stays readable; narrower screens scroll sideways.
  const minWidth = Math.max(320, hours.length * 18 + 90);

  return (
    <section
      aria-labelledby="hour-chart-title"
      aria-busy={isLoading}
      className={`${CARD} p-4 sm:p-6 space-y-4 transition-opacity duration-200 ${isLoading ? "opacity-60" : "opacity-100"}`}
    >
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 id="hour-chart-title" className="text-base sm:text-lg font-bold text-white font-['Space_Grotesk',sans-serif]">
            Hour by hour · {placeName}
          </h2>
          <p className="text-xs text-slate-400">Forecast pedestrian counts against the 8-week typical, with the chance of rain.</p>
        </div>
        <ul className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-200" aria-label="Chart legend">
          <li className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-sm bg-teal-400" aria-hidden />
            Forecast
          </li>
          {hasTypical && (
            <li className="flex items-center gap-1.5">
              <span className="w-4 h-0.5 bg-[#7AA2FF]" aria-hidden />
              Typical
            </li>
          )}
          {hasRain && (
            <li className="flex items-center gap-1.5">
              <span className="w-4 h-0 border-t-2 border-dashed border-sky-400" aria-hidden />
              Chance of rain
            </li>
          )}
          {best && (
            <li className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-sm bg-teal-400/30 border border-teal-400" aria-hidden />
              Best
            </li>
          )}
          {avoid && (
            <li className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-sm bg-rose-500/30 border border-rose-400" aria-hidden />
              Avoid
            </li>
          )}
        </ul>
      </div>

      <div
        className={`w-full overflow-x-auto rounded-lg ${FOCUS_RING}`}
        tabIndex={0}
        role="group"
        aria-label="Forecast chart. The same figures are in the table below."
      >
        <div className="h-72 sm:h-80" style={{ minWidth }}>
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={hours} margin={{ top: 12, right: 0, left: -8, bottom: 0 }} barCategoryGap="18%">
              <defs>
                <linearGradient id="planForecastBar" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#00E5C7" stopOpacity={0.95} />
                  <stop offset="100%" stopColor="#00E5C7" stopOpacity={0.4} />
                </linearGradient>
                <linearGradient id="planRainArea" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#38BDF8" stopOpacity={0.22} />
                  <stop offset="100%" stopColor="#38BDF8" stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" vertical={false} />
              <XAxis
                dataKey="hourLocal"
                tickFormatter={(value: string) => axisHour(value, value === first)}
                stroke="#475569"
                tick={{ fill: "#CBD5E1", fontSize: 11 }}
                interval={hours.length > 24 ? 2 : hours.length > 12 ? 1 : 0}
                tickMargin={6}
              />
              <YAxis
                yAxisId="count"
                stroke="#475569"
                tick={{ fill: "#CBD5E1", fontSize: 11 }}
                width={48}
                tickFormatter={(value: number) => (value >= 1000 ? `${Math.round(value / 100) / 10}k` : String(value))}
              />
              <YAxis
                yAxisId="rain"
                orientation="right"
                domain={[0, 100]}
                ticks={[0, 50, 100]}
                stroke="#475569"
                tick={{ fill: "#7DD3FC", fontSize: 11 }}
                width={hasRain ? 40 : 0}
                hide={!hasRain}
                tickFormatter={(value: number) => `${value}%`}
              />
              <Tooltip content={<HourTooltip />} cursor={{ fill: "rgba(255,255,255,0.05)" }} />

              {best && (
                <ReferenceArea yAxisId="count" x1={best[0]} x2={best[1]} fill="rgba(0,229,199,0.14)" stroke="rgba(0,229,199,0.6)" strokeDasharray="3 3" />
              )}
              {avoid && (
                <ReferenceArea yAxisId="count" x1={avoid[0]} x2={avoid[1]} fill="rgba(244,63,94,0.12)" stroke="rgba(244,63,94,0.55)" strokeDasharray="3 3" />
              )}

              {hasRain && (
                <Area
                  yAxisId="rain"
                  type="monotone"
                  dataKey="precipProb"
                  stroke="#38BDF8"
                  strokeWidth={1.5}
                  strokeDasharray="4 3"
                  fill="url(#planRainArea)"
                  dot={false}
                  activeDot={false}
                  isAnimationActive={false}
                />
              )}
              <Bar yAxisId="count" dataKey="forecastCount" fill="url(#planForecastBar)" radius={[3, 3, 0, 0]} maxBarSize={26} isAnimationActive={false} />
              {hasTypical && (
                <Line
                  yAxisId="count"
                  type="monotone"
                  dataKey="typicalCount"
                  stroke="#7AA2FF"
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 4, fill: "#ffffff", stroke: "#7AA2FF", strokeWidth: 2 }}
                  isAnimationActive={false}
                />
              )}
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>

      {minWidth > 340 && <p className="sm:hidden text-xs text-slate-400">Swipe the chart sideways to see later hours.</p>}

      <details className="group text-sm">
        <summary className={`inline-flex cursor-pointer items-center gap-1 rounded-md text-xs font-semibold text-teal-300 hover:text-teal-200 ${FOCUS_RING}`}>
          <span className="group-open:hidden">Show these hours as a table</span>
          <span className="hidden group-open:inline">Hide the table</span>
        </summary>
        <div className={`mt-3 overflow-x-auto rounded-lg border border-white/10 ${FOCUS_RING}`} tabIndex={0} role="group" aria-label="Forecast table">
          <table className="w-full text-xs text-left">
            <caption className="sr-only">Hour-by-hour forecast for {placeName}</caption>
            <thead className="bg-white/5 text-slate-300 font-mono">
              <tr>
                <th scope="col" className="px-3 py-2 font-semibold">Hour</th>
                <th scope="col" className="px-3 py-2 font-semibold text-right">Forecast</th>
                <th scope="col" className="px-3 py-2 font-semibold text-right">Typical</th>
                <th scope="col" className="px-3 py-2 font-semibold text-right">Against typical</th>
                <th scope="col" className="px-3 py-2 font-semibold text-right">Chance of rain</th>
                <th scope="col" className="px-3 py-2 font-semibold text-right">Rain</th>
                <th scope="col" className="px-3 py-2 font-semibold text-right">Temp</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5 font-mono text-slate-200">
              {hours.map((h) => (
                <tr key={h.hourLocal}>
                  <th scope="row" className="px-3 py-1.5 font-normal font-sans whitespace-nowrap">{formatHourLong(h.hourLocal)}</th>
                  <td className="px-3 py-1.5 text-right">{count(h.forecastCount)}</td>
                  <td className="px-3 py-1.5 text-right">{h.typicalCount === null ? "–" : count(h.typicalCount)}</td>
                  <td className="px-3 py-1.5 text-right">{h.deltaPct === null ? "–" : signedPct(h.deltaPct)}</td>
                  <td className="px-3 py-1.5 text-right">{h.precipProb === null ? "–" : `${Math.round(h.precipProb)}%`}</td>
                  <td className="px-3 py-1.5 text-right whitespace-nowrap">{h.precipMm === null ? "–" : `${h.precipMm} mm`}</td>
                  <td className="px-3 py-1.5 text-right whitespace-nowrap">{h.tempC === null ? "–" : `${Math.round(h.tempC)}°C`}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </section>
  );
}
