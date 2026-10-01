"""The Plan API's recommendation logic lives in web/lib/plan-core.ts (TypeScript).

These tests run that real code through web/scripts/plan-recommend.mjs, so the
"right hours" are checked in the same suite as the rest of the data layer.
They need Node 22.18+ (which runs TypeScript directly) and are skipped without it.
"""

import json
import re
import shutil
import subprocess
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from pulse.timeutil import local_hour_to_utc

WEB = Path(__file__).resolve().parents[2] / "web"


def node_version() -> tuple[int, ...]:
    node = shutil.which("node")
    if not node:
        return (0,)
    out = subprocess.run([node, "--version"], capture_output=True, text=True).stdout
    return tuple(int(x) for x in re.findall(r"\d+", out)[:2])


pytestmark = pytest.mark.skipif(node_version() < (22, 18), reason="needs Node 22.18+ to run web/lib/plan-core.ts")


def ms(day: date, hour: int) -> int:
    return int(local_hour_to_utc(day, hour).timestamp() * 1000)


def plan(forecasts, weather, now: datetime, window="12h", sensor="cbd") -> dict:
    payload = {"forecasts": forecasts, "weather": weather, "sensor": sensor,
               "nowMs": int(now.timestamp() * 1000), "window": window}
    done = subprocess.run(
        ["node", "scripts/plan-recommend.mjs"], cwd=WEB, input=json.dumps(payload),
        capture_output=True, text=True, timeout=60,
    )
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def span(rec: dict) -> str:
    """'12-14' for a block from 12:00 to 14:00 local."""
    return f"{int(rec['start'][11:13])}-{int(rec['end'][11:13]) or 24}"


TUESDAY = date(2026, 10, 6)  # after the 4 Oct change: AEDT, UTC+11
NOW = datetime(2026, 10, 5, 18, 30, tzinfo=timezone.utc)  # Tue 05:30 AEDT -> the 12h window is 06:00-17:00

# One sensor, typical 100 every hour.
#   hour      06   07   08   09   10   11   12   13   14   15   16   17
COUNTS = [900, 100, 300, 200, 150, 400, 500, 450, 120, 80, 60, 310]
#   rain risk: 11:00 by amount (0.3 mm), 12:00 by both, 13:00 by chance (60%). 17:00 is just under both.
RAIN = {11: (40, 0.3), 12: (80, 1.0), 13: (60, 0.0), 17: (49, 0.1)}
FORECASTS = [
    {"sensorId": 7, "ms": ms(TUESDAY, 6 + i), "predicted": count, "baseline": 100} for i, count in enumerate(COUNTS)
]
WEATHER = [
    {"ms": ms(TUESDAY, h), "precipProb": RAIN.get(h, (10, 0.0))[0], "precipMm": RAIN.get(h, (10, 0.0))[1],
     "tempC": 15, "windKmh": 10, "weatherCode": 3}
    for h in range(6, 18)
]
# Two-hour blocks inside 7am-10pm (mean count, rain-risk hours):
#   07 200,0  08 250,0  09 175,0  10 275,1  11 450,2  12 475,2  13 285,1  14 100,0  15 70,0  16 185,0


@pytest.fixture(scope="module")
def result():
    return plan(FORECASTS, WEATHER, NOW, sensor=7)


def test_hours_are_local_and_carry_forecast_typical_and_weather(result):
    first = result["hours"][0]
    assert first["hourLocal"] == "2026-10-06T06:00:00+11:00"
    assert (first["forecastCount"], first["typicalCount"], first["deltaPct"]) == (900, 100, 800)
    assert len(result["hours"]) == 12 and result["hours"][6]["precipMm"] == 1.0


def test_most_traffic_picks_the_busiest_blocks(result):
    r = result["recommendations"]["mostTraffic"]
    assert span(r["best"]) == "12-14"  # 475 an hour; 06-08 (500) is before 7am, so it isn't offered
    assert span(r["secondBest"]) == "10-12"  # 11-13 and 13-15 overlap the best
    assert span(r["avoid"]) == "15-17"
    assert r["best"]["deltaPct"] == 375 and r["best"]["maxPrecipProb"] == 80


def test_busy_but_dry_puts_any_dry_block_above_a_wet_one(result):
    r = result["recommendations"]["busyButDry"]
    assert span(r["best"]) == "8-10"  # busiest block with no rain-risk hour, though 12-14 is twice as busy
    assert span(r["secondBest"]) == "16-18"  # 49% and 0.1 mm at 17:00 are under both thresholds
    assert span(r["avoid"]) == "11-13"  # two rain-risk hours, and the quieter of the two such blocks
    assert r["best"]["maxPrecipProb"] == 10
    assert "dry" in r["best"]["reason"] and "likely" in r["avoid"]["reason"]


