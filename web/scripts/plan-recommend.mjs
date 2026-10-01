// Runs the Plan API's pure logic from the command line, so pytest can check the
// real code (pipeline/tests/test_plan_recommendations.py). Needs Node 22.18+,
// which runs TypeScript files directly.
//   echo '{"forecasts": [...], "weather": [...], "sensor": "cbd", "nowMs": 0, "window": "12h"}' \
//     | node scripts/plan-recommend.mjs
import { buildHours, recommend, windowRange } from "../lib/plan-core.ts";

let input = "";
for await (const chunk of process.stdin) input += chunk;
const { forecasts, weather, sensor, nowMs, window } = JSON.parse(input);

const range = windowRange(nowMs, window);
const hours = buildHours(forecasts, weather, sensor, range);
process.stdout.write(JSON.stringify({ range, hours, recommendations: recommend(hours) }));
