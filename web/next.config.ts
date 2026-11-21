import type { NextConfig } from "next";

/**
 * Pages are rendered on request (`dynamic = "force-dynamic"`) and cached by
 * Vercel's CDN, not by ISR: CDN caching isn't billed as ISR writes. Next sets
 * `Cache-Control: no-store` on dynamic pages, so the CDN rule goes in
 * `Vercel-CDN-Cache-Control`, which Vercel's CDN reads ahead of Cache-Control.
 * Browsers still re-ask the CDN each visit.
 *
 * s-maxage=3600: at most one render (one database read) per page per CDN
 * region per hour. stale-while-revalidate=600: once that hour is up, the next
 * visitor gets the cached copy while a fresh one renders in the background, so
 * no one waits on Neon waking up. Data timestamps on the page are the
 * database's own, and the badges age them in the browser (lib/useFreshness.ts).
 */
export const CDN_CACHE = "public, s-maxage=3600, stale-while-revalidate=600";

const CACHED_PATHS = ["/", "/map", "/plan", "/about", "/opengraph-image", "/plan/opengraph-image"];

const nextConfig: NextConfig = {
  async headers() {
    return CACHED_PATHS.map((source) => ({
      source,
      headers: [{ key: "Vercel-CDN-Cache-Control", value: CDN_CACHE }],
    }));
  },
};

export default nextConfig;
