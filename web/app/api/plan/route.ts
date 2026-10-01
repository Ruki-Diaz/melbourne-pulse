import type { NextRequest } from "next/server";

import { getPlan } from "@/lib/plan";
import { PLAN_WINDOWS, type PlanWindow } from "@/lib/plan-core";

import { fail, guarded, ok } from "./respond";

export const revalidate = 3600;

/**
 * GET /api/plan?sensor=<id|cbd>&window=<12h|today|tomorrow|36h>
 * Defaults: sensor=cbd, window=12h. Shape: docs/plan-api.md.
 */
export function GET(request: NextRequest) {
  const params = request.nextUrl.searchParams;
  const sensorParam = params.get("sensor") ?? "cbd";
  const window = (params.get("window") ?? "12h") as PlanWindow;

  if (!PLAN_WINDOWS.includes(window)) {
    return fail(400, `window must be one of: ${PLAN_WINDOWS.join(", ")}`);
  }
  if (sensorParam !== "cbd" && !/^\d{1,6}$/.test(sensorParam)) {
    return fail(400, 'sensor must be "cbd" or a sensor id');
  }
  const sensor = sensorParam === "cbd" ? "cbd" : Number(sensorParam);

  return guarded(async () => {
    const plan = await getPlan(sensor, window);
    return plan ? ok(plan) : fail(404, `No forecast for sensor ${sensorParam}.`);
  });
}
