from datetime import date, datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

import features
from predict import targets_for
from pulse.history import complete_days
from pulse.timeutil import local
from pulse.typical import typical


def synthetic_history(first=date(2026, 7, 1), last=date(2026, 10, 20), sensors=(1, 2), down=()):
    """Deterministic counts per (sensor, day, hour); `down` = (sensor, day) with no data."""
    rng = np.random.default_rng(0)
    rows = []
    day = first
    while day <= last:
        for lid in sensors:
            if (lid, day) in down:
                continue
            for hour in range(24):
                if 1 <= hour <= 4:
                    continue  # quiet hours omitted, like the city's data
                rows.append((lid, day, hour, int(rng.integers(50, 500)) * lid))
        day += timedelta(days=1)
    frame = pd.DataFrame(complete_days(rows), columns=["location_id", "date", "hour", "ts", "count"])
    frame["date"] = pd.to_datetime(frame["date"])
    return frame


def test_typical_matches_the_apps_calculation_across_dst():
    hist = synthetic_history()
    # Targets after the 4 Oct change, so the 8-week window spans AEST and AEDT.
    targets = hist[(hist["date"] >= "2026-10-12") & (hist["date"] <= "2026-10-18")].reset_index(drop=True)
    got = features.build(targets, hist, ["typical_8w"])["typical_8w"].to_numpy()

    for i in range(0, len(targets), 37):
        row = targets.iloc[i]
        mine = hist[hist["location_id"] == row["location_id"]]
        expected = typical(
            [(ts.to_pydatetime(), c, False) for ts, c in zip(mine["ts"], mine["count"])],
            row["ts"].to_pydatetime(),
        )
        assert got[i] == pytest.approx(expected), row


def test_no_feature_uses_data_from_the_last_7_days():
    """Deleting everything within 7 days of the target must not change any feature,
    so every feature is known 24 h (in fact 6+ days) before the hour it predicts."""
    hist = synthetic_history()
    columns = features.BASE + features.EXTRA
    target_day = pd.Timestamp("2026-10-15")
    targets = hist[hist["date"] == target_day].reset_index(drop=True)

    full = features.build(targets, hist, columns)
    truncated = features.build(targets, hist[hist["date"] <= target_day - pd.Timedelta(days=7)], columns)
    pd.testing.assert_frame_equal(full, truncated)


def test_down_days_become_missing_not_zero():
    hist = synthetic_history(down={(1, date(2026, 10, 8))})
    targets = pd.DataFrame({"location_id": [1], "date": [pd.Timestamp("2026-10-15")], "hour": [12]})
    f = features.build(targets, hist, ["lag_1w", "weeks_available", "down_days_4w"])
    assert np.isnan(f.loc[0, "lag_1w"])
    assert f.loc[0, "weeks_available"] == 7
    assert f.loc[0, "down_days_4w"] == 1


def test_holiday_flags():
    targets = pd.DataFrame(
        {"location_id": [1, 1], "date": pd.to_datetime(["2026-11-03", "2026-11-10"]), "hour": [12, 12]}
    )
    f = features.build(targets, synthetic_history(), ["public_holiday", "lag_1w_holiday", "school_holiday"])
    assert f["public_holiday"].tolist() == [True, False]  # Melbourne Cup Day
    assert f["lag_1w_holiday"].tolist() == [False, True]
    school = features.build(
        pd.DataFrame({"location_id": [1, 1], "date": pd.to_datetime(["2025-07-10", "2025-07-25"]), "hour": [9, 9]}),
        synthetic_history(),
        ["school_holiday"],
    )
    assert school["school_holiday"].tolist() == [True, False]


def test_targets_are_next_36_real_hours_across_spring_forward():
    hist = synthetic_history(last=date(2026, 10, 3))
    now = datetime(2026, 10, 3, 3, 37, tzinfo=timezone.utc)  # Sat 13:37 AEST
    t = targets_for(hist, now)
    one = t[t["location_id"] == 1]
    assert len(one) == 36 and one["ts"].is_unique
    assert one["ts"].diff().dropna().eq(pd.Timedelta(hours=1)).all()
    assert one["ts"].iloc[0] == datetime(2026, 10, 3, 4, tzinfo=timezone.utc)
    local_times = [local(ts) for ts in one["ts"]]
    assert not any(t.date() == date(2026, 10, 4) and t.hour == 2 for t in local_times)  # doesn't exist
    assert sum(t.date() == date(2026, 10, 4) for t in local_times) == 23  # the short day


