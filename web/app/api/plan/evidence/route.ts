import { getPlanEvidence } from "@/lib/plan";

import { guarded, ok } from "../respond";

// Answered per request from the cached database snapshot (lib/plan.ts), never
// prerendered: a build or regeneration that hit a database hiccup would
// otherwise pin its error response for the whole hour.
export const dynamic = "force-dynamic";
export const revalidate = 3600;

/** GET /api/plan/evidence: what the rain effect is based on. Shape: docs/plan-api.md. */
export function GET() {
  return guarded(async () => ok(await getPlanEvidence()));
}
