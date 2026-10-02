from datetime import date, timedelta

import pytest

import audit
import summary
from conftest import utc
from feed_quality import typicals
from pulse import quality
from pulse.quality import HeavyRain, Quality, assess
from pulse.timeutil import local
from test_summary import PARKING, PEDESTRIAN, SENSORS

HOUR = utc(2026, 10, 1, 5)  # Thu 1 Oct, 3pm AEST
DAY = date(2026, 10, 1)
TYPICAL = {lid: 1000.0 for lid in range(1, 101)}  # 100 sensors, typically 1,000 an hour each
HEAVY = HeavyRain(mm=2.0, ci_low=-0.366)


def counts(low: int, level: int = 400) -> dict[int, int]:
    """`low` sensors at `level`, the other sensors at their typical 1,000."""
    return {lid: (level if lid <= low else 1000) for lid in TYPICAL}


def flagged(hour=HOUR - timedelta(hours=1)) -> Quality:
    return Quality(hour, 100, 80, True, "low_counts")


def test_most_sensors_under_half_their_typical_is_an_anomaly():
    q = assess(HOUR, DAY, counts(60), TYPICAL)
    assert q.anomaly and q.reason == "low_counts" and (q.judged, q.low, q.share) == (100, 60, 0.6)
    q = assess(HOUR, DAY, counts(59), TYPICAL)
    assert not q.anomaly and q.reason == "ok" and q.share == 0.59  # 59% is under the line


def test_low_means_under_half_not_merely_quiet():
    assert not assess(HOUR, DAY, counts(100, level=500), TYPICAL).anomaly  # exactly half is not "under half"
    assert assess(HOUR, DAY, counts(100, level=499), TYPICAL).anomaly
    # A rainy afternoon: every sensor 30% down is a real change, not a fault.
    assert assess(HOUR, DAY, counts(100, level=700), TYPICAL).low == 0


def test_heavy_rain_lowers_the_bar_by_what_heavy_rain_can_explain():
    # In heavy rain a sensor is only "low" under 0.5 x (1 - 0.366) = 31.7% of typical.
    q = assess(HOUR, DAY, counts(100, level=400), TYPICAL, rain_mm=3.8, heavy=HEAVY)
    assert not q.anomaly and q.low == 0 and q.heavy_rain  # 40% of typical: heavy rain can explain it
    q = assess(HOUR, DAY, counts(70, level=250), TYPICAL, rain_mm=3.8, heavy=HEAVY)
    assert q.anomaly and q.low == 70 and q.heavy_rain  # 25% of typical: rain cannot
    # Light rain gets no allowance, and neither does heavy rain we have no measurement for.
    assert assess(HOUR, DAY, counts(100, level=400), TYPICAL, rain_mm=1.9, heavy=HEAVY).anomaly
    assert assess(HOUR, DAY, counts(100, level=400), TYPICAL, rain_mm=3.8, heavy=None).anomaly
    assert assess(HOUR, DAY, counts(100, level=400), TYPICAL, rain_mm=None, heavy=HEAVY).anomaly


def test_a_public_holiday_is_never_an_anomaly():
    q = assess(HOUR, DAY, counts(90), TYPICAL, is_public_holiday=lambda day: day == DAY)
    assert not q.anomaly and q.reason == "public_holiday" and q.low == 90  # the share is still recorded


def test_an_anomaly_holds_through_a_middling_hour_and_ends_when_sensors_recover():
    assert assess(HOUR, DAY, counts(25), TYPICAL, previous=flagged()).reason == "holding"  # 25% still low
    q = assess(HOUR, DAY, counts(24), TYPICAL, previous=flagged())
    assert not q.anomaly and q.reason == "ok"
    assert not assess(HOUR, DAY, counts(40), TYPICAL).anomaly  # 40% alone doesn't start one
    assert not assess(HOUR, DAY, counts(40), TYPICAL, previous=Quality(HOUR, 100, 2, False, "ok")).anomaly