def test_retired_sensors_are_not_forecast():
    hist = synthetic_history(sensors=(1, 2))
    hist = hist[~((hist["location_id"] == 2) & (hist["date"] > "2026-09-30"))]
    t = targets_for(hist, datetime(2026, 10, 21, tzinfo=timezone.utc))
    assert set(t["location_id"]) == {1}


# ------------------------------------------------------ feed-anomaly hours are left out

import anomalies  # noqa: E402


def at(day: str, hour: int, sensor: int = 1) -> pd.DataFrame:
    return pd.DataFrame({"location_id": [sensor], "date": [pd.Timestamp(day)], "hour": [hour]})


def count(hist, day: str, hour: int, sensor: int = 1) -> float:
    row = hist[(hist["location_id"] == sensor) & (hist["date"] == day) & (hist["hour"] == hour)]
    return float(row["count"].iloc[0])


def flag(*day_hours: tuple[str, int]) -> frozenset[int]:
    days, hours = zip(*day_hours)
    return frozenset(anomalies.keys(pd.to_datetime(list(days)), list(hours)).tolist())


HISTORY_COLUMNS = ["lag_1w", "lag_2w", "typical_8w", "mean_4w", "weeks_available", "day_total_1w", "lag_1w_holiday"]


def test_with_nothing_flagged_the_features_are_exactly_last_week_and_the_week_before():
    hist = synthetic_history()
    f = features.build(at("2026-10-15", 12), hist, HISTORY_COLUMNS)
    assert f.loc[0, "lag_1w"] == count(hist, "2026-10-08", 12) and f.loc[0, "lag_2w"] == count(hist, "2026-10-01", 12)
    weeks = [count(hist, str((pd.Timestamp("2026-10-15") - pd.Timedelta(weeks=k)).date()), 12) for k in range(1, 9)]
    assert f.loc[0, "typical_8w"] == np.median(weeks) and f.loc[0, "mean_4w"] == np.mean(weeks[:4])
    assert f.loc[0, "weeks_available"] == 8
    assert f.loc[0, "day_total_1w"] == hist[(hist["location_id"] == 1) & (hist["date"] == "2026-10-08")]["count"].sum()


def test_a_flagged_hour_is_skipped_and_the_next_valid_week_is_used():
    hist = synthetic_history()
    target = at("2026-10-15", 12)
    excluded = flag(("2026-10-08", 12))  # last week's same hour was a feed anomaly
    f = features.build(target, hist, HISTORY_COLUMNS, excluded=excluded)

    assert f.loc[0, "lag_1w"] == count(hist, "2026-10-01", 12)  # two weeks ago stands in for last week
    assert f.loc[0, "lag_2w"] == count(hist, "2026-09-24", 12)  # and three weeks ago for two
    weeks = [count(hist, str((pd.Timestamp("2026-10-15") - pd.Timedelta(weeks=k)).date()), 12) for k in range(2, 9)]
    assert f.loc[0, "typical_8w"] == np.median(weeks)  # the flagged week is not in the median
    assert f.loc[0, "mean_4w"] == np.mean(weeks[:3])  # nor in the 4-week mean (3 valid weeks left)
    assert f.loc[0, "weeks_available"] == 7
    # The day it happened on has an understated total, so the day total comes from the week before too.
    assert f.loc[0, "day_total_1w"] == hist[(hist["location_id"] == 1) & (hist["date"] == "2026-10-01")]["count"].sum()

    # The flagged value itself can be anything: it never reaches a feature.
    poisoned = hist.copy()
    poisoned.loc[(poisoned["date"] == "2026-10-08") & (poisoned["hour"] == 12), "count"] = 1
    pd.testing.assert_frame_equal(f, features.build(target, poisoned, HISTORY_COLUMNS, excluded=excluded))
    # Other hours of the day, and other targets, are untouched.
    untouched = features.build(at("2026-10-15", 9), hist, ["lag_1w", "lag_2w", "typical_8w"], excluded=excluded)
    pd.testing.assert_frame_equal(untouched, features.build(at("2026-10-15", 9), hist, ["lag_1w", "lag_2w", "typical_8w"]))


