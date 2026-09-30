from datetime import date, timedelta

from conftest import utc
from pulse.aggregate import (
    hourly_sums,
    parking_hourly,
    pedestrian_hourly,
    slim_parking,
    slim_sensors,
)
from pulse.timeutil import local_hour_to_utc

# ---------------------------------------------------------------- pedestrians


def test_hourly_sums_match_city_hourly_dataset(minute_rows, monthly_rows):
    """Summing the per-minute feed reproduces the city's own hourly totals,
    for 1-minute and 5-minute sensors alike (so rows are counts, not rates)."""
    sums = hourly_sums(minute_rows)
    for m in monthly_rows:
        hour = local_hour_to_utc(date.fromisoformat(m["sensing_date"]), m["hourday"])
        assert sums[(m["location_id"], hour)] == m["pedestriancount"], m


def test_missing_zero_minutes_are_not_row_counted(minute_rows, monthly_rows):
    # Sensor 3 (1-minute) has only 35 rows in 16:00Z: the other minutes had 0 people.
    hour = utc(2026, 9, 29, 16)
    rows = [r for r in minute_rows if r["location_id"] == 3 and r["sensing_datetime"].startswith("2026-09-29T16")]
    assert len(rows) == 35
    expected = next(m["pedestriancount"] for m in monthly_rows if m["location_id"] == 3 and m["hourday"] == 2)
    assert hourly_sums(minute_rows)[(3, hour)] == expected == 76


def test_five_minute_sensor_with_gaps(minute_rows):
    # Sensor 41 reports 5-minute buckets and omitted 3 empty ones in 16:00Z.
    rows = [r for r in minute_rows if r["location_id"] == 41 and r["sensing_datetime"].startswith("2026-09-29T16")]
    assert len(rows) == 9
    assert all(int(r["sensing_datetime"][14:16]) % 5 == 0 for r in rows)
    assert hourly_sums(minute_rows)[(41, utc(2026, 9, 29, 16))] == 33


def test_latest_two_hours_with_current_partial(minute_rows):
    out = pedestrian_hourly(minute_rows, window_start=utc(2026, 9, 29, 14))
    assert {h.hour for h in out} == {utc(2026, 9, 29, 15), utc(2026, 9, 29, 16)}
    assert all(h.is_partial == (h.hour == utc(2026, 9, 29, 16)) for h in out)
    assert len(out) == 4 * 2  # every sensor gets both hours


def test_sensor_silent_for_an_hour_gets_zero():
    rows = [
        {"location_id": 1, "sensing_datetime": "2026-09-29T15:10:00+00:00", "total_of_directions": 4},
        {"location_id": 1, "sensing_datetime": "2026-09-29T16:20:00+00:00", "total_of_directions": 2},
        {"location_id": 2, "sensing_datetime": "2026-09-29T15:30:00+00:00", "total_of_directions": 7},
    ]
    out = {(h.location_id, h.hour): h.count for h in pedestrian_hourly(rows, utc(2026, 9, 29, 13))}
    assert out[(2, utc(2026, 9, 29, 16))] == 0
    assert out[(1, utc(2026, 9, 29, 16))] == 2


def test_hour_starting_before_window_is_dropped(minute_rows):
    # If the window began mid-way through 15:00Z, that hour would be undercounted.
    out = pedestrian_hourly(minute_rows, window_start=utc(2026, 9, 29, 15, 30))
    assert {h.hour for h in out} == {utc(2026, 9, 29, 16)}


def test_empty_feed():
    assert pedestrian_hourly([], utc(2026, 9, 29, 14)) == []


# ---------------------------------------------------------------- parking

NOW = utc(2026, 9, 30, 17, 5)


def bay(lastupdated, status="Unoccupied", kerbsideid=1):
    return {
        "kerbsideid": kerbsideid,
        "status_description": status,
        "lastupdated": lastupdated,
        "status_timestamp": lastupdated,
        "zone_number": None,
        "location": {"lon": 144.9612345678, "lat": -37.8112345678},
    }


def test_stale_cutoff_is_24_hours():
    exactly = (NOW - timedelta(hours=24)).isoformat()
    just_over = (NOW - timedelta(hours=24, seconds=1)).isoformat()
    fresh, stale = slim_parking([bay(exactly), bay(just_over)], NOW)
    assert fresh["stale"] is False
    assert stale["stale"] is True


def test_missing_timestamp_or_unknown_status_is_stale():
    a, b = slim_parking([bay(None), bay(NOW.isoformat(), status="Unknown")], NOW)
    assert a["stale"] and b["stale"]


def test_slim_parking_shape(parking_rows):
    bays = slim_parking(parking_rows, NOW)
    assert len(bays) == 80
    assert all(set(b) == {"kerbsideid", "lat", "lon", "free", "stale"} for b in bays)
    # Fixture: 40 bays last reported in 2024, 40 in the hour before NOW.
    assert sum(b["stale"] for b in bays) == 40
    assert bays[0]["lat"] == round(parking_rows[0]["location"]["lat"], 6)


def test_pct_free_excludes_stale_bays():
    bays = [
        {"free": True, "stale": False},
        {"free": False, "stale": False},
        {"free": False, "stale": False},
        {"free": True, "stale": False},
        {"free": True, "stale": True},  # would make it 60% if counted
    ]
    assert parking_hourly(bays) == {"bays_free": 2, "bays_occupied": 2, "bays_stale": 1, "pct_free": 0.5}


def test_pct_free_when_everything_is_stale():
    assert parking_hourly([{"free": True, "stale": True}])["pct_free"] is None


def test_slim_sensors(location_rows):
    sensors = slim_sensors(location_rows)
    assert [s["location_id"] for s in sensors] == [3, 4, 5, 41]
    assert sensors[0] == {
        "location_id": 3,
        "name": "Melbourne Central",
        "lat": -37.81101524,
        "lon": 144.96429485,
        "indoor": False,
    }