def test_quietest_picks_the_lowest_blocks(result):
    r = result["recommendations"]["quietest"]
    assert span(r["best"]) == "15-17"
    assert span(r["secondBest"]) == "9-11"  # 14-16 and 16-18 overlap the best
    assert span(r["avoid"]) == "12-14"


def test_recommendations_never_overlap_and_never_say_people(result):
    for preset in result["recommendations"].values():
        blocks = [(r["start"], r["end"]) for r in preset.values()]
        for i, (start, end) in enumerate(blocks):
            for other_start, other_end in blocks[i + 1:]:
                assert end <= other_start or other_end <= start
        for rec in preset.values():
            assert "people" not in rec["reason"].lower()
            assert "pedestrian counts" in rec["reason"] or "foot traffic" in rec["reason"]


def test_rain_never_changes_the_forecast_counts(result):
    dry = plan(FORECASTS, [], NOW, sensor=7)
    assert [h["forecastCount"] for h in dry["hours"]] == [h["forecastCount"] for h in result["hours"]] == COUNTS
    assert dry["recommendations"]["mostTraffic"] == {
        k: {**v, "maxPrecipProb": None, "reason": dry["recommendations"]["mostTraffic"][k]["reason"]}
        for k, v in result["recommendations"]["mostTraffic"].items()
    }
    assert "No weather forecast" in dry["recommendations"]["busyButDry"]["best"]["reason"]


def test_ties_go_to_the_earlier_block():
    flat = [{**f, "predicted": 100} for f in FORECASTS]
    r = plan(flat, [], NOW, sensor=7)["recommendations"]
    assert span(r["mostTraffic"]["best"]) == span(r["quietest"]["best"]) == "7-9"
    assert span(r["mostTraffic"]["secondBest"]) == "9-11"


def test_cbd_sums_sensors_and_compares_like_with_like():
    second = [{**f, "sensorId": 8, "predicted": 50, "baseline": None if i == 0 else 50} for i, f in enumerate(FORECASTS)]
    hours = plan(FORECASTS + second, WEATHER, NOW)["hours"]
    # 06:00: sensor 8 has no typical, so no CBD typical; the delta uses sensor 7 alone (900 vs 100).
    assert (hours[0]["forecastCount"], hours[0]["typicalCount"], hours[0]["deltaPct"]) == (950, None, 800)
    assert (hours[1]["forecastCount"], hours[1]["typicalCount"], hours[1]["deltaPct"]) == (150, 150, 0)


def test_late_evening_falls_back_to_the_hours_there_are():
    late = datetime(2026, 10, 6, 10, 30, tzinfo=timezone.utc)  # Tue 21:30 AEDT
    forecasts = [{"sensorId": 7, "ms": ms(TUESDAY, h), "predicted": 40, "baseline": 50} for h in (22, 23)]
    today = plan(forecasts, [], late, window="today", sensor=7)
    assert [h["hourLocal"][11:13] for h in today["hours"]] == ["22", "23"]
    r = today["recommendations"]["quietest"]
    assert span(r["best"]) == "22-24" and r["secondBest"] is None and r["avoid"] is None

    after_eleven = datetime(2026, 10, 6, 12, 30, tzinfo=timezone.utc)  # 23:30: nothing left of today
    empty = plan(forecasts, [], after_eleven, window="today", sensor=7)
    assert empty["hours"] == [] and empty["recommendations"]["mostTraffic"]["best"] is None


def test_tomorrow_is_the_whole_local_day_across_the_dst_change():
    saturday = datetime(2026, 10, 3, 3, 37, tzinfo=timezone.utc)  # Sat 13:37 AEST; clocks go forward on Sunday
    start = int(datetime(2026, 10, 3, 14, tzinfo=timezone.utc).timestamp() * 1000)  # Sun 00:00 AEST
    forecasts = [{"sensorId": 7, "ms": start + i * 3_600_000, "predicted": 10, "baseline": 10} for i in range(-3, 30)]
    out = plan(forecasts, [], saturday, window="tomorrow", sensor=7)
    labels = [h["hourLocal"] for h in out["hours"]]
    assert len(labels) == 23 and all(label.startswith("2026-10-04") for label in labels)
    assert labels[1] == "2026-10-04T01:00:00+10:00" and labels[2] == "2026-10-04T03:00:00+11:00"  # no 02:00
