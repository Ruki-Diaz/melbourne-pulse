"use client";

import React, { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { AlertCircle, RotateCw } from "lucide-react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import type { EvidenceResponse, EvidenceRow } from "@/lib/plan";

import { FOCUS_RING, clockHour, count, formatDay, signedPct } from "./plan-utils";

const SensorSensitivityMap = dynamic(() => import("./SensorSensitivityMap").then((mod) => mod.SensorSensitivityMap), {
  ssr: false,
  loading: () => (
    <div className="w-full h-80 sm:h-96 rounded-xl border border-white/10 bg-slate-900/60 animate-pulse motion-reduce:animate-none flex items-center justify-center text-xs text-slate-300">
      Loading sensor map…
    </div>
  ),
});

const GROUP_LABELS: Record<EvidenceRow["group"], string> = {
  overall: "Overall",
  intensity: "By rain intensity",
  daytype: "By day type",
  temperature: "By temperature",
};

/** A scale that fits every estimate and interval, always includes zero, rounded out to 10s. */
function scaleFor(rows: EvidenceRow[]): { min: number; max: number } {
  const values = rows.flatMap((r) => [r.value, r.ciLow ?? r.value, r.ciHigh ?? r.value]);
  return {
    min: Math.floor(Math.min(0, ...values) / 10) * 10,
    max: Math.ceil(Math.max(0, ...values) / 10) * 10 || 10,
  };
}

function ForestRow({ row, scale }: { row: EvidenceRow; scale: { min: number; max: number } }) {
  const at = (value: number) => ((value - scale.min) / (scale.max - scale.min)) * 100;
  const low = at(row.ciLow ?? row.value);
  const high = at(row.ciHigh ?? row.value);
  const interval = row.ciLow !== null && row.ciHigh !== null ? `${signedPct(row.ciLow)} to ${signedPct(row.ciHigh)}` : null;

  return (
    <li className="grid grid-cols-[1fr_auto] sm:grid-cols-[minmax(0,15rem)_1fr_auto] items-center gap-x-4 gap-y-1 py-2.5 px-3 sm:px-4">
      <div className="min-w-0 col-span-2 sm:col-span-1">
        <span className={`text-sm ${row.reliable ? "text-slate-100" : "text-slate-300"}`}>{row.label}</span>
        {!row.reliable && <span className="ml-2 text-[11px] font-medium text-amber-300 whitespace-nowrap">not reliable</span>}
      </div>
      <div className="relative h-5" aria-hidden>
        <div className="absolute inset-y-0 w-px bg-slate-400/60" style={{ left: `${at(0)}%` }} />
        <div
          className="absolute top-1/2 -translate-y-1/2 h-0.5 rounded-full"
          style={{ left: `${low}%`, width: `${Math.max(high - low, 0.5)}%`, backgroundColor: row.reliable ? "#38BDF8" : "#94A3B8" }}
        />
        <div
          className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-3 h-3 rounded-full border-2 border-[#0d1424]"
          style={{ left: `${at(row.value)}%`, backgroundColor: row.reliable ? "#7DD3FC" : "#CBD5E1" }}
        />
      </div>
      <div className="text-right whitespace-nowrap">
        <span className={`text-sm font-mono font-semibold ${row.reliable ? "text-sky-300" : "text-slate-300"}`}>{signedPct(row.value)}</span>
        <span className="block text-[11px] text-slate-400 font-mono">
          {interval ? <span className="hidden sm:inline">{interval} · </span> : null}
          {count(row.nWetHours)} wet h
        </span>
        {interval && <span className="sr-only">95% interval {interval}</span>}
      </div>
    </li>
  );
}

function ForestPlot({ forest }: { forest: EvidenceRow[] }) {
  const scale = scaleFor(forest);
  const groups = (Object.keys(GROUP_LABELS) as EvidenceRow["group"][])
    .map((group) => ({ group, rows: forest.filter((r) => r.group === group) }))
    .filter((g) => g.rows.length > 0);

  return (
    <div className="rounded-xl border border-white/10 bg-slate-900/40 divide-y divide-white/5">
      {groups.map(({ group, rows }) => (
        <div key={group} className="py-1">
          <h4 className="px-3 sm:px-4 pt-2 text-[11px] font-mono uppercase tracking-wider text-teal-300 font-semibold">{GROUP_LABELS[group]}</h4>
          <ul>
            {rows.map((row) => (
              <ForestRow key={`${row.group}-${row.key}`} row={row} scale={scale} />
            ))}
          </ul>
        </div>
      ))}
      <p className="px-3 sm:px-4 py-2 text-[11px] font-mono text-slate-400 flex justify-between" aria-hidden>
        <span>{signedPct(scale.min)}</span>
        <span>the line marks no change</span>
        <span>{signedPct(scale.max)}</span>
      </p>
    </div>
  );
}

function ProfileChart({ profile }: { profile: EvidenceResponse["profile"] }) {
  if (profile.length === 0) {
    return <p className="rounded-xl border border-white/10 bg-slate-900/40 p-6 text-center text-sm text-slate-300">No hourly profile is available yet.</p>;
  }
  const data = profile.map((p) => ({ ...p, label: clockHour(p.hour) }));
  return (
    <div className="rounded-xl border border-white/10 bg-slate-900/40 p-3 sm:p-4">
      <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-200 mb-2" aria-label="Chart legend">
        <li className="flex items-center gap-1.5">
          <span className="w-4 h-0.5 bg-sky-400" aria-hidden />
          Wet hours
        </li>
        <li className="flex items-center gap-1.5">
          <span className="w-4 h-0 border-t-2 border-dashed border-slate-300" aria-hidden />
          Matching dry hours
        </li>
      </ul>
      <div className="w-full h-64 sm:h-72" role="img" aria-label="Line chart of average CBD pedestrian counts by hour of day, in wet hours and in matching dry hours.">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 8, left: -8, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" vertical={false} />
            <XAxis dataKey="label" stroke="#475569" tick={{ fill: "#CBD5E1", fontSize: 11 }} interval="preserveStartEnd" minTickGap={16} />
            <YAxis
              stroke="#475569"
              tick={{ fill: "#CBD5E1", fontSize: 11 }}
              width={48}
              tickFormatter={(value: number) => (value >= 1000 ? `${Math.round(value / 1000)}k` : String(value))}
            />
            <Tooltip
              contentStyle={{ backgroundColor: "rgba(10,15,26,0.95)", border: "1px solid rgba(255,255,255,0.15)", borderRadius: 12, fontSize: 12 }}
              labelStyle={{ color: "#F8FAFC", fontWeight: 600 }}
              itemStyle={{ color: "#E2E8F0" }}
              formatter={(value, name) => [count(Number(value)), name === "wet" ? "Wet hours" : "Matching dry hours"]}
            />
            <Line type="monotone" dataKey="dry" stroke="#CBD5E1" strokeWidth={2} strokeDasharray="6 4" dot={false} isAnimationActive={false} />
            <Line type="monotone" dataKey="wet" stroke="#38BDF8" strokeWidth={2.5} dot={false} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function SensorTable({ sensors }: { sensors: EvidenceResponse["sensors"] }) {
  return (
    <details className="group">
      <summary className={`inline-flex cursor-pointer items-center rounded-md text-xs font-semibold text-teal-300 hover:text-teal-200 ${FOCUS_RING}`}>
        <span className="group-open:hidden">Show all {sensors.length} sensors as a table</span>
        <span className="hidden group-open:inline">Hide the table</span>
      </summary>
      <div className={`mt-3 max-h-96 overflow-auto rounded-lg border border-white/10 ${FOCUS_RING}`} tabIndex={0} role="group" aria-label="Rain effect by sensor">
        <table className="w-full text-xs text-left">
          <caption className="sr-only">Change in pedestrian counts in a wet hour, by sensor</caption>
          <thead className="bg-[#111a2c] text-slate-300 font-mono sticky top-0">
            <tr>
              <th scope="col" className="px-3 py-2 font-semibold">Sensor</th>
              <th scope="col" className="px-3 py-2 font-semibold text-right">Change</th>
              <th scope="col" className="px-3 py-2 font-semibold text-right">95% interval</th>
              <th scope="col" className="px-3 py-2 font-semibold text-right">Wet hours</th>
              <th scope="col" className="px-3 py-2 font-semibold">Reliable</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5 text-slate-200">
            {sensors.map((s) => (
              <tr key={s.id}>
                <th scope="row" className="px-3 py-1.5 font-normal">{s.name}</th>
                <td className="px-3 py-1.5 text-right font-mono">{signedPct(s.value)}</td>
                <td className="px-3 py-1.5 text-right font-mono whitespace-nowrap">
                  {s.ciLow !== null && s.ciHigh !== null ? `${signedPct(s.ciLow)} to ${signedPct(s.ciHigh)}` : "–"}
                </td>
                <td className="px-3 py-1.5 text-right font-mono">{count(s.nWetHours)}</td>
                <td className={`px-3 py-1.5 ${s.reliable ? "" : "text-amber-300"}`}>{s.reliable ? "Yes" : "No"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

type Load = { attempt: number; evidence?: EvidenceResponse; error?: string };

/** The body of "How we know". Loaded, with its charts and map, only when the section is first opened. */
export function EvidenceBody() {
  const [attempt, setAttempt] = useState(0);
  const [load, setLoad] = useState<Load | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/plan/evidence")
      .then(async (res) => {
        if (!res.ok) throw new Error((await res.json().catch(() => null))?.error ?? `The evidence could not be loaded (${res.status}).`);
        return res.json() as Promise<EvidenceResponse>;
      })
      .then((evidence) => !cancelled && setLoad({ attempt, evidence }))
      .catch((error: unknown) => !cancelled && setLoad({ attempt, error: error instanceof Error ? error.message : "The evidence could not be loaded." }));
    return () => {
      cancelled = true;
    };
  }, [attempt]);

  if (!load || load.attempt !== attempt) {
    return (
      <div className="space-y-4" role="status" aria-label="Loading the evidence">
        <div className="h-6 w-48 bg-slate-800 rounded animate-pulse motion-reduce:animate-none" />
        <div className="h-48 bg-slate-800/60 rounded-xl animate-pulse motion-reduce:animate-none" />
        <div className="h-48 bg-slate-800/60 rounded-xl animate-pulse motion-reduce:animate-none" />
      </div>
    );
  }

  if (load.error || !load.evidence) {
    return (
      <div role="alert" className="flex flex-wrap items-center gap-3 p-4 rounded-xl bg-rose-950/30 border border-rose-500/30 text-rose-200 text-sm">
        <AlertCircle className="w-5 h-5 shrink-0" aria-hidden />
        <span className="flex-1 min-w-[12rem]">{load.error}</span>
        <button
          type="button"
          onClick={() => setAttempt((n) => n + 1)}
          className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-rose-400/40 text-xs font-semibold hover:bg-rose-500/10 ${FOCUS_RING}`}
        >
          <RotateCw className="w-3.5 h-3.5" aria-hidden />
          Try again
        </button>
      </div>
    );
  }

  const { forest, profile, sensors, method, window } = load.evidence;
  if (forest.length === 0) {
    return <p className="text-sm text-slate-300">The rain effect hasn&rsquo;t been measured yet. It is recalculated once a month.</p>;
  }
  const reliableSensors = sensors.filter((s) => s.reliable).length;

  return (
    <div className="space-y-8">
      <section className="space-y-3">
        <h3 className="text-sm font-semibold text-white font-['Space_Grotesk',sans-serif]">Change in pedestrian counts in a wet hour</h3>
        <ForestPlot forest={forest} />
        <p className="text-xs text-slate-400">
          Each dot is the estimated change against matching dry hours; the bar is its 95% interval.
          {method && ` An estimate is marked not reliable when it has fewer than ${method.minWetHours} wet hours or its interval includes zero.`}
        </p>
      </section>

      <section className="space-y-3">
        <h3 className="text-sm font-semibold text-white font-['Space_Grotesk',sans-serif]">Average CBD foot traffic by hour of day: wet against dry</h3>
        <ProfileChart profile={profile} />
        <p className="text-xs text-slate-400">
          Totals across all sensors. Each wet hour is set against dry hours at the same sensor, hour of day, day type and month.
        </p>
      </section>

      {sensors.length > 0 && (
        <section className="space-y-3">
          <h3 className="text-sm font-semibold text-white font-['Space_Grotesk',sans-serif]">Rain effect at each sensor</h3>
          <SensorSensitivityMap sensors={sensors} />
          <p className="text-xs text-slate-400">
            {reliableSensors} of {sensors.length} sensors have a reliable estimate of their own. Where a sensor doesn&rsquo;t, this page shows the CBD-wide effect.
          </p>
          <SensorTable sensors={sensors} />
        </section>
      )}

      <section className="space-y-2">
        <h3 className="text-sm font-semibold text-white font-['Space_Grotesk',sans-serif]">Method</h3>
        <div className="text-sm text-slate-300 leading-relaxed space-y-2 max-w-3xl">
          <p>
            {method ? `An hour counts as wet when at least ${method.wetMm} mm of rain was observed. ` : ""}
            Each wet hour at a sensor is compared with the average of dry hours at the same sensor, hour of day, day
            type (weekday, or weekend and public holiday) and month
            {method ? `, as long as there are at least ${method.minDryHours} such dry hours` : ""}. So a wet Tuesday
            9am in July is only compared with dry weekday 9ams in July at that sensor.
          </p>
          <p>
            The effect is the total count in wet hours divided by the total expected from those dry hours, minus one.
            {method &&
              ` The 95% intervals come from ${method.bootstrapReps} bootstrap resamples of whole days, recalculating the dry-hour averages each time.`}
          </p>
          <p className="text-slate-400">
            {window ? `Measured from ${formatDay(window.start)} to ${formatDay(window.end)}` : "Measured over the last 12 months"} and
            recalculated monthly. Pedestrian counts: City of Melbourne Open Data. Observed weather: Open-Meteo.
          </p>
        </div>
      </section>
    </div>
  );
}
