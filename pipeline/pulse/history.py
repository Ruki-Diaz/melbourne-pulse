"""Clean the city's hourly history (pedestrian-counting-system-monthly-counts-per-hour).

The dataset leaves out hours with zero people, just like the per-minute feed, so
a missing row is ambiguous: nobody walked past, or the sensor was down. We treat
a sensor-day with at least one row as "up" and fill its missing hours with 0 (the
same rule fetch.py uses live), and a sensor-day with no rows at all as "down":
it stays absent, so it never counts as a real zero in 'typical' or the model.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from typing import Iterable

from .timeutil import local_hour_to_utc


def complete_days(
    rows: Iterable[tuple[int, date, int, int]],
) -> list[tuple[int, date, int, datetime, int]]:
    """(location_id, local date, hourday, count) -> every valid hour of each up sensor-day.

    Returns (location_id, local date, hourday, UTC hour start, count), sorted.
    Hours that don't map to one instant at a DST change are dropped (see
    timeutil.local_hour_to_utc), including the city's merged autumn 02:00 row.
    """
    days: dict[tuple[int, date], dict[int, int]] = defaultdict(dict)
    for lid, day, hour, count in rows:
        days[(lid, day)][hour] = count

    out = []
    for (lid, day), hours in sorted(days.items()):
        for hour in range(24):
            start = local_hour_to_utc(day, hour)
            if start is not None:
                out.append((lid, day, hour, start, hours.get(hour, 0)))
    return out
