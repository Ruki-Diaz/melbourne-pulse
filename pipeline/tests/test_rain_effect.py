from datetime import date, datetime, timedelta, timezone

import numpy as np
import pytest

import rain_effect
from pulse.history import complete_days
from pulse.timeutil import local_hour_to_utc
from rain_effect import build_table, compute, is_day_off, reliable, window_for

JULY = (date(2026, 7, 1), date(2026, 7, 31))


def row(day: date, hour: int, count: int, sensor: int = 1):
    return (sensor, day, hour, local_hour_to_utc(day, hour), count)


def weather(rain: dict[tuple[date, int], float], temps: dict[date, float] | None = None, days=JULY):
    """Observed weather for every hour of `days`: dry and 15 C unless listed."""
    out, day = [], days[0]
    while day <= days[1]:
        for hour in range(24):
            stamp = local_hour_to_utc(day, hour)
            if stamp is not None:
                out.append(
                    {"hour": stamp, "precipitation": rain.get((day, hour), 0.0), "temperature": (temps or {}).get(day, 15.0)}
                )
        day += timedelta(days=1)
    return out


def d(day: int) -> date:
    return date(2026, 7, day)


# One sensor, July 2026. 1-3 and 6-7 July are weekdays; 4-5 and 11-12 are a weekend.
#   weekday 12:00  dry 100, 110, 90 (mean 100)   wet 80 (light), 60 (heavy)
#   weekend 12:00  dry 50, 50, 50   (mean 50)    wet 25 (light)
#   weekday 13:00  dry 40, 60 only -> too few dry hours, so its wet hour (5) is left out
HAND_MADE = [
    row(d(1), 12, 100), row(d(2), 12, 110), row(d(3), 12, 90), row(d(6), 12, 80), row(d(7), 12, 60),
    row(d(4), 12, 50), row(d(5), 12, 50), row(d(11), 12, 50), row(d(12), 12, 25),
    row(d(1), 13, 40), row(d(2), 13, 60), row(d(6), 13, 5),
]  # fmt: skip
RAIN = {(d(6), 12): 1.0, (d(7), 12): 3.0, (d(12), 12): 0.2, (d(6), 13): 1.0}
TEMPS = {d(6): 10.0, d(7): 15.0, d(12): 25.0}


def results(rows=HAND_MADE, rain=RAIN, temps=TEMPS, window=JULY, **kwargs):
    table = build_table(rows, weather(rain, temps), *window)
    return {(r["scope"], r["key"]): r for r in compute(table, **kwargs)}


def test_matched_effect_on_a_hand_made_fixture():
    r = results(reps=20)
    # overall: actual 80 + 60 + 25 = 165 against expected 100 + 100 + 50 = 250
    assert r[("overall", "all")]["effect"] == pytest.approx(165 / 250 - 1)
    assert r[("overall", "all")]["n_wet_hours"] == 3
    assert r[("intensity", "light")]["effect"] == pytest.approx((80 + 25) / 150 - 1)  # 0.2 mm counts as wet
    assert r[("intensity", "heavy")]["effect"] == pytest.approx(60 / 100 - 1)  # 3 mm
    assert r[("daytype", "weekday")]["effect"] == pytest.approx(140 / 200 - 1)
    assert r[("daytype", "weekend")]["effect"] == pytest.approx(25 / 50 - 1)
    assert r[("temperature", "cold")]["effect"] == pytest.approx(80 / 100 - 1)  # 10 C
    assert r[("temperature", "mild")]["effect"] == pytest.approx(60 / 100 - 1)  # 15 C
    assert r[("temperature", "warm")]["effect"] == pytest.approx(25 / 50 - 1)  # 25 C
    assert r[("sensor", "1")]["effect"] == pytest.approx(165 / 250 - 1)
    assert r[("profile", "cbd")]["detail"] == [{"hour": 12, "wet": 55.0, "dry": 83.3, "n_wet_hours": 3}]


def test_a_cell_needs_three_dry_hours():
    # With a third dry 13:00 the left-out wet hour (5 against a mean of 50) joins in.
    r = results(rows=HAND_MADE + [row(d(3), 13, 50)], reps=5)
    assert r[("overall", "all")]["effect"] == pytest.approx(170 / 300 - 1)
    assert r[("overall", "all")]["n_wet_hours"] == 4  # was 3 while that hour was left out
    r = results(rows=HAND_MADE + [row(d(3), 13, 50)], rain={**RAIN, (d(6), 13): 0.1}, reps=5)
    assert r[("overall", "all")]["effect"] != pytest.approx(170 / 300 - 1)  # 0.1 mm is not wet


