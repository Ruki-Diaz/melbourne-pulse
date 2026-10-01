// Runs the Plan API's pure logic from the command line, so pytest can check the
// real code (pipeline/tests/test_plan_recommendations.py). Needs Node 22.18+,
// which runs TypeScript files directly.
//   echo '{"forecasts": [...], "weather": [...], "sensor": "cbd", "nowMs": 0, "window": "12h"}' \
//     | node scripts/plan-recommend.mjs
// With a "snapshot" key instead, it returns the whole /api/plan response for that snapshot.
import { assemblePlan, buildHours, recommend, windowRange } from "../lib/plan-core.ts";

let input = "";
for await (const chunk of process.stdin) input += chunk;
const { snapshot, forecasts, weather, sensor, nowMs, window } = JSON.parse(input);

if (snapshot) {
  process.stdout.write(JSON.stringify(assemblePlan(snapshot, sensor, window, nowMs)));
} else {
  const range = windowRange(nowMs, window);
  const { hours, sensorsUsed } = buildHours(forecasts, weather, sensor, range);
  process.stdout.write(JSON.stringify({ range, hours, sensorsUsed, recommendations: recommend(hours) }));
}
