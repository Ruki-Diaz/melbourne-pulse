import { Suspense } from "react";

import { PlanClient, PlanFirstPaint } from "@/components/plan/PlanClient";
import { getPlan } from "@/lib/plan";

// Rebuilt hourly and after each ingest, like the other pages.
export const revalidate = 3600;

/**
 * /plan: pick a time to be in the CBD from forecast foot traffic and rain.
 *
 * The server computes the plan for the default choices, so the answer is in
 * the first HTML. In the browser, PlanClient reads the choices from the URL
 * and keeps the data current from /api/plan.
 */
export default async function PlanPage() {
  const initialPlan = await getPlan("cbd", "36h").catch(() => null);
  return (
    <Suspense fallback={<PlanFirstPaint plan={initialPlan} />}>
      <PlanClient initialPlan={initialPlan} />
    </Suspense>
  );
}