def test_wet_hours_are_real_hours_not_sensor_hours():
    two_sensors = HAND_MADE + [row(r[1], r[2], r[4] * 2, sensor=2) for r in HAND_MADE]
    r = results(rows=two_sensors, reps=5)
    assert r[("overall", "all")]["n_wet_hours"] == 3
    assert r[("sensor", "2")]["effect"] == pytest.approx(165 / 250 - 1)


def test_public_holidays_count_as_weekend():
    assert is_day_off(date(2026, 11, 3))  # Melbourne Cup Day, a Tuesday
    assert is_day_off(date(2026, 7, 4)) and not is_day_off(date(2026, 7, 6))


def noisy_year(seed=3, days=120, effect=-0.2):
    """Two sensors, hours 9-17, for `days` days from 1 March; every 4th day is wet all day."""
    rng = np.random.default_rng(seed)
    rows, rain = [], {}
    for i in range(days):
        day = date(2026, 3, 1) + timedelta(days=i)
        for hour in range(9, 18):
            if i % 4 == 0:
                rain[(day, hour)] = 1.0
            for sensor in (1, 2):
                base = 200 * sensor * (1 + effect if i % 4 == 0 else 1)
                rows.append(row(day, hour, int(base * rng.uniform(0.8, 1.2)), sensor))
    span = (date(2026, 3, 1), date(2026, 3, 1) + timedelta(days=days - 1))
    return build_table(rows, weather(rain, days=span), *span)


def test_bootstrap_is_deterministic_and_brackets_the_estimate():
    table = noisy_year()
    first = {(r["scope"], r["key"]): r for r in compute(table, reps=60)}
    again = {(r["scope"], r["key"]): r for r in compute(table, reps=60)}
    assert first == again  # same seed, same intervals

    overall = first[("overall", "all")]
    assert overall["ci_low"] < overall["effect"] < overall["ci_high"]
    assert overall["effect"] == pytest.approx(-0.2, abs=0.03)
    assert overall["n_wet_hours"] == 30 * 9 and overall["reliable"]

    other_seed = {(r["scope"], r["key"]): r for r in compute(table, reps=60, seed=1)}
    assert other_seed[("overall", "all")]["effect"] == overall["effect"]  # the estimate doesn't depend on the seed
    assert other_seed[("overall", "all")]["ci_low"] != overall["ci_low"]


def test_bootstrap_resamples_whole_days():
    """Every hour of a day shares one weight, so a resample can't split a day."""
    table = noisy_year(days=40)
    weights = np.zeros(len(table.days))
    weights[::4] = 2.0  # only the wet days, twice each: no dry hours are left
    actual, expected, used = rain_effect.matched(table, weights)
    assert not used.any() and actual.sum() == 0 and expected.sum() == 0


def test_trust_rule():
    assert reliable(100, -0.30, -0.10)
    assert not reliable(99, -0.30, -0.10)  # too few wet hours
    assert not reliable(500, -0.10, 0.05)  # interval includes zero
    assert not reliable(500, -0.10, 0.0)
    assert reliable(500, 0.02, 0.20)  # an increase (e.g. an indoor sensor) can be reliable too
    assert not reliable(500, None, None)


def test_few_wet_hours_are_stored_but_not_reliable():
    r = results(reps=50)
    assert r[("overall", "all")]["n_wet_hours"] == 3 and not r[("overall", "all")]["reliable"]


def test_window_is_the_12_months_ending_on_the_last_day():
    assert window_for(date(2026, 9, 29)) == (date(2025, 9, 30), date(2026, 9, 29))
    assert window_for(date(2026, 12, 31)) == (date(2026, 1, 1), date(2026, 12, 31))
    assert window_for(date(2024, 2, 29)) == (date(2023, 3, 1), date(2024, 2, 29))  # leap day
    start, end = window_for(date(2026, 9, 29))
    assert (end - start).days + 1 == 365


def test_rows_outside_the_window_are_ignored():
    start, end = date(2026, 7, 2), date(2026, 7, 11)
    table = build_table(HAND_MADE, weather(RAIN, TEMPS), start, end)
    assert table.days[0] == start and table.days[-1] == end  # 1 July and 12 July are gone
    assert len(table.count) == len([r for r in HAND_MADE if start <= r[1] <= end])


def test_window_ends_on_the_newest_day_with_counts_and_weather():
    rows = [row(d(day), hour, 10) for day in (1, 2, 3) for hour in range(24)]
    full = weather({})
    assert rain_effect.last_full_day(rows, full) == d(3)
    # The archive hasn't published 3 July's last hours yet.
    late = local_hour_to_utc(d(3), 20)
    partial = [{**w, "precipitation": None} if w["hour"] >= late else w for w in full]
    assert rain_effect.last_full_day(rows, partial) == d(2)