def test_quiet_sensors_are_not_judged_and_an_unjudgeable_hour_inherits_the_last_state():
    night_typical = {lid: (40.0 if lid <= 10 else 5.0) for lid in range(1, 101)}
    night = {lid: 1 for lid in night_typical}
    q = assess(HOUR, DAY, night, night_typical)
    assert (q.judged, q.anomaly, q.reason) == (10, False, "too_few_sensors")  # only 10 sensors have a typical of 30+
    assert assess(HOUR, DAY, night, night_typical, previous=flagged()).anomaly  # stays flagged overnight
    # A sensor with no typical, or that hasn't finished reporting (absent from counts), is not judged.
    assert assess(HOUR, DAY, {1: 0, 2: 0, 999: 0}, TYPICAL).judged == 2


def test_typical_for_the_check_leaves_out_hours_already_flagged():
    thursdays_3pm = [HOUR - timedelta(weeks=k) for k in range(1, 9)]
    history = {(3, 15): {7: {(local(h).date(), h): value for h, value in zip(thursdays_3pm, [100, 900, 900, 900, 900, 900, 900, 900])}}}
    assert typicals(history, set(), HOUR) == {7: 900.0}
    history[(3, 15)][7] = {(local(h).date(), h): value for h, value in zip(thursdays_3pm, [100, 100, 900, 900])}
    assert typicals(history, set(), HOUR) == {7: 500.0}
    assert typicals(history, {thursdays_3pm[0], thursdays_3pm[1]}, HOUR) == {7: 900.0}  # the two faulty weeks are ignored


def test_ranges_joins_consecutive_flagged_hours():
    hours = [Quality(HOUR + timedelta(hours=i), 100, low, low >= 25, "x") for i, low in enumerate([70, 28, 49, 10, 65])]
    assert quality.ranges(hours) == [(HOUR, HOUR + timedelta(hours=2), 0.7), (HOUR + timedelta(hours=4), HOUR + timedelta(hours=4), 0.65)]


# ------------------------------------------------------------ what the site says

ANOMALY = {"judged": 96, "low": 67, "share": 0.7, "reason": "low_counts"}


def test_during_an_anomaly_the_sentence_is_the_warning_and_makes_no_comparison(monkeypatch):
    stats = summary.build_stats(PEDESTRIAN, SENSORS, PARKING, anomaly=ANOMALY)
    assert stats["vs_typical_pct"] is None  # no percentage against typical is even computed
    assert stats["pedestrians"] == 2400  # the raw count is kept
    assert stats["feed_anomaly"] == {"share": 0.7, "judged": 96, "low": 67}

    monkeypatch.setattr(summary, "ask_gemini", lambda _: pytest.fail("Gemini must not be asked during an anomaly"))
    result = summary.compose(stats)
    assert result["source"] == "template"
    assert result["text"] == (
        "Foot traffic is far below normal across most sensors. "
        "This may be severe weather, a major event, or a sensor feed issue."
    )
    # It doesn't assume a fault, quote a comparison, or call the counts "people".
    assert "quieter" not in result["text"] and "%" not in result["text"] and "people" not in result["text"]
    assert "looks unusual" not in result["text"] and "incomplete" not in result["text"]


def test_without_an_anomaly_the_sentence_is_unchanged():
    stats = summary.build_stats(PEDESTRIAN, SENSORS, PARKING, anomaly=None)
    assert "feed_anomaly" not in stats and stats["vs_typical_pct"] == 17
    assert summary.template(stats).startswith("Melbourne's CBD is 17% busier than a typical Thursday at 1pm")


# ------------------------------------------------- audit: ours against the city's hourly data


