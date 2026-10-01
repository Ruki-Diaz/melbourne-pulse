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


def run(payload: dict) -> dict:
    done = subprocess.run(
        ["node", "scripts/plan-recommend.mjs"], cwd=WEB, input=json.dumps(payload),
        capture_output=True, text=True, timeout=60,
    )
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def plan(forecasts, weather, now: datetime, window="12h", sensor="cbd") -> dict:
    return run({"forecasts": forecasts, "weather": weather, "sensor": sensor,
                "nowMs": int(now.timestamp() * 1000), "window": window})


def response(snapshot: dict, now: datetime, window="12h", sensor="cbd") -> dict:
    """The whole /api/plan response for a database snapshot."""
    return run({"snapshot": snapshot, "sensor": sensor, "nowMs": int(now.timestamp() * 1000), "window": window})


PRESETS = ("mostTraffic", "busyButDry", "quietest")


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
    assert r["best"]["reason"].startswith("Busiest hours where rain isn't likely:")
    assert r["avoid"]["reason"].startswith("Most likely to be wet:") and r["avoid"]["reason"].endswith("Rain likely (80%).")


def test_quietest_picks_the_lowest_blocks(result):
    r = result["recommendations"]["quietest"]
    assert span(r["best"]) == "15-17"
    assert span(r["secondBest"]) == "9-11"  # 14-16 and 16-18 overlap the best
    assert span(r["avoid"]) == "12-14"


def test_recommendations_never_overlap_and_never_say_people(result):
    for preset in (result["recommendations"][name] for name in PRESETS):
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
    assert "No rain forecast" in dry["recommendations"]["busyButDry"]["best"]["reason"]


def test_ties_go_to_the_earlier_block():
    flat = [{**f, "predicted": 100} for f in FORECASTS]
    r = plan(flat, [], NOW, sensor=7)["recommendations"]
    assert span(r["mostTraffic"]["best"]) == span(r["quietest"]["best"]) == "7-9"
    assert span(r["mostTraffic"]["secondBest"]) == "9-11"


def at(hour: int, sensor: int, predicted: float, baseline: float | None) -> dict:
    return {"sensorId": sensor, "ms": ms(TUESDAY, hour), "predicted": predicted, "baseline": baseline}


def test_cbd_total_uses_the_same_sensors_for_forecast_and_typical_in_every_hour():
    forecasts = (
        [at(h, 1, 100, 80) for h in (6, 7, 8)]
        + [at(h, 2, 200, 150) for h in (6, 7, 8)]
        # Sensor 3 has no typical at 07:00, sensor 4 has no forecast at 08:00: neither is used anywhere.
        + [at(6, 3, 1000, 900), at(7, 3, 1000, None), at(8, 3, 1000, 900)]
        + [at(6, 4, 5000, 4000), at(7, 4, 5000, 4000)]
    )
    out = plan(forecasts, [], NOW)
    assert out["sensorsUsed"] == 2
    assert [(h["forecastCount"], h["typicalCount"], h["deltaPct"]) for h in out["hours"]] == [(300, 230, 30.4)] * 3

    # With every sensor complete, all four are used, in every hour.
    whole = [f if f["baseline"] is not None else {**f, "baseline": 900} for f in forecasts] + [at(8, 4, 5000, 4000)]
    out = plan(whole, [], NOW)
    assert out["sensorsUsed"] == 4
    assert [(h["forecastCount"], h["typicalCount"]) for h in out["hours"]] == [(6300, 5130)] * 3


def test_a_leftover_hour_from_an_old_run_does_not_shrink_the_cbd_total():
    forecasts = [at(h, s, 100, 100) for h in (6, 7, 8) for s in (1, 2, 3, 4)] + [at(9, 1, 100, 100)]
    out = plan(forecasts, [], NOW)
    assert out["sensorsUsed"] == 4
    assert [h["hourLocal"][11:13] for h in out["hours"]] == ["06", "07", "08"]  # 09:00 has 1 of 4 sensors


