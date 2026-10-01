"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { usePathname, useSearchParams } from "next/navigation";
import { AlertTriangle, RotateCw } from "lucide-react";

import type { PlanResponse, PlanSensor } from "@/lib/plan";
import { HOUR_MS, PLAN_WINDOWS, type PlanWindow } from "@/lib/plan-core";
import { useNow } from "@/lib/useFreshness";

import { AnswerCard } from "./AnswerCard";
import { EvidenceSection } from "./EvidenceSection";
import { PlanHeader, ShortWindowNote } from "./PlanHeader";
import { CBD_LABEL, GOALS, PlanControls, type GoalOption } from "./PlanControls";
import { RainEffectCard } from "./RainEffectCard";
import { CARD, FOCUS_RING } from "./plan-utils";

const ChartSkeleton = () => (
  <div className={`${CARD} h-[26rem] animate-pulse motion-reduce:animate-none`} role="status" aria-label="Loading the chart" />
);

// The chart library is the heaviest part of the page; it loads after the answer is on screen.
const HourChart = dynamic(() => import("./HourChart").then((mod) => mod.HourChart), { ssr: false, loading: ChartSkeleton });

/**
 * Draws its children only once the placeholder is on (or near) the screen. On a
 * phone the chart starts below the fold, so its code isn't part of the first load.
 */
function WhenVisible({ children }: { children: React.ReactNode }) {
  const ref = useRef<HTMLDivElement | null>(null);
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el || visible) return;
    const observer = new IntersectionObserver(
      (entries) => entries.some((e) => e.isIntersecting) && setVisible(true),
      { rootMargin: "200px" }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [visible]);
  return visible ? <>{children}</> : <div ref={ref}><ChartSkeleton /></div>;
}

const DEFAULTS = { sensor: "cbd", goal: "busyButDry", window: "36h" } as const;

type Result = { key: string; plan?: PlanResponse; error?: string };

async function getJson<T>(url: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(url, { signal });
  if (!res.ok) {
    const body = (await res.json().catch(() => null)) as { error?: string } | null;
    throw new Error(body?.error ?? `The server answered ${res.status}.`);
  }
  return res.json() as Promise<T>;
}

/**
 * The Plan page. The choices (sensor, goal, window, evidence open) live in the
 * URL, so a plan can be bookmarked or shared; every figure comes from /api/plan.
 */