def test_audit_reports_hours_where_our_total_differs_from_the_citys():
    h1, h2, h3 = HOUR, HOUR + timedelta(hours=1), HOUR + timedelta(hours=2)
    ours = {h1: {1: 500, 2: 470, 3: 10}, h2: {1: 200, 2: 100}, h3: {1: 300}}
    city = {h1: {1: 500, 2: 500}, h2: {1: 500, 2: 400}}  # the city hasn't published h3 yet
    rows = audit.compare_hours(ours, city, flagged={h2})
    assert [r["hour"] for r in rows] == [h1, h2]  # only hours both have
    assert (rows[0]["ours"], rows[0]["city"], rows[0]["sensors"], rows[0]["mismatch"]) == (970, 1000, 2, False)  # 3% under: within tolerance
    assert (rows[1]["ours"], rows[1]["city"], rows[1]["mismatch"], rows[1]["flagged"]) == (300, 900, True, True)
    assert rows[1]["gap"] == pytest.approx(-2 / 3)


# ----------------------------------------------- the website's wording (web/lib/feed-anomaly.ts)

import json  # noqa: E402
import subprocess  # noqa: E402

from test_plan_recommendations import WEB, node_version  # noqa: E402

needs_node = pytest.mark.skipif(node_version() < (22, 18), reason="needs Node 22.18+ to run web/lib/feed-anomaly.ts")
STORED = "Melbourne's CBD is 60% quieter than a typical Friday at 1am, and 66% of parking bays are free."
LIVE = [{"location_id": 3, "count": 12, "typical": 40}, {"location_id": 5, "count": 9, "typical": None}]


def site(anomaly):
    done = subprocess.run(
        ["node", "scripts/feed-anomaly-check.mjs"], cwd=WEB, capture_output=True, text=True, timeout=60,
        input=json.dumps({"summary": STORED, "anomaly": anomaly, "sensors": LIVE}),
    )
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


@needs_node
def test_the_site_replaces_the_headline_and_withholds_every_comparison_during_an_anomaly():
    flagged = site({"sensorsJudged": 96, "sensorsLow": 67, "shareLow": 0.7})
    assert flagged["headline"] == summary.FEED_ANOMALY_TEXT == flagged["text"]  # one wording, pipeline and site
    assert "quieter" not in flagged["headline"] and "%" not in flagged["headline"]
    # Raw counts stay; the typical each comparison would need is gone.
    assert [(s["location_id"], s["count"], s["typical"]) for s in flagged["sensors"]] == [(3, 12, None), (5, 9, None)]
    assert flagged["countNote"] == summary.FEED_ANOMALY_TEXT  # the stat card carries the same sentence
    # A withheld comparison says it is paused; it does not claim the sensor has no baseline.
    assert flagged["labels"] == ["Comparison paused", "comparison paused", "Comparison paused", "comparison paused"]


@needs_node
def test_the_site_is_unchanged_when_the_hour_is_not_flagged():
    normal = site(None)
    assert normal["headline"] == STORED and normal["sensors"] == LIVE
    assert normal["labels"] == ["No baseline yet", "no baseline yet", "No baseline", "n/a"]  # a real missing baseline


# ------------------------------------- resolving a flagged hour against the city's figures

import feed_quality  # noqa: E402
import rain_effect  # noqa: E402


def compared(ours: int, city: int, flagged: bool = True, hour=HOUR) -> dict:
    return audit.compare_hours({hour: {1: ours}}, {hour: {1: city}}, {hour} if flagged else set())[0]


def test_a_flagged_hour_is_real_if_the_city_agrees_and_a_fault_if_we_are_well_below():
    assert audit.resolution(compared(1000, 1000)) == "confirmed_real"
    assert audit.resolution(compared(950, 1000)) == "confirmed_real"  # 5% under: within tolerance
    assert audit.resolution(compared(1050, 1000)) == "confirmed_real"  # 5% over
    assert audit.resolution(compared(949, 1000)) == "confirmed_fault"  # more than 5% below the city's
    assert audit.resolution(compared(300, 1000)) == "confirmed_fault"
    assert audit.resolution(compared(1100, 1000)) is None  # above the city's: neither story fits
    assert audit.resolution(compared(300, 1000, flagged=False)) is None  # only flagged hours are resolved


