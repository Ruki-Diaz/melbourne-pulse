from datetime import date, timedelta

from pulse.timeutil import HOUR, local_hour_to_utc
from pulse.typical import typical, typical_by_sensor

# Target: Monday 12 Oct 2026, 9am local (AEDT, after the 4 Oct change) = 22:00Z Sun.
TARGET = local_hour_to_utc(date(2026, 10, 12), 9)


def mondays_9am(weeks):
    """Local Mondays 9am going back `weeks` weeks from TARGET."""
    return [local_hour_to_utc(date(2026, 10, 12) - timedelta(weeks=w), 9) for w in range(1, weeks + 1)]


def test_median_of_last_8_same_weekday_hours():
    history = [(h, c, False) for h, c in zip(mondays_9am(8), [100, 200, 300, 400, 500, 600, 700, 800])]
    assert typical(history, TARGET) == 450


def test_matches_local_hour_across_dst():
    hours = mondays_9am(8)
    # Weeks before 4 Oct were AEST, so 9am local was 23:00Z, not 22:00Z.
    assert hours[0].hour == 22 and hours[-1].hour == 23
    # A row at the same *UTC* time as TARGET's offset but the wrong local hour
    # (Monday 8am AEST = 22:00Z) must not be picked up.
    decoy = local_hour_to_utc(date(2026, 9, 28), 8)
    assert decoy.hour == 22
    history = [(h, 10, False) for h in hours] + [(decoy, 10_000, False)]
    assert typical(history, TARGET) == 10


def test_ignores_partial_older_than_8_weeks_other_hours_and_future():
    good = [(h, 50, False) for h in mondays_9am(8)]
    noise = [
        (mondays_9am(1)[0], 9_999, True),  # partial
        (mondays_9am(9)[-1], 9_999, False),  # 9 weeks back
        (mondays_9am(1)[0] + HOUR, 9_999, False),  # 10am
        (mondays_9am(1)[0] + timedelta(days=1), 9_999, False),  # Tuesday
        (TARGET, 9_999, False),  # the target hour itself
        (TARGET + timedelta(weeks=1), 9_999, False),  # future
    ]
    assert typical(good + noise, TARGET) == 50


def test_fewer_than_8_weeks_still_gives_a_value():
    assert typical([(mondays_9am(2)[1], 42, False)], TARGET) == 42


def test_no_history():
    assert typical([], TARGET) is None
    assert typical([(mondays_9am(1)[0], 5, True)], TARGET) is None


def test_typical_by_sensor_skips_sensors_without_history():
    rows = [(1, h, 20, False) for h in mondays_9am(8)] + [(2, mondays_9am(1)[0], 30, True)]
    assert typical_by_sensor(rows, TARGET) == {1: 20}
