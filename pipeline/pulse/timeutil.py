"""Time helpers. All storage is UTC `timestamptz`; all *meaning* is Melbourne local.

Melbourne's UTC offset is always a whole number of hours (+10 AEST / +11 AEDT),
so flooring a UTC instant to the hour gives the same instant as flooring the
local time. That is what makes hourly bucketing DST-safe: a 23-hour spring day
and a 25-hour autumn day just produce 23 or 25 distinct UTC hour instants.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

MEL = ZoneInfo("Australia/Melbourne")
UTC = timezone.utc
HOUR = timedelta(hours=1)


def parse_ts(value: str) -> datetime:
    """Parse an API ISO-8601 timestamp (always has an offset) into aware UTC."""
    return datetime.fromisoformat(value).astimezone(UTC)


def floor_hour(dt: datetime) -> datetime:
    """Start of the hour containing `dt`, as aware UTC."""
    return dt.astimezone(UTC).replace(minute=0, second=0, microsecond=0)


def local_hour_to_utc(day: date, hour: int) -> datetime | None:
    """UTC start of local hour `hour` on local date `day`.

    Returns None for hours that don't map to exactly one instant:
    - the skipped 02:00 on the first Sunday of October (doesn't exist), and
    - the repeated 02:00 on the first Sunday of April (exists twice; the city's
      hourly dataset merges both into one row, so its count is ~2x real).
    """
    naive = datetime.combine(day, time(hour))
    first = naive.replace(tzinfo=MEL, fold=0)
    second = naive.replace(tzinfo=MEL, fold=1)
    if first.utcoffset() != second.utcoffset():
        return None
    return first.astimezone(UTC)


def hours_from(start: datetime, n: int) -> list[datetime]:
    """`n` consecutive hour starts from `start`, stepping in real (UTC) time."""
    start = floor_hour(start)
    return [start + i * HOUR for i in range(n)]


def local(dt: datetime) -> datetime:
    return dt.astimezone(MEL)
