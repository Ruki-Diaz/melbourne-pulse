"""Spot hours when the city's live sensor feed itself looks wrong.

On Thu 1 Oct 2026, from mid-afternoon, almost every sensor at once read under
half its typical count, with every minute present and rain no heavier than that
morning. Whatever the cause, a count like that must not be reported as "the CBD
is 60% quieter", fed to the forecast as history, or used to train the model.

The test is deliberately about breadth, not depth: real events (rain, a public
holiday, a parade) move sensors by different amounts and never push most of
them below half at the same moment. A fault in the feed does.

Pure functions, no I/O. feed_quality.py stores the results.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Callable

# A sensor is "low" when its count is under this share of its typical count for
# that weekday and hour. Half is far outside ordinary variation: in the two
# weeks to 2 Oct 2026, an ordinary hour had 1% of sensors this low (95th
# percentile 6%).
LOW_RATIO = 0.5
# An hour is an anomaly when at least this share of sensors is low. A public
# holiday in that fortnight (Grand Final eve) peaked at 41%; the 1 Oct episode
# reached 96%, or 70% after the heavy-rain allowance below.
MIN_SHARE = 0.6
# Once an anomaly has started it holds while at least this share is still low,
# so one middling hour inside a fault doesn't flip the site back and forth.
# A quarter is still about five times an ordinary hour.
HOLD_SHARE = 0.25
# Sensors with a typical count below this are not judged: at 3am, 2 passes
# instead of 5 is "under half" by chance.
MIN_TYPICAL = 30
# With fewer judged sensors than this the hour can't be assessed (overnight).
# It then inherits the state of the hour before it.
MIN_SENSORS = 20


@dataclass(frozen=True)
class HeavyRain:
    """What heavy rain can explain, from the measured rain effect (rain_effect.py)."""

    mm: float  # an hour is heavy from this much rain
    ci_low: float  # lower end of the 95% interval of the heavy-rain effect, e.g. -0.37


@dataclass(frozen=True)
class Quality:
    hour: datetime
    judged: int  # sensors with a usable typical
    low: int  # of those, how many were under the threshold
    anomaly: bool
    # ok | low_counts | holding | public_holiday | too_few_sensors
    reason: str
    heavy_rain: bool = False

    @property
    def share(self) -> float | None:
        return self.low / self.judged if self.judged else None


def assess(
    hour: datetime,
    local_day: date,
    counts: dict[int, int],
    typical: dict[int, float],
    *,
    previous: Quality | None = None,
    rain_mm: float | None = None,
    heavy: HeavyRain | None = None,
    is_public_holiday: Callable[[date], bool] = lambda _: False,
) -> Quality:
    """Assess one finished hour.

    `counts` and `typical` are per sensor, for sensors that have finished
    reporting the hour. `previous` is the assessment of the hour just before
    this one, if there is one.

    Heavy rain: when the hour had heavy rain, each sensor's threshold is lowered
    by the most that heavy rain is known to remove (the lower end of its
    measured 95% interval), so rain alone can't trip the test.
    """
    is_heavy = heavy is not None and rain_mm is not None and rain_mm >= heavy.mm
    allowance = 1 + heavy.ci_low if is_heavy else 1.0
    judged = [lid for lid in counts if typical.get(lid, 0) >= MIN_TYPICAL]
    low = sum(1 for lid in judged if counts[lid] < LOW_RATIO * allowance * typical[lid])
    ongoing = bool(previous and previous.anomaly)

    def result(anomaly: bool, reason: str) -> Quality:
        return Quality(hour, len(judged), low, anomaly, reason, is_heavy)

    if is_public_holiday(local_day):
        # "Typical" is an ordinary weekday, so offices being empty is expected.
        return result(False, "public_holiday")
    if len(judged) < MIN_SENSORS:
        return result(ongoing, "too_few_sensors")
    share = low / len(judged)
    if ongoing:
        return result(True, "holding") if share >= HOLD_SHARE else result(False, "ok")
    return result(True, "low_counts") if share >= MIN_SHARE else result(False, "ok")


def ranges(assessments: list[Quality]) -> list[tuple[datetime, datetime, float]]:
    """Runs of consecutive anomalous hours: (first hour, last hour, highest share low)."""
    out: list[list] = []
    for q in sorted((q for q in assessments if q.anomaly), key=lambda q: q.hour):
        share = q.share or 0.0
        if out and (q.hour - out[-1][1]).total_seconds() == 3600:
            out[-1][1] = q.hour
            out[-1][2] = max(out[-1][2], share)
        else:
            out.append([q.hour, q.hour, share])
    return [tuple(r) for r in out]