def test_one_sensor_reports_itself_and_keeps_hours_without_a_typical():
    out = plan([at(6, 7, 40, None), at(7, 7, 50, 40), at(7, 8, 999, 999)], [], NOW, sensor=7)
    assert out["sensorsUsed"] == 1
    assert [(h["forecastCount"], h["typicalCount"], h["deltaPct"]) for h in out["hours"]] == [(40, None, None), (50, 40, 25)]
    assert plan([], [], NOW)["sensorsUsed"] == 0


def snapshot(**overrides) -> dict:
    base = {
        "readAt": "2026-10-05T18:10:00.000Z",
        "forecasts": FORECASTS,
        "weather": WEATHER,
        "sensors": [{"location_id": 7, "name": "Town Hall (West)", "lat": -37.81, "lon": 144.96}],
        "rain": [
            {"scope": "overall", "key": "all", "effect": -0.185, "ciLow": -0.218, "ciHigh": -0.144,
             "nWetHours": 876, "reliable": True},
            {"scope": "sensor", "key": "7", "effect": -0.05, "ciLow": -0.12, "ciHigh": 0.02,
             "nWetHours": 876, "reliable": False},
        ],
        "rainProfile": [],
        "rainMethod": None,
        "rainWindow": {"start": "2025-09-30", "end": "2026-09-29"},
        "latestWrite": {
            "forecasts": "2026-10-04T17:44:00.000Z",
            "weather": "2026-10-05T18:07:00.000Z",
            "rainEffect": "2026-10-01T17:13:00.000Z",
        },
    }
    return {**base, **overrides}


def test_data_freshness_is_each_tables_latest_write_and_the_snapshot_time():
    out = response(snapshot(), NOW)
    assert out["dataFreshness"] == {
        "forecastGeneratedAt": "2026-10-04T17:44:00.000Z",
        "weatherFetchedAt": "2026-10-05T18:07:00.000Z",
        "rainEffectComputedAt": "2026-10-01T17:13:00.000Z",
        "snapshotAt": "2026-10-05T18:10:00.000Z",
    }
    assert out["sensor"] == "cbd" and out["sensorsUsed"] == 1 and out["generatedAt"] == "2026-10-05T18:30:00.000Z"

    # A later write to a table shows up, even when the rows for these hours are identical.
    newer = snapshot(readAt="2026-10-05T19:10:00.000Z",
                     latestWrite={"forecasts": None, "weather": "2026-10-05T19:07:00.000Z", "rainEffect": None})
    again = response(newer, NOW)
    assert again["dataFreshness"]["weatherFetchedAt"] == "2026-10-05T19:07:00.000Z"
    assert again["dataFreshness"]["forecastGeneratedAt"] is None
    assert again["dataFreshness"]["snapshotAt"] == "2026-10-05T19:10:00.000Z"


def test_the_same_snapshot_always_gives_the_same_hours():
    first = response(snapshot(), NOW, window="36h")
    later = response(snapshot(), datetime(2026, 10, 5, 18, 55, tzinfo=timezone.utc), window="36h")  # same hour, later
    assert first["hours"] == later["hours"] and first["recommendations"] == later["recommendations"]
    assert first["dataFreshness"] == later["dataFreshness"]
    # An hour later the window has moved on by one hour; every hour both responses share is identical.
    next_hour = response(snapshot(), datetime(2026, 10, 5, 19, 5, tzinfo=timezone.utc), window="36h")
    assert next_hour["hours"] == first["hours"][1:]


def test_a_sensor_without_a_reliable_rain_effect_falls_back_to_the_cbd_one():
    out = response(snapshot(), NOW, sensor=7)
    assert out["sensor"]["name"] == "Town Hall (West)"
    assert out["rainEffect"] == {"value": -18.5, "ciLow": -21.8, "ciHigh": -14.4, "nWetHours": 876,
                                 "reliable": True, "usedFallback": True, "scope": "cbd"}
    assert response(snapshot(), NOW, sensor=999) is None  # no forecast for that id


