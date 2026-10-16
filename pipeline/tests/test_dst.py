"""Daylight saving: Melbourne springs forward 4 Oct 2026 (02:00 -> 03:00) and
falls back 4 Apr 2027 (03:00 -> 02:00)."""

from datetime import date, timedelta

import pytest

from conftest import utc
from pulse.aggregate import hourly_sums, pedestrian_hourly
from pulse.timeutil import floor_hour, hours_from, local, local_hour_to_utc

SPRING = date(2026, 10, 4)
AUTUMN = date(2027, 4, 4)


def minutes_over_local_day(day):
    """One fake feed row every 15 minutes across a whole local day."""
    start = local_hour_to_utc(day, 0)
    end = local_hour_to_utc(day + timedelta(days=1), 0)
    rows, t = [], start
    while t < end:
        rows.append({"location_id": 1, "sensing_datetime": t.isoformat(), "total_of_directions": 1})
        t += timedelta(minutes=15)
    return rows


@pytest.mark.parametrize(("day", "hours"), [(SPRING, 23), (AUTUMN, 25), (date(2026, 10, 11), 24)])
def test_local_day_has_right_number_of_hour_buckets(day, hours):
    sums = hourly_sums(minutes_over_local_day(day))
    assert len(sums) == hours
    assert all(count == 4 for count in sums.values())  # no bucket swallowed another


def test_repeated_2am_stays_two_separate_hours():
    first = utc(2027, 4, 3, 15)  # 02:00 AEDT
    second = utc(2027, 4, 3, 16)  # 02:00 AEST
    assert local(first).hour == local(second).hour == 2
    assert floor_hour(first + timedelta(minutes=59)) == first
    assert floor_hour(second + timedelta(minutes=1)) == second


def test_local_hour_to_utc_around_changes():
    assert local_hour_to_utc(SPRING, 1) == utc(2026, 10, 3, 15)  # 01:00 AEST
    assert local_hour_to_utc(SPRING, 2) is None  # doesn't exist
    assert local_hour_to_utc(SPRING, 3) == utc(2026, 10, 3, 16)  # 03:00 AEDT
    assert local_hour_to_utc(AUTUMN, 1) == utc(2027, 4, 3, 14)  # 01:00 AEDT
    assert local_hour_to_utc(AUTUMN, 2) is None  # happens twice; city data merges them
    assert local_hour_to_utc(AUTUMN, 3) == utc(2027, 4, 3, 17)  # 03:00 AEST


@pytest.mark.parametrize(("start", "skipped", "doubled"), [(utc(2026, 10, 3, 2), 2, None), (utc(2027, 4, 3, 2), None, 2)])
def test_24_hour_horizon_across_change(start, skipped, doubled):
    hours = hours_from(start, 24)
    assert len(set(hours)) == 24
    assert all(b - a == timedelta(hours=1) for a, b in zip(hours, hours[1:]))
    local_hours = [local(h).hour for h in hours]
    if skipped is not None:
        assert skipped not in local_hours and len(set(local_hours)) == 23
    if doubled is not None:
        assert local_hours.count(doubled) == 2


def test_pedestrian_hourly_across_spring_forward():
    rows = [
        {"location_id": 8, "sensing_datetime": "2026-10-03T13:00:00+00:00", "total_of_directions": 1},  # the feed starts with the window
        {"location_id": 7, "sensing_datetime": "2026-10-03T15:59:00+00:00", "total_of_directions": 5},  # 01:59 AEST
        {"location_id": 7, "sensing_datetime": "2026-10-03T16:00:00+00:00", "total_of_directions": 3},  # 03:00 AEDT
    ]
    out = [h for h in pedestrian_hourly(rows, window_start=utc(2026, 10, 3, 13)) if h.location_id == 7]
    assert [(local(h.hour).strftime("%H:%M %Z"), h.count, h.is_partial) for h in out] == [
        ("00:00 AEST", 0, False),  # sensor is up on 4 Oct, so its silent hour is a real 0
        ("01:00 AEST", 5, False),
        ("03:00 AEDT", 3, True),  # 02:00 doesn't exist
    ]


def test_the_hour_the_city_has_started_trimming_is_never_rewritten():
    """The city trims the feed at 13:55 UTC: 00:55 AEDT. Its oldest midnight hour holds 5 minutes, not 60."""
    rows = [
        {"location_id": 7, "sensing_datetime": "2026-10-13T13:55:00+00:00", "total_of_directions": 9},  # 00:55 AEDT, oldest in the feed
        {"location_id": 7, "sensing_datetime": "2026-10-13T14:10:00+00:00", "total_of_directions": 4},  # 01:10 AEDT
    ]
    out = pedestrian_hourly(rows, window_start=utc(2026, 10, 13, 13))  # the window asks for midnight onwards
    assert [(local(h.hour).strftime("%H:%M"), h.count) for h in out] == [("01:00", 4)]  # midnight left as stored
