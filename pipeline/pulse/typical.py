"""'Typical' = median count for the same sensor, weekday and local hour over the
previous 8 weeks, ignoring partial hours.

The same weekday/hour is matched in *local* time, so a Monday 9am in AEDT is
compared with Monday 9am in AEST from before the clocks changed, even though
the two are 23:00Z and 22:00Z.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from statistics import median
from typing import Iterable

from .timeutil import local

WEEKS = 8


def history_since(target: datetime) -> datetime:
    """Earliest instant `typical` can look at (a day of slack for DST)."""
    return target - timedelta(weeks=WEEKS, days=1)


def typical(history: Iterable[tuple[datetime, int, bool]], target: datetime) -> float | None:
    """Median of (hour, count, is_partial) rows matching `target`'s local weekday and hour."""
    t = local(target)
    first_day = t.date() - timedelta(weeks=WEEKS)
    values = []
    for hour, count, is_partial in history:
        h = local(hour)
        if (
            not is_partial
            and hour < target
            and h.date() >= first_day
            and h.weekday() == t.weekday()
            and h.hour == t.hour
        ):
            values.append(count)
    return float(median(values)) if values else None


def typical_by_sensor(
    rows: Iterable[tuple[int, datetime, int, bool]], target: datetime
) -> dict[int, float]:
    """`typical` for every sensor in (location_id, hour, count, is_partial) rows."""
    by_sensor: dict[int, list[tuple[datetime, int, bool]]] = defaultdict(list)
    for lid, hour, count, is_partial in rows:
        by_sensor[lid].append((hour, count, is_partial))
    out = {}
    for lid, hist in by_sensor.items():
        value = typical(hist, target)
        if value is not None:
            out[lid] = value
    return out
