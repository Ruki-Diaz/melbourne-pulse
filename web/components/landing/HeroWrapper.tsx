"use client";

import Link from "next/link";
import React from "react";
import { ArrowRight, CalendarClock } from "lucide-react";

import { FreshnessBadge } from "@/components/ui/FreshnessBadge";
import { GlassHeadlineHero } from "@/components/ui/glass-headline-hero";
import { useFreshness } from "@/lib/useFreshness";

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
  /** The small link under the buttons; its label is written on the server from the weather forecast. */
  planLink: { label: string; href: string };
}

/**
 * The hero is rendered on the server too, so its headline and summary are in
 * the first HTML and paint before any script loads. Only the WebGL background
 * waits for the browser.
 */
export function HeroWrapper({ updatedAt, renderedAt, planLink, ...props }: HeroWrapperProps) {
  const freshness = useFreshness(updatedAt, renderedAt);
  return (
    <GlassHeadlineHero
      {...props}
      badge={<FreshnessBadge freshness={freshness} />}
      footer={
        <Link
          href={planLink.href}
          className="group inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full border border-slate-600/40 bg-slate-900/70 hover:border-teal-400/50 text-slate-200 hover:text-white text-xs sm:text-sm font-medium tracking-wide backdrop-blur-md transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-400"
        >
          <CalendarClock className="w-3.5 h-3.5 text-teal-400" aria-hidden />
          <span>{planLink.label}</span>
          <ArrowRight className="w-3.5 h-3.5 text-teal-400 transition-transform group-hover:translate-x-0.5" aria-hidden />
        </Link>
      }
    />
  );
}