class QualityTable:
    """feed_quality as a dict, with just the two statements resolve() and assess_range() use."""

    def __init__(self, rows: dict):
        self.rows = rows  # hour -> {"anomaly": bool, "resolution": str | None}
        self.depth = 0

    def transaction(self):
        return self

    def __enter__(self):
        self.depth += 1
        return self

    def __exit__(self, *_):
        self.depth -= 1
        return False

    def execute(self, sql, params=None):
        assert "update feed_quality set resolution" in sql and self.depth == 1
        verdict, anomaly, hour = params
        row = self.rows.get(hour)
        hit = row is not None and row["resolution"] is None  # "where ... resolution is null"
        if hit:
            row.update(resolution=verdict, anomaly=anomaly)
        return type("Result", (), {"rowcount": int(hit)})()


def test_resolving_unflags_real_hours_keeps_faults_flagged_and_is_final():
    h1, h2, h3, h4 = (HOUR + timedelta(hours=i) for i in range(4))
    table = QualityTable({h: {"anomaly": True, "resolution": None} for h in (h1, h2, h3)})
    table.rows[h4] = {"anomaly": True, "resolution": "confirmed_fault"}  # settled on an earlier day
    hours = [compared(980, 1000, hour=h1), compared(400, 1000, hour=h2), compared(1000, 1000, flagged=False, hour=h3),
             compared(1000, 1000, hour=h4)]

    assert audit.resolve(table, hours) == {"confirmed_real": 1, "confirmed_fault": 1}
    assert table.rows[h1] == {"anomaly": False, "resolution": "confirmed_real"}  # counts as normal data again
    assert table.rows[h2] == {"anomaly": True, "resolution": "confirmed_fault"}  # stays excluded
    assert table.rows[h3] == {"anomaly": True, "resolution": None}  # not offered as flagged: untouched
    assert table.rows[h4] == {"anomaly": True, "resolution": "confirmed_fault"}  # a resolution is never overwritten
    assert audit.resolve(table, hours) == {"confirmed_real": 0, "confirmed_fault": 0}  # running it again changes nothing


class StoredCounts:
    """Answers assess_range's three reads from fixed data."""

    def __init__(self, counts, quality_rows, heavy=None):
        self.counts, self.quality_rows, self.heavy = counts, quality_rows, heavy

    def execute(self, sql, params=None):
        if "from pedestrian_hourly" in sql:
            rows = self.counts
        elif "from feed_quality" in sql:
            assert "resolution is not null" in sql  # resolved hours are always loaded
            rows = self.quality_rows
        else:
            rows = []  # no rain_effect row
        return type("Result", (), {"fetchall": lambda _: rows, "fetchone": lambda _: None, "__iter__": lambda _: iter(rows)})()


def test_a_backfill_never_re_flags_an_hour_the_audit_confirmed_as_real():
    weeks = [HOUR + timedelta(hours=i) - timedelta(weeks=k) for k in range(1, 9) for i in range(3)]
    counts = [(lid, h, 1000) for h in weeks for lid in range(1, 41)]  # 40 sensors, typically 1,000
    now_hours = [HOUR + timedelta(hours=i) for i in range(3)]
    counts += [(lid, h, 100) for h in now_hours for lid in range(1, 41)]  # all three hours collapse
    resolved_real = (now_hours[1], 40, 40, False, "low_counts", False)  # the audit unflagged the middle one

    fresh = feed_quality.assess_range(StoredCounts(counts, []), now_hours[0], now_hours[2], {})
    assert [q.anomaly for q in fresh] == [True, True, True]

    kept = feed_quality.assess_range(StoredCounts(counts, [resolved_real]), now_hours[0], now_hours[2], {})
    assert [q.hour for q in kept] == [now_hours[0], now_hours[2]]  # the resolved hour is not re-assessed or rewritten
    assert [q.reason for q in kept] == ["low_counts", "low_counts"]  # and the hour after it starts afresh, not "holding"


