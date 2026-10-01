/**
 * Shared by the /api/plan routes. Responses may be reused by the CDN for 5
 * minutes and served stale for an hour while a fresh one is fetched; the data
 * behind them is cached for an hour in lib/plan.ts either way.
 */
const CACHE = "public, s-maxage=300, stale-while-revalidate=3600";

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
