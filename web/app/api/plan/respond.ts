/**
 * Shared by the /api/plan routes. Vercel's CDN reuses a response for an hour
 * and serves it stale for 10 more minutes while a fresh one renders, the same
 * rule as the pages (next.config.ts). This is CDN caching, not ISR.
 */
const CACHE = "public, s-maxage=3600, stale-while-revalidate=600";

export function ok(body: unknown): Response {
  return Response.json(body, { headers: { "Cache-Control": CACHE } });
}

export function fail(status: number, error: string): Response {
  return Response.json({ error }, { status, headers: { "Cache-Control": "no-store" } });
}

/** Runs a handler; a database problem becomes a 503 instead of an unhandled error. */
export async function guarded(handler: () => Promise<Response>): Promise<Response> {
  try {
    return await handler();
  } catch (error) {
    console.error("plan API:", error);
    return fail(503, "Plan data is unavailable right now.");
  }
}