export function PlanClient({ initialPlan }: { initialPlan: PlanResponse | null }) {
  const params = useSearchParams();
  const pathname = usePathname();
  const now = useNow();

  const sensorParam = params.get("sensor") ?? DEFAULTS.sensor;
  const sensor: number | "cbd" = /^\d{1,6}$/.test(sensorParam) ? Number(sensorParam) : "cbd";
  const goal: GoalOption = GOALS.find((g) => g.id === params.get("goal"))?.id ?? DEFAULTS.goal;
  const planWindow: PlanWindow = PLAN_WINDOWS.find((w) => w === params.get("window")) ?? DEFAULTS.window;
  const evidenceOpen = params.get("evidence") === "1";

  const setParams = useCallback(
    (changes: Record<string, string | null>) => {
      const next = new URLSearchParams(params.toString());
      for (const [name, value] of Object.entries(changes)) {
        if (value === null || value === DEFAULTS[name as keyof typeof DEFAULTS]) next.delete(name);
        else next.set(name, value);
      }
      const query = next.toString();
      // replaceState keeps useSearchParams in sync without a round trip to the server.
      window.history.replaceState(null, "", query ? `${pathname}?${query}` : pathname);
    },
    [params, pathname]
  );

  const [sensors, setSensors] = useState<PlanSensor[]>([]);
  const [sensorsError, setSensorsError] = useState(false);
  useEffect(() => {
    let cancelled = false;
    getJson<{ sensors: PlanSensor[] }>("/api/plan/sensors")
      .then((data) => !cancelled && setSensors(data.sensors))
      .catch(() => !cancelled && setSensorsError(true));
    return () => {
      cancelled = true;
    };
  }, []);

  // Refetch when the choice changes and when the clock passes into a new hour (the windows start at the next hour).
  const [attempt, setAttempt] = useState(0);
  const hour = now > 0 ? Math.floor(now / HOUR_MS) : null;
  const key = `${sensor}|${planWindow}|${hour}|${attempt}`;
  // The server's plan for the default choices is shown at once; the request below replaces it.
  // "initial" never equals a real key, so it is marked as updating unless it is for this very hour.
  const [result, setResult] = useState<Result | null>(initialPlan ? { key: "initial", plan: initialPlan } : null);
  useEffect(() => {
    if (hour === null) return;
    const controller = new AbortController();
    getJson<PlanResponse>(`/api/plan?sensor=${sensor}&window=${planWindow}`, controller.signal)
      .then((plan) => setResult({ key, plan }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setResult({ key, error: error instanceof Error ? error.message : "The plan could not be loaded." });
      });
    return () => controller.abort();
  }, [key, sensor, planWindow, hour]);

  const isDefault = sensor === DEFAULTS.sensor && planWindow === DEFAULTS.window;
  const fromServer = result?.key === "initial";
  // The server's plan stands in only for the default choices, and counts as current if it was made this hour.
  const serverPlanIsCurrent =
    fromServer && isDefault && attempt === 0 && (hour === null || Math.floor(Date.parse(initialPlan!.generatedAt) / HOUR_MS) === hour);
  const isLoading = result?.key !== key && !serverPlanIsCurrent;
  const plan = fromServer && !isDefault ? null : (result?.plan ?? null);
  const error = !isLoading ? (result?.error ?? null) : null;
  const openEvidence = useCallback(() => {
    setParams({ evidence: "1" });
    requestAnimationFrame(() => {
      const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      document.getElementById("evidence")?.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
    });
  }, [setParams]);

  const selectSensor = useCallback((id: number | "cbd") => setParams({ sensor: String(id) }), [setParams]);

  return (
    <PlanView
      sensor={sensor}
      goal={goal}
      planWindow={planWindow}
      evidenceOpen={evidenceOpen}
      sensors={sensors}
      sensorsError={sensorsError}
      plan={plan}
      error={error}
      isLoading={isLoading}
      now={now}
      onSelectSensor={selectSensor}
      onSelectGoal={(id) => setParams({ goal: id })}
      onSelectWindow={(id) => setParams({ window: id })}
      onToggleEvidence={(open) => setParams({ evidence: open ? "1" : null })}
      onOpenEvidence={openEvidence}
      onShowCbd={() => setParams({ sensor: null })}
      onRetry={() => setAttempt((n) => n + 1)}
    />
  );
}

interface PlanViewProps {
  sensor: number | "cbd";
  goal: GoalOption;
  planWindow: PlanWindow;
  evidenceOpen: boolean;
  sensors: PlanSensor[];
  sensorsError: boolean;
  plan: PlanResponse | null;
  error: string | null;
  isLoading: boolean;
  now: number;
  onSelectSensor: (sensor: number | "cbd") => void;
  onSelectGoal: (goal: GoalOption) => void;
  onSelectWindow: (window: PlanWindow) => void;
  onToggleEvidence: (open: boolean) => void;
  onOpenEvidence: () => void;
  onShowCbd: () => void;
  onRetry: () => void;
}

