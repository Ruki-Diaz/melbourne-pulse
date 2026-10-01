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
