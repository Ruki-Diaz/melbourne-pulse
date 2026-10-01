// The site quotes the forecast model's test results in a few places. They are
// read from lib/model-metrics.json, which this script writes from
// ../model/metrics.json (the file train.py produces), so the numbers can't
// drift from the report. It also refreshes public/chart.png.
//
// Runs before `dev` and `build`. Both outputs are committed: if the model
// folder isn't there (a build that only has web/), the committed copies are used.
import { copyFileSync, existsSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const model = join(root, "..", "model");
const source = join(model, "metrics.json");

if (!existsSync(source)) {
  console.log("model/metrics.json not found; keeping the committed lib/model-metrics.json");
} else {
  const NAIVE = "Seasonal naive (same hour last week)";
  const TYPICAL = "Typical (8-week median, the app's baseline)";
  const LGBM = "LightGBM";
  const { decision, attempts } = JSON.parse(readFileSync(source, "utf8"));
  const shipped = attempts.find((a) => a.label === decision.shipped);
  const control = attempts.find((a) => a.label === decision.control);
  const one = (x) => Math.round(x * 10) / 10;
  const scores = (r) => ({ mae: one(r.mae), mape: one(r.mape), wetMae: one(r.wet_mae) });

  const metrics = {
    source: "model/metrics.json (written by model/train.py; do not edit by hand)",
    test: {
      from: shipped.split.test[0],
      to: shipped.split.test[1],
      sensorHours: shipped.split.test_rows_scored,
      sensors: shipped.split.sensors,
      wetHours: decision.test_wet_hours,
    },
    naive: scores(shipped.results[NAIVE]),
    typical: scores(shipped.results[TYPICAL]),
    model: scores(shipped.results[LGBM]),
    withoutWeather: scores(control.results[LGBM]),
    usesWeather: decision.ship_weather,
    // How much lower the model's error is than the 8-week typical, in percent.
    improvementPct: Math.round((1 - shipped.results[LGBM].mae / shipped.results[TYPICAL].mae) * 100),
  };
  writeFileSync(join(root, "lib", "model-metrics.json"), JSON.stringify(metrics, null, 2) + "\n");
  copyFileSync(join(model, "chart.png"), join(root, "public", "chart.png"));
  console.log(
    `model metrics -> lib/model-metrics.json (MAE ${metrics.model.mae} vs ${metrics.typical.mae} typical, ` +
      `${metrics.improvementPct}% lower)`
  );
}