@pytest.mark.parametrize(
    "change_day, hours",
    [(date(2026, 10, 4), 23), (date(2026, 4, 5), 23)],  # spring: no 02:00; autumn: repeated 02:00 dropped
)
def test_weather_joins_on_the_real_hour_across_a_dst_change(change_day, hours):
    days = (change_day - timedelta(days=1), change_day + timedelta(days=1))
    counts = complete_days(
        (1, days[0] + timedelta(days=i), hour, 10) for i in range(3) for hour in range(24)
    )
    # Weather for every real hour, with the rain amount encoding which hour it is.
    first = datetime.combine(days[0] - timedelta(days=1), datetime.min.time(), timezone.utc)
    stamps = [first + timedelta(hours=i) for i in range(24 * 5)]
    observed = [{"hour": s, "precipitation": s.timestamp() / 3600, "temperature": 15.0} for s in stamps]

    table = build_table(counts, observed, *days)
    assert len(table.count) == len(counts) == 24 + hours + 24
    np.testing.assert_array_equal(table.precip, [r[3].timestamp() / 3600 for r in counts])
    assert sorted(table.hour[table.day == 1]) == [h for h in range(24) if h != 2]


class FakeDatabase:
    """Just enough of psycopg to check save(): rows change only if the transaction block finishes."""

    def __init__(self, rows, fail_after=None):
        self.rows, self.fail_after = list(rows), fail_after
        self.pending, self.depth, self.outside = None, 0, []

    def transaction(self):
        return self

    def cursor(self):
        return self

    def __enter__(self):
        if self.depth == 0 and self.pending is None:
            self.pending = list(self.rows)
        self.depth += 1
        return self

    def __exit__(self, exc_type, *_):
        self.depth -= 1
        if self.depth == 0:
            if exc_type is None:
                self.rows = self.pending  # commit
            self.pending = None  # an exception rolls back: self.rows is untouched
        return False

    def _write(self, sql):
        if self.pending is None:
            self.outside.append(sql)  # a write outside any transaction would be applied at once
            self.pending = self.rows
        return self.pending

    def execute(self, sql, params=None):
        assert "delete from rain_effect" in sql
        self._write(sql).clear()

    def executemany(self, sql, rows):
        assert "insert into rain_effect" in sql
        target = self._write(sql)
        for i, r in enumerate(rows):
            if self.fail_after is not None and i >= self.fail_after:
                raise ConnectionError("connection lost mid-write")
            target.append((r["scope"], r["key"]))


NEW_ROWS = [
    {"scope": "overall", "key": "all", "effect": -0.2, "ci_low": -0.3, "ci_high": -0.1, "n_wet_hours": 500,
     "reliable": True, "detail": {"method": rain_effect.METHOD}},
    {"scope": "sensor", "key": "1", "effect": -0.1, "ci_low": -0.2, "ci_high": 0.1, "n_wet_hours": 400,
     "reliable": False, "detail": None},
    {"scope": "profile", "key": "cbd", "effect": None, "ci_low": None, "ci_high": None, "n_wet_hours": 500,
     "reliable": True, "detail": [{"hour": 12, "wet": 1.0, "dry": 2.0, "n_wet_hours": 3}]},
]
OLD_ROWS = [("overall", "all"), ("sensor", "1"), ("sensor", "99")]
STAMP = datetime(2026, 10, 2, tzinfo=timezone.utc)


def test_a_failure_part_way_through_the_write_keeps_the_old_rows():
    db = FakeDatabase(OLD_ROWS, fail_after=2)  # the old rows are already deleted when the 3rd insert fails
    with pytest.raises(ConnectionError):
        rain_effect.save(db, NEW_ROWS, date(2025, 10, 1), date(2026, 9, 30), STAMP)
    assert db.rows == OLD_ROWS and db.outside == []


def test_a_successful_write_replaces_every_row_in_one_transaction():
    db = FakeDatabase(OLD_ROWS)
    rain_effect.save(db, NEW_ROWS, date(2025, 10, 1), date(2026, 9, 30), STAMP)
    assert db.rows == [("overall", "all"), ("sensor", "1"), ("profile", "cbd")]  # the retired sensor 99 is gone
    assert db.outside == []  # the delete and every insert were inside the transaction


def test_the_method_is_stored_with_the_overall_row():
    r = results(reps=7)
    assert r[("overall", "all")]["detail"] == {"method": {**rain_effect.METHOD, "bootstrap_reps": 7}}
    assert rain_effect.METHOD["wet_mm"] == 0.2 and rain_effect.METHOD["min_wet_hours"] == 100
    assert r[("sensor", "1")]["detail"] is None
