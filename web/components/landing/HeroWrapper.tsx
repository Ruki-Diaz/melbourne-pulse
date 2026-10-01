"use client";

import dynamic from "next/dynamic";
import React from "react";

import { FreshnessBadge } from "@/components/ui/FreshnessBadge";
import { useFreshness } from "@/lib/useFreshness";

const DynamicHero = dynamic(
  () => import("@/components/ui/glass-headline-hero").then((mod) => mod.GlassHeadlineHero),
  {
    ssr: false,
    loading: () => (
      <div
        className="relative min-h-[580px] md:min-h-[640px] w-full flex flex-col justify-center items-center bg-[#05080D] overflow-hidden"
        aria-label="Loading Melbourne Pulse Hero"
      >
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_35%,rgba(0,229,199,0.12),transparent_60%)]" />
        <div className="max-w-4xl mx-auto px-4 text-center flex flex-col items-center animate-pulse">
          <div className="h-8 w-48 bg-slate-800/80 rounded-full mb-6 border border-slate-700/40" />
          <div className="h-16 w-80 sm:w-96 bg-slate-800/60 rounded-2xl mb-6" />
          <div className="h-6 w-72 sm:w-[480px] bg-slate-800/40 rounded-lg mb-8" />
          <div className="flex gap-4">
            <div className="h-12 w-40 bg-teal-500/20 rounded-xl" />
            <div className="h-12 w-32 bg-slate-800/40 rounded-xl" />
          </div>
        </div>
      </div>
    ),
  }
);

interface HeroWrapperProps {
  /** When the live data was last written (ISO), or null if there is none. */
  updatedAt: string | null;
  /** When the server built this page (ISO). */
  renderedAt: string;
  title: string;
  description: string;
  primaryAction: { label: string; href: string };
  secondaryAction: { label: string; href: string };
  colors: string[];
}

export function HeroWrapper({ updatedAt, renderedAt, ...props }: HeroWrapperProps) {
  const freshness = useFreshness(updatedAt, renderedAt);
  return <DynamicHero {...props} badge={<FreshnessBadge freshness={freshness} />} />;
}
