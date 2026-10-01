"use client";

import React, { useEffect, useId, useMemo, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { Building2, Check, ChevronDown, CloudSun, Map as MapIcon, MapPin, Search, TrendingUp, VolumeX } from "lucide-react";

import type { PlanSensor } from "@/lib/plan";
import type { PlanWindow } from "@/lib/plan-core";

import { FOCUS_RING } from "./plan-utils";

const MiniSensorPickerMap = dynamic(() => import("./MiniSensorPickerMap").then((mod) => mod.MiniSensorPickerMap), {
  ssr: false,
  loading: () => (
    <div className="w-full h-64 sm:h-72 rounded-xl border border-white/10 bg-slate-900/60 animate-pulse motion-reduce:animate-none flex items-center justify-center text-xs text-slate-300">
      Loading sensor map…
    </div>
  ),
});

export type GoalOption = "busyButDry" | "mostTraffic" | "quietest";

export const GOALS: Array<{ id: GoalOption; label: string; icon: React.ComponentType<{ className?: string }> }> = [
  { id: "busyButDry", label: "Busy but dry", icon: CloudSun },
  { id: "mostTraffic", label: "Most foot traffic", icon: TrendingUp },
  { id: "quietest", label: "Quietest", icon: VolumeX },
];

export const WINDOWS: Array<{ id: PlanWindow; label: string }> = [
  { id: "12h", label: "Next 12h" },
  { id: "today", label: "Today" },
  { id: "tomorrow", label: "Tomorrow" },
  { id: "36h", label: "Next 36h" },
];

export const CBD_LABEL = "Whole CBD";

/** A radio group drawn as a row of buttons: arrow keys move and select, Tab leaves the group. */
function Segmented<T extends string>({
  label,
  options,
  value,
  onChange,
  accent,
  note,
}: {
  label: string;
  options: Array<{ id: T; label: string; icon?: React.ComponentType<{ className?: string }> }>;
  value: T;
  onChange: (value: T) => void;
  accent: boolean;
  note?: React.ReactNode;
}) {
  const labelId = useId();
  const refs = useRef<Array<HTMLButtonElement | null>>([]);

  function onKeyDown(event: React.KeyboardEvent, index: number) {
    const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[event.key];
    const next = event.key === "Home" ? 0 : event.key === "End" ? options.length - 1 : step === undefined ? null : (index + step + options.length) % options.length;
    if (next === null) return;
    event.preventDefault();
    onChange(options[next].id);
    refs.current[next]?.focus();
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-1.5">
        <span id={labelId} className="text-[11px] font-mono uppercase tracking-wider text-slate-400">
          {label}
        </span>
        {note}
      </div>
      <div role="radiogroup" aria-labelledby={labelId} className="flex bg-slate-900/90 border border-white/10 rounded-xl p-1 gap-1">
        {options.map((option, index) => {
          const selected = option.id === value;
          const Icon = option.icon;
          return (
            <button
              key={option.id}
              ref={(el) => {
                refs.current[index] = el;
              }}
              type="button"
              role="radio"
              aria-checked={selected}
              tabIndex={selected ? 0 : -1}
              onClick={() => onChange(option.id)}
              onKeyDown={(event) => onKeyDown(event, index)}
              className={`flex-1 min-h-11 flex items-center justify-center gap-1.5 py-2 px-1.5 rounded-lg text-xs leading-tight font-semibold text-center lg:whitespace-nowrap transition-colors ${FOCUS_RING} ${
                selected
                  ? accent
                    ? "bg-teal-400 text-zinc-950"
                    : "bg-slate-700 text-white ring-1 ring-white/20"
                  : "text-slate-300 hover:text-white hover:bg-white/5"
              }`}
            >
              {Icon && <Icon className={`hidden sm:block w-3.5 h-3.5 shrink-0 ${selected ? "text-zinc-950" : "text-teal-400"}`} />}
              <span>{option.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

/** Searchable sensor picker: type to filter, arrow keys to move, Enter to choose, Escape to close. */
function SensorCombobox({
  sensors,
  selected,
  onSelect,
}: {
  sensors: PlanSensor[];
  selected: number | "cbd";
  onSelect: (sensor: number | "cbd") => void;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const rootRef = useRef<HTMLDivElement | null>(null);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const listRef = useRef<HTMLUListElement | null>(null);
  const baseId = useId();
  const labelId = `${baseId}-label`;
  const listId = `${baseId}-list`;

  const options = useMemo(() => {
    const q = query.trim().toLowerCase();
    const all: Array<{ id: number | "cbd"; name: string }> = [{ id: "cbd", name: CBD_LABEL }, ...sensors];
    return q ? all.filter((o) => o.name.toLowerCase().includes(q)) : all;
  }, [sensors, query]);

  const selectedName = selected === "cbd" ? CBD_LABEL : (sensors.find((s) => s.id === selected)?.name ?? `Sensor ${selected}`);

  useEffect(() => {
    if (!open) return;
    function onPointerDown(event: PointerEvent) {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [open]);

  useEffect(() => {
    if (open) listRef.current?.querySelector('[data-active="true"]')?.scrollIntoView({ block: "nearest" });
  }, [open, active]);

  function openList() {
    setQuery("");
    setActive(Math.max(0, selected === "cbd" ? 0 : sensors.findIndex((s) => s.id === selected) + 1));
    setOpen(true);
  }

  function close(returnFocus: boolean) {
    setOpen(false);
    if (returnFocus) triggerRef.current?.focus();
  }

  function choose(id: number | "cbd") {
    onSelect(id);
    close(true);
  }

  function onKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      if (options.length) setActive((i) => (i + (event.key === "ArrowDown" ? 1 : -1) + options.length) % options.length);
    } else if (event.key === "Home" || event.key === "End") {
      event.preventDefault();
      setActive(event.key === "Home" ? 0 : Math.max(0, options.length - 1));
    } else if (event.key === "Enter") {
      event.preventDefault();
      if (options[active]) choose(options[active].id);
    } else if (event.key === "Escape") {
      event.preventDefault();
      close(true);
    } else if (event.key === "Tab") {
      setOpen(false);
    }
  }

  return (
    <div className="flex-1 min-w-0" ref={rootRef}>
      <button
        ref={triggerRef}
        type="button"
        onClick={() => (open ? close(false) : openList())}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? listId : undefined}
        aria-labelledby={`${labelId} ${baseId}-value`}
        className={`w-full min-h-11 flex items-center justify-between gap-2 px-3.5 py-2.5 rounded-xl bg-slate-900/90 hover:bg-slate-800/90 border border-white/10 text-left text-sm text-white transition-colors ${FOCUS_RING}`}
      >
        <span className="flex items-center gap-2 min-w-0">
          {selected === "cbd" ? (
            <Building2 className="w-4 h-4 text-teal-400 shrink-0" aria-hidden />
          ) : (
            <MapPin className="w-4 h-4 text-teal-400 shrink-0" aria-hidden />
          )}
          <span id={`${baseId}-value`} className="truncate font-medium">
            {selectedName}
          </span>
        </span>
        <ChevronDown className={`w-4 h-4 text-slate-400 shrink-0 transition-transform ${open ? "rotate-180" : ""}`} aria-hidden />
      </button>
      <span id={labelId} className="sr-only">
        Location
      </span>

      {open && (
        <div className="absolute top-full left-0 right-0 mt-2 z-50 bg-[#0A0F1A] border border-white/15 rounded-xl shadow-2xl overflow-hidden flex flex-col">
          <div className="p-2.5 border-b border-white/10 flex items-center gap-2">
            <Search className="w-4 h-4 text-slate-400 shrink-0" aria-hidden />
            <input
              autoFocus
              type="text"
              role="combobox"
              aria-expanded="true"
              aria-controls={listId}
              aria-autocomplete="list"
              aria-activedescendant={options[active] ? `${baseId}-option-${options[active].id}` : undefined}
              aria-label="Search sensors by street or name"
              placeholder="Search by street or sensor name"
              value={query}
              onChange={(event) => {
                setQuery(event.target.value);
                setActive(0);
              }}
              onKeyDown={onKeyDown}
              className="w-full bg-transparent text-base sm:text-sm text-white placeholder-slate-400 focus:outline-none"
            />
          </div>
          <ul ref={listRef} id={listId} role="listbox" aria-labelledby={labelId} className="max-h-64 overflow-y-auto p-1">
            {options.length === 0 && (
              <li role="presentation" className="px-3 py-4 text-center text-sm text-slate-300">
                No sensor matches &ldquo;{query}&rdquo;
              </li>
            )}
            {options.map((option, index) => {
              const isSelected = option.id === selected;
              const isActive = index === active;
              return (
                <li
                  key={option.id}
                  id={`${baseId}-option-${option.id}`}
                  role="option"
                  aria-selected={isSelected}
                  data-active={isActive}
                  onPointerMove={() => setActive(index)}
                  onClick={() => choose(option.id)}
                  className={`flex items-center justify-between gap-2 px-3 py-2 rounded-lg text-sm cursor-pointer ${
                    isActive ? "bg-white/10" : ""
                  } ${isSelected ? "text-teal-300 font-semibold" : "text-slate-200"}`}
                >
                  <span className="flex items-center gap-2 min-w-0">
                    {option.id === "cbd" && <Building2 className="w-4 h-4 text-teal-400 shrink-0" aria-hidden />}
                    <span className="truncate">{option.name}</span>
                    {option.id === "cbd" && sensors.length > 0 && (
                      <span className="text-xs font-normal text-slate-400 shrink-0">all {sensors.length} sensors</span>
                    )}
                  </span>
                  {isSelected && <Check className="w-4 h-4 text-teal-400 shrink-0" aria-hidden />}
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
}

interface PlanControlsProps {
  sensors: PlanSensor[];
  selectedSensor: number | "cbd";
  onSelectSensor: (sensor: number | "cbd") => void;
  selectedGoal: GoalOption;
  onSelectGoal: (goal: GoalOption) => void;
  selectedWindow: PlanWindow;
  onSelectWindow: (window: PlanWindow) => void;
  isLoading?: boolean;
}

export function PlanControls({
  sensors,
  selectedSensor,
  onSelectSensor,
  selectedGoal,
  onSelectGoal,
  selectedWindow,
  onSelectWindow,
  isLoading = false,
}: PlanControlsProps) {
  const [showMap, setShowMap] = useState(false);
  const mapId = useId();

  return (
    <section
      aria-label="Plan options"
      className="lg:sticky lg:top-[4.5rem] z-30 bg-[#070B13]/90 backdrop-blur-xl border border-white/10 rounded-2xl p-3 sm:p-4 shadow-xl"
    >
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_1.3fr_1fr] gap-3 lg:gap-4 items-start">
        <div>
          <div className="text-[11px] font-mono uppercase tracking-wider text-slate-400 mb-1.5" aria-hidden>
            Location
          </div>
          {/* relative: the sensor list opens across the full width of this row */}
          <div className="relative flex gap-2">
            <SensorCombobox sensors={sensors} selected={selectedSensor} onSelect={onSelectSensor} />
            <button
              type="button"
              onClick={() => setShowMap((v) => !v)}
              aria-expanded={showMap}
              aria-controls={mapId}
              className={`min-h-11 px-3 rounded-xl border flex items-center gap-1.5 text-xs font-semibold transition-colors ${FOCUS_RING} ${
                showMap
                  ? "bg-teal-500/20 border-teal-500/50 text-teal-200"
                  : "bg-slate-900/90 border-white/10 text-slate-200 hover:text-white hover:bg-slate-800"
              }`}
            >
              <MapIcon className="w-4 h-4 text-teal-400" aria-hidden />
              <span className="whitespace-nowrap">{showMap ? "Hide map" : "Pick on map"}</span>
            </button>
          </div>
        </div>

        <div>
          <Segmented label="Goal" options={GOALS} value={selectedGoal} onChange={onSelectGoal} accent />
        </div>

        <div>
          <Segmented
            label="Window"
            options={WINDOWS}
            value={selectedWindow}
            onChange={onSelectWindow}
            accent={false}
            note={
              <span role="status" className="text-[11px] text-teal-300 font-mono">
                {isLoading ? "Updating…" : ""}
              </span>
            }
          />
        </div>
      </div>

      {showMap && (
        <div id={mapId} className="mt-3 pt-3 border-t border-white/10 space-y-2">
          <p className="text-xs text-slate-300">Select a sensor dot to see its own forecast. The list above has the same sensors.</p>
          <MiniSensorPickerMap sensors={sensors} selectedSensor={selectedSensor} onSelectSensor={onSelectSensor} />
        </div>
      )}
    </section>
  );
}