class FlagRows:
    """feed_quality rows as (hour, anomaly, resolution); answers a select the way Postgres would."""

    def __init__(self, rows):
        self.rows = rows

    def execute(self, sql, params=None):
        assert "from feed_quality where anomaly" in sql
        unresolved_only = "resolution is null" in sql
        return [(hour,) for hour, anomaly, resolution in self.rows if anomaly and (resolution is None or not unresolved_only)]


def test_rain_effect_leaves_out_only_unresolved_hours():
    storm, fault, pending = HOUR, HOUR + timedelta(hours=1), HOUR + timedelta(hours=2)
    table = FlagRows([(storm, False, "confirmed_real"), (fault, True, "confirmed_fault"), (pending, True, None)])
    rows = [(1, DAY, 15, storm, 300), (2, DAY, 15, storm, 280), (1, DAY, 16, fault, 700), (1, DAY, 17, pending, 10)]

    flagged = rain_effect.flagged_hours(table)
    assert flagged == {pending}  # a resolved hour is used whichever way it was resolved
    kept = rain_effect.without_flagged(rows, flagged)
    # The real storm stays in as rain evidence, and so does the fault hour: these rows are the
    # city's final figures, which were right even though our live table was short.
    assert [r[3] for r in kept] == [storm, storm, fault]
    assert rain_effect.without_flagged(rows, set()) == rows


def test_the_site_still_treats_a_confirmed_fault_as_flagged():
    """The website compares against our live table, where a fault hour really is incomplete."""
    import inspect

    from pulse import db

    # The site's typical and its notice read `anomaly` alone, so confirmed_fault (anomaly = true) stays out...
    assert "q.anomaly)" in inspect.getsource(db.typicals_for) and "resolution" not in inspect.getsource(db.typicals_for)
    assert "and anomaly" in inspect.getsource(db.feed_anomaly) and "resolution" not in inspect.getsource(db.feed_anomaly)
    # ...and resolving a fault keeps anomaly true.
    table = QualityTable({HOUR: {"anomaly": True, "resolution": None}})
    audit.resolve(table, [compared(400, 1000)])
    assert table.rows[HOUR] == {"anomaly": True, "resolution": "confirmed_fault"}


def test_seeded_hours_are_never_resolved_automatically():
    """Before the live feed started, our table was copied from the city's dataset: agreement proves nothing."""
    first_live = audit.LIVE_FEED_SINCE
    assert first_live == utc(2026, 9, 30, 5)  # Wed 30 Sep 2026, 3pm in Melbourne
    grand_final = utc(2026, 9, 26, 2)  # Sat 26 Sep, 12pm: seeded, and flagged by the backfill
    last_seeded = first_live - timedelta(hours=1)

    assert audit.resolution(compared(1000, 1000, hour=grand_final)) is None  # "agrees", but circular
    assert audit.resolution(compared(300, 1000, hour=grand_final)) is None  # nor is it called a fault
    assert audit.resolution(compared(1000, 1000, hour=last_seeded)) is None
    assert audit.resolution(compared(1000, 1000, hour=first_live)) == "confirmed_real"  # the first live hour is fair game

    table = QualityTable({h: {"anomaly": True, "resolution": None} for h in (grand_final, first_live)})
    done = audit.resolve(table, [compared(1000, 1000, hour=grand_final), compared(1000, 1000, hour=first_live)])
    assert done == {"confirmed_real": 1, "confirmed_fault": 0}
    assert table.rows[grand_final] == {"anomaly": True, "resolution": None}  # left flagged
    assert table.rows[first_live] == {"anomaly": False, "resolution": "confirmed_real"}
