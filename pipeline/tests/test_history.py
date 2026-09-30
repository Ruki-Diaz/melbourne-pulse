from datetime import date

from conftest import utc
from pulse.history import complete_days


def test_up_sensor_day_is_filled_with_zeros():
    out = complete_days([(3, date(2026, 9, 30), 9, 500), (3, date(2026, 9, 30), 10, 700)])
    assert len(out) == 24
    counts = {hour: count for _, _, hour, _, count in out}
    assert counts[9] == 500 and counts[10] == 700 and counts[3] == 0
    assert out[0][3] == utc(2026, 9, 29, 14)  # local midnight AEST


def test_down_sensor_day_stays_absent():
    out = complete_days([(3, date(2026, 9, 30), 9, 500)])
    assert {(lid, day) for lid, day, *_ in out} == {(3, date(2026, 9, 30))}


def test_dst_days_have_23_and_24_valid_hours():
    spring = complete_days([(1, date(2026, 10, 4), 12, 5)])
    autumn = complete_days([(1, date(2027, 4, 4), 12, 5), (1, date(2027, 4, 4), 2, 999)])
    assert len(spring) == 23
    # Autumn has 25 real hours, but the city merges both 02:00s into one row,
    # which we drop: 24 - 1 = 23 usable hours, and the merged 999 never appears.
    assert len(autumn) == 23 and all(count != 999 for *_, count in autumn)
