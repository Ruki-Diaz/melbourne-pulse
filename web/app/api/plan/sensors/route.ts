import { getPlanSensors } from "@/lib/plan";

import { guarded, ok } from "../respond";

export const revalidate = 3600;

/** GET /api/plan/sensors: the sensors that have a forecast, for the picker. Shape: docs/plan-api.md. */
export function GET() {
  return guarded(async () => ok({ sensors: await getPlanSensors() }));
}
