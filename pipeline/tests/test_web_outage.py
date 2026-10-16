"""A database outage must never be cached as an empty website.

The website's reads (web/lib/db.ts) throw when Neon can't be reached, so Next.js
keeps serving the last good page with its "Last updated X h ago" badge. Only a
database that isn't configured at all (local builds, CI) gives empty results.
Runs the real TypeScript with Node 22.18+ and the installed web packages; skipped
without them (the hourly job), run by the ci workflow.
"""

import json
import os
import subprocess

import pytest

from test_plan_recommendations import WEB, node_version

pytestmark = [
    pytest.mark.skipif(node_version() < (22, 18), reason="needs Node 22.18+ to run web/lib/db.ts"),
    # The hourly job doesn't install the website's packages; the ci workflow does (npm ci).
    pytest.mark.skipif(
        not (WEB / "node_modules" / "@neondatabase" / "serverless").is_dir(),
        reason="needs web/node_modules (npm ci in web/)",
    ),
]

READS = {
    "getLatest": 'db.getLatest("pedestrian")',
    "getAllLatest": "db.getAllLatest()",
    "getLatestSummaryData": "db.getLatestSummaryData()",
    "getForecasts": "db.getForecasts(9)",
    "getRecentPedestrianHistory": "db.getRecentPedestrianHistory(24)",
    "getFeedAnomaly": 'db.getFeedAnomaly("2026-10-16T00:00:00Z")',
}

SCRIPT = """
const db = await import("./lib/db.ts");
const out = {};
for (const [name, call] of Object.entries({%s})) {
  try { out[name] = { returned: await call() }; } catch (e) { out[name] = { threw: String(e.message) }; }
}
console.log(JSON.stringify(out));
""" % ", ".join(f"{name}: () => {expr}" for name, expr in READS.items())


def run(url: str | None) -> dict:
    env = {k: v for k, v in os.environ.items() if k != "DATABASE_URL_READONLY"}
    if url:
        env["DATABASE_URL_READONLY"] = url
    done = subprocess.run(
        ["node", "--no-warnings", "--conditions=react-server", "--input-type=module", "-e", SCRIPT],
        cwd=WEB, env=env, capture_output=True, text=True, timeout=60,
    )
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def test_every_read_throws_when_the_database_cant_be_reached():
    results = run("postgresql://web_reader:x@neon.invalid/neondb")  # .invalid never resolves
    assert {name: "threw" in r for name, r in results.items()} == {name: True for name in READS}


def test_an_unconfigured_database_gives_empty_results_for_local_builds():
    results = run(None)
    assert all("returned" in r for r in results.values())
    assert results["getForecasts"]["returned"] == []
    assert results["getLatestSummaryData"]["returned"] == {"pedestrian": None, "sensors": None, "summary": None, "parking": None}
