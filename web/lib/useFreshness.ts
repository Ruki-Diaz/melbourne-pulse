"use client";

import { useSyncExternalStore } from "react";

import { getFreshness, type Freshness } from "./freshness";

// One shared clock that ticks once a minute while any component is listening.
let current = Date.now();
let timer: ReturnType<typeof setInterval> | null = null;
const listeners = new Set<() => void>();

function subscribe(listener: () => void) {
  listeners.add(listener);
  if (!timer) {
    current = Date.now();
    timer = setInterval(() => {
      current = Date.now();
      listeners.forEach((l) => l());
    }, 60_000);
  }
  return () => {
    listeners.delete(listener);
    if (listeners.size === 0 && timer) {
      clearInterval(timer);
      timer = null;
    }
  };
}

/**
 * Freshness computed in the browser, so a page served from the hourly cache
 * can't keep saying "Live" after it stops being true.
 *
 * During server rendering and hydration the clock reads `renderedAt` (when the
 * server built the page), so both renders match; React then switches to the
 * browser's clock and re-checks every minute.
 */
export function useFreshness(updatedAt: string | null, renderedAt: string): Freshness {
  const now = useSyncExternalStore(
    subscribe,
    () => current,
    () => Date.parse(renderedAt)
  );
  return getFreshness(updatedAt, now);
}

/**
 * Returns the current client timestamp in ms, safely synchronized via useSyncExternalStore.
 */
export function useNow(fallbackMs: number = 0): number {
  return useSyncExternalStore(
    subscribe,
    () => current,
    () => fallbackMs
  );
}

