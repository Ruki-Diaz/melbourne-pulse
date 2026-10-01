"use client";

import React from "react";
import dynamic from "next/dynamic";
import { ChevronDown, FlaskConical } from "lucide-react";

import { CARD } from "./plan-utils";

const EvidenceBody = dynamic(() => import("./EvidenceBody").then((mod) => mod.EvidenceBody), {
  ssr: false,
  loading: () => <div className="h-48 bg-slate-800/60 rounded-xl animate-pulse motion-reduce:animate-none" role="status" aria-label="Loading the evidence" />,
});

/** Collapsible "How we know". The charts, map and data are only fetched once it is opened. */
export function EvidenceSection({ open, onToggle }: { open: boolean; onToggle: (open: boolean) => void }) {
  return (
    <section id="evidence" aria-labelledby="evidence-title" className={`${CARD} overflow-hidden scroll-mt-24`}>
      <h2 id="evidence-title">
        <button
          type="button"
          onClick={() => onToggle(!open)}
          aria-expanded={open}
          aria-controls="evidence-body"
          className="w-full flex items-center justify-between gap-3 px-5 sm:px-6 py-4 text-left hover:bg-white/[0.03] transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-teal-400"
        >
          <span className="flex items-center gap-3">
            <span className="flex items-center justify-center w-9 h-9 rounded-xl bg-purple-500/10 border border-purple-500/30 text-purple-300 shrink-0">
              <FlaskConical className="w-4 h-4" aria-hidden />
            </span>
            <span>
              <span className="block text-base sm:text-lg font-bold text-white font-['Space_Grotesk',sans-serif]">How we know</span>
              <span className="block text-xs font-normal text-slate-400 mt-0.5">The evidence behind the rain effect, and how it was measured</span>
            </span>
          </span>
          <ChevronDown className={`w-5 h-5 text-slate-300 shrink-0 transition-transform duration-200 motion-reduce:transition-none ${open ? "rotate-180" : ""}`} aria-hidden />
        </button>
      </h2>
      <div id="evidence-body" hidden={!open} className="border-t border-white/10 px-4 sm:px-6 py-5">
        {open && <EvidenceBody />}
      </div>
    </section>
  );
}