@pytest.mark.parametrize(
    "chance, wording",
    [(0, "Low rain risk (0%)"), (29, "Low rain risk (29%)"), (30, "Some rain risk (30%)"),
     (49, "Some rain risk (49%)"), (50, "Rain likely (50%)"), (88, "Rain likely (88%)")],
)
def test_rain_wording_follows_the_highest_chance_and_always_shows_it(chance, wording):
    weather = [{**w, "precipProb": chance, "precipMm": 0.0} for w in WEATHER]
    recs = plan(FORECASTS, weather, NOW, sensor=7)["recommendations"]
    for preset in PRESETS:
        for rec in recs[preset].values():
            assert rec["reason"].endswith(f". {wording}.") and "unlikely" not in rec["reason"].lower()
            assert rec["maxPrecipProb"] == chance


def test_hours_considered_is_the_real_range_the_blocks_came_from(result):
    # 06:00-17:00 was forecast, but blocks are only offered inside 7am-10pm.
    assert result["recommendations"]["hoursConsidered"] == {
        "from": "2026-10-06T07:00:00+11:00", "to": "2026-10-06T18:00:00+11:00", "daytimeOnly": True}
    starts = [r["start"] for name in PRESETS for r in result["recommendations"][name].values()]
    ends = [r["end"] for name in PRESETS for r in result["recommendations"][name].values()]
    assert min(starts) >= "2026-10-06T07:00:00+11:00" and max(ends) <= "2026-10-06T18:00:00+11:00"
    assert plan([], [], NOW)["recommendations"]["hoursConsidered"] is None


def test_late_evening_falls_back_to_the_hours_there_are():
    late = datetime(2026, 10, 6, 10, 30, tzinfo=timezone.utc)  # Tue 21:30 AEDT
    forecasts = [{"sensorId": 7, "ms": ms(TUESDAY, h), "predicted": 40, "baseline": 50} for h in (22, 23)]
    today = plan(forecasts, [], late, window="today", sensor=7)
    assert [h["hourLocal"][11:13] for h in today["hours"]] == ["22", "23"]
    r = today["recommendations"]["quietest"]
    assert span(r["best"]) == "22-24" and r["secondBest"] is None and r["avoid"] is None
    assert today["recommendations"]["hoursConsidered"] == {
        "from": "2026-10-06T22:00:00+11:00", "to": "2026-10-07T00:00:00+11:00", "daytimeOnly": False}

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


def test_landing_page_rain_outlook_matches_the_summary_rule():
    """web/lib/plan-core.ts rainOutlook: first rain-risk hour in the next 12, with the same thresholds as summary.py."""
    def outlook(by_hour: dict[int, tuple[float | None, float | None]], hours=12):
        weather = [
            {"ms": ms(TUESDAY, h), "precipProb": by_hour.get(h, (10, 0.0))[0], "precipMm": by_hour.get(h, (10, 0.0))[1],
             "tempC": 15, "windKmh": 10, "weatherCode": 3}
            for h in range(5, 24)
        ]
        return run({"rain": {"weather": weather, "nowMs": int(NOW.timestamp() * 1000), "hours": hours}})

    assert outlook({}) is None
    assert outlook({15: (80, 1.2), 16: (65, 0.4)}) == {"startMs": ms(TUESDAY, 15), "startLabel": "3pm", "maxProb": 80}
    assert outlook({9: (20, 0.2)})["startLabel"] == "9am"  # by amount
    assert outlook({9: (49, 0.1)}) is None  # just under both thresholds
    assert outlook({5: (90, 2.0)})["startLabel"] == "now"  # the hour in progress (NOW is 05:30)
    assert outlook({17: (90, 2.0)}) is None  # 12 hours from 05:00 ends at 17:00
    assert outlook({17: (90, 2.0)}, hours=13)["startLabel"] == "5pm"
