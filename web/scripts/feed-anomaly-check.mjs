// Runs web/lib/feed-anomaly.ts from the command line so pytest can check the
// site's anomaly wording (pipeline/tests/test_quality.py). Needs Node 22.18+.
//   echo '{"summary": "...", "anomaly": {...} | null, "sensors": [...]}' | node scripts/feed-anomaly-check.mjs
import { FEED_ANOMALY_COUNT_NOTE, FEED_ANOMALY_TEXT, forDisplay, headline, noComparisonLabel } from "../lib/feed-anomaly.ts";

let input = "";
for await (const chunk of process.stdin) input += chunk;
const { summary, anomaly, sensors } = JSON.parse(input);
process.stdout.write(
  JSON.stringify({
    text: FEED_ANOMALY_TEXT,
    countNote: FEED_ANOMALY_COUNT_NOTE,
    headline: headline(summary, anomaly) ?? null,
    sensors: forDisplay(sensors, anomaly),
    labels: ["No baseline yet", "no baseline yet", "No baseline", "n/a"].map((label) => noComparisonLabel(anomaly !== null, label)),
  })
);