def test_two_flagged_weeks_in_a_row_fall_back_further_and_all_flagged_is_missing():
    hist = synthetic_history()
    f = features.build(at("2026-10-15", 12), hist, ["lag_1w", "lag_2w"], excluded=flag(("2026-10-08", 12), ("2026-10-01", 12)))
    assert f.loc[0, "lag_1w"] == count(hist, "2026-09-24", 12) and f.loc[0, "lag_2w"] == count(hist, "2026-09-17", 12)
    every_week = flag(*[(str((pd.Timestamp("2026-10-15") - pd.Timedelta(weeks=k)).date()), 12) for k in range(1, 9)])
    f = features.build(at("2026-10-15", 12), hist, ["lag_1w", "typical_8w", "weeks_available"], excluded=every_week)
    assert np.isnan(f.loc[0, "lag_1w"]) and np.isnan(f.loc[0, "typical_8w"]) and f.loc[0, "weeks_available"] == 0


def test_a_sensor_that_was_down_still_reads_as_missing_not_as_an_earlier_week():
    hist = synthetic_history(down={(1, date(2026, 10, 8))})
    f = features.build(at("2026-10-15", 12), hist, ["lag_1w", "lag_2w"], excluded=flag(("2026-09-17", 12)))
    assert np.isnan(f.loc[0, "lag_1w"])  # down last week: missing, as before
    assert f.loc[0, "lag_2w"] == count(hist, "2026-10-01", 12)


def test_flagged_hours_are_keyed_by_melbourne_local_time_across_dst():
    # 2026-10-03T16:00Z is 03:00 on Sunday 4 Oct (AEDT: 02:00 doesn't exist that day).
    # 2026-10-01T05:00Z is 15:00 on Thursday 1 Oct (AEST).
    got = anomalies.from_utc([datetime(2026, 10, 3, 16, tzinfo=timezone.utc), datetime(2026, 10, 1, 5, tzinfo=timezone.utc)])
    assert got == flag(("2026-10-04", 3), ("2026-10-01", 15))
    assert anomalies.from_utc([]) == frozenset()


def test_flagged_hours_are_never_training_examples_and_the_count_is_reported(capsys, monkeypatch):
    import train

    hist = synthetic_history()
    excluded = flag(("2026-10-08", 12), ("2026-10-08", 13))
    dropped = train.flagged_rows(hist, excluded)
    assert dropped.sum() == 4  # 2 hours x 2 sensors
    assert set(hist[dropped]["date"].dt.strftime("%Y-%m-%d")) == {"2026-10-08"} and set(hist[dropped]["hour"]) == {12, 13}
    assert train.flagged_rows(hist, frozenset()).sum() == 0

    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert anomalies.flagged() == frozenset()  # no database: nothing excluded, and it says so
    assert "no feed-anomaly hours are excluded" in capsys.readouterr().out


def test_forecast_does_not_use_a_flagged_hour_as_history():
    import lightgbm as lgb

    from predict import forecast

    hist = synthetic_history(last=date(2026, 10, 3))
    now = datetime(2026, 10, 3, 3, 37, tzinfo=timezone.utc)
    X = features.build(hist, hist, features.BASE)
    booster = lgb.train({"objective": "l1", "verbose": -1, "num_threads": 1, "min_data_in_leaf": 5},
                        lgb.Dataset(X, hist["count"].to_numpy(dtype=float), categorical_feature=["sensor"]), num_boost_round=30)
    excluded = flag(("2026-09-26", 15), ("2026-09-27", 15))  # the same hour one week before two of the targets
    normal = forecast(hist, now, booster, features.BASE)
    clean = forecast(hist, now, booster, features.BASE, excluded=excluded)

    poisoned = hist.copy()
    bad = poisoned["date"].isin(pd.to_datetime(["2026-09-26", "2026-09-27"])) & (poisoned["hour"] == 15)
    poisoned.loc[bad, "count"] = 0  # what a feed fault looks like
    pd.testing.assert_frame_equal(clean, forecast(poisoned, now, booster, features.BASE, excluded=excluded))  # ignored
    assert not forecast(poisoned, now, booster, features.BASE).equals(normal)  # without the flag it would leak in
