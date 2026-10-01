import { getPlanEvidence } from "@/lib/plan";

import { guarded, ok } from "../respond";

export const revalidate = 3600;

/** GET /api/plan/evidence: what the rain effect is based on. Shape: docs/plan-api.md. */
export function GET() {
  return guarded(async () => ok(await getPlanEvidence()));
}