/** Everything on the page, given the choices and the data. No state of its own. */
function PlanView({
  sensor,
  goal,
  planWindow,
  evidenceOpen,
  sensors,
  sensorsError,
  plan,
  error,
  isLoading,
  now,
  onSelectSensor,
  onSelectGoal,
  onSelectWindow,
  onToggleEvidence,
  onOpenEvidence,
  onShowCbd,
  onRetry,
}: PlanViewProps) {
  const goalLabel = GOALS.find((g) => g.id === goal)?.label ?? "";
  const placeName = plan ? (plan.sensor === "cbd" ? CBD_LABEL : plan.sensor.name) : CBD_LABEL;

  return (
    <main className="min-h-screen bg-[#05080D]">
      <div className="fixed inset-0 -z-10 pointer-events-none bg-[radial-gradient(ellipse_at_top,_rgba(0,229,199,0.06)_0%,_transparent_60%)]" aria-hidden />

      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8 sm:py-12 space-y-6">
        <PlanHeader plan={plan} now={now} failed={error !== null} />

        <PlanControls
          sensors={sensors}
          selectedSensor={sensor}
          onSelectSensor={onSelectSensor}
          selectedGoal={goal}
          onSelectGoal={onSelectGoal}
          selectedWindow={planWindow}
          onSelectWindow={onSelectWindow}
          isLoading={isLoading && plan !== null}
        />

        {sensorsError && (
          <p role="status" className="text-xs text-amber-200 bg-amber-950/40 border border-amber-500/30 rounded-lg px-3 py-2">
            The list of sensors could not be loaded, so only {CBD_LABEL} can be chosen for now.
          </p>
        )}

        {error && (
          <div role="alert" className="flex flex-wrap items-center gap-3 p-4 rounded-xl bg-rose-950/30 border border-rose-500/30 text-rose-200 text-sm">
            <AlertTriangle className="w-5 h-5 shrink-0" aria-hidden />
            <span className="flex-1 min-w-[12rem]">{error}</span>
            {sensor !== "cbd" && (
              <button
                type="button"
                onClick={onShowCbd}
                className={`px-3 py-1.5 rounded-lg border border-rose-400/40 text-xs font-semibold hover:bg-rose-500/10 ${FOCUS_RING}`}
              >
                Show {CBD_LABEL}
              </button>
            )}
            <button
              type="button"
              onClick={onRetry}
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-rose-400/40 text-xs font-semibold hover:bg-rose-500/10 ${FOCUS_RING}`}
            >
              <RotateCw className="w-3.5 h-3.5" aria-hidden />
              Try again
            </button>
          </div>
        )}

        {!plan && !error && (
          <div className="space-y-6" role="status" aria-label="Loading the forecast">
            <div className={`${CARD} h-64 animate-pulse motion-reduce:animate-none`} />
            <ChartSkeleton />
          </div>
        )}

        {plan && !error && (
          <>
            <AnswerCard
              recommendations={plan.recommendations[goal]}
              hoursConsidered={plan.recommendations.hoursConsidered}
              goalLabel={goalLabel}
              hoursInWindow={plan.hours.length}
              isLoading={isLoading}
            />
            <ShortWindowNote plan={plan} />
            <WhenVisible>
              <HourChart
                hours={plan.hours}
                bestBlock={plan.recommendations[goal].best}
                avoidBlock={plan.recommendations[goal].avoid}
                placeName={placeName}
                isLoading={isLoading}
              />
            </WhenVisible>
            <RainEffectCard rainEffect={plan.rainEffect} placeName={placeName} onOpenEvidence={onOpenEvidence} />
          </>
        )}

        <EvidenceSection open={evidenceOpen} onToggle={onToggleEvidence} />
      </div>
    </main>
  );
}

const NOTHING = () => {};

/**
 * What the server sends first: the page with its default choices (Whole CBD,
 * busy but dry, next 36 hours) and the plan the server computed. PlanClient
 * draws the same thing once it has read the URL, then takes over.
 */
export function PlanFirstPaint({ plan }: { plan: PlanResponse | null }) {
  return (
    <PlanView
      sensor={DEFAULTS.sensor}
      goal={DEFAULTS.goal}
      planWindow={DEFAULTS.window}
      evidenceOpen={false}
      sensors={[]}
      sensorsError={false}
      plan={plan}
      error={null}
      isLoading={false}
      now={0}
      onSelectSensor={NOTHING}
      onSelectGoal={NOTHING}
      onSelectWindow={NOTHING}
      onToggleEvidence={NOTHING}
      onOpenEvidence={NOTHING}
      onShowCbd={NOTHING}
      onRetry={NOTHING}
    />
  );
}
