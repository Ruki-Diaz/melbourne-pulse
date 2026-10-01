"""Turn raw feed rows into the small shapes we store. Pure functions, no I/O."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta

from .timeutil import HOUR, floor_hour, local, parse_ts

STALE_AFTER = timedelta(hours=24)
# A sensor has finished reporting an hour once its newest minute is this far into
# it or later. 5-minute sensors end an hour at :55, and sensors upload in batches
# that can trail the rest of the feed by an hour or more.
SETTLED_AFTER = timedelta(minutes=50)


@dataclass(frozen=True)
class HourCount:
    location_id: int
    hour: datetime  # UTC start of the local hour
    count: int
    is_partial: bool


def hourly_sums(rows: list[dict]) -> dict[tuple[int, datetime], int]:
    """Sum `total_of_directions` per (location_id, hour start). Never counts rows."""
    sums: dict[tuple[int, datetime], int] = defaultdict(int)
    for r in rows:
        key = (int(r["location_id"]), floor_hour(parse_ts(r["sensing_datetime"])))
        sums[key] += int(r["total_of_directions"] or 0)
    return dict(sums)


def sensor_watermarks(rows: list[dict]) -> dict[int, datetime]:
    """The newest minute each sensor has reported."""
    newest: dict[int, datetime] = {}
    for r in rows:
        lid, at = int(r["location_id"]), parse_ts(r["sensing_datetime"])
        if lid not in newest or at > newest[lid]:
            newest[lid] = at
    return newest


def is_settled(watermark: datetime | None, hour: datetime) -> bool:
    """Has this sensor finished reporting the hour that starts at `hour`?

    The feed as a whole can be past an hour while one sensor is still part-way
    through it. Until the sensor's own newest minute reaches the end of the
    hour, its count is a partial one and must not be compared with a typical
    full hour. (A sensor nobody walked past also looks unfinished, because zero
    minutes aren't published; leaving it out costs nothing.)
    """
    return watermark is not None and watermark >= hour + SETTLED_AFTER


def pedestrian_hourly(rows: list[dict], window_start: datetime) -> list[HourCount]:
    """Sum per-minute rows into every hour of the download window, per sensor.

    - Every run re-writes the whole window (fetch.py uses ~24 h), so hours a
      missed run would have written, late-arriving minutes, and hours stored
      as partial all self-heal on the next successful run.
    - The "current" hour is the one holding the newest minute in the feed
      (the watermark). It is still filling up, so it is marked partial.
    - Minutes with zero people are omitted by the feed, and some sensors report
      5-minute buckets. Both are counts, so we sum `total_of_directions` and
      never count rows.
    - Missing hours: same rule as pulse.history. A sensor that reported on a
      local day gets 0 for its silent hours that day; a sensor silent all day
      is treated as down and gets no rows (not zeros).
    - Hours that start before `window_start` were only partly downloaded, so
      they are dropped rather than overwriting a good value with a short one.
    """
    if not rows:
        return []

    watermark = max(parse_ts(r["sensing_datetime"]) for r in rows)
    current = floor_hour(watermark)
    first = floor_hour(window_start)
    if first < window_start:
        first += HOUR
    hours = []
    h = first
    while h <= current:
        hours.append(h)
        h += HOUR

    sums = hourly_sums(rows)
    up_days = {(lid, local(hour).date()) for lid, hour in sums}
    sensors = sorted({lid for lid, _ in sums})

    return [
        HourCount(lid, h, sums.get((lid, h), 0), is_partial=(h == current))
        for lid in sensors
        for h in hours
        if (lid, h) in sums or (lid, local(h).date()) in up_days
    ]


def slim_parking(rows: list[dict], now: datetime) -> list[dict]:
    """One small dict per bay: exactly {kerbsideid, lat, lon, free, stale}.

    A bay is stale if its sensor hasn't reported for 24 h (or its status is
    unrecognised); its last status can't be trusted, so it is drawn grey and
    left out of the % free denominator.
    """
    cutoff = now - STALE_AFTER
    bays = []
    for r in rows:
        loc = r.get("location") or {}
        if r.get("kerbsideid") is None or loc.get("lat") is None or loc.get("lon") is None:
            continue
        status = r.get("status_description")
        updated = r.get("lastupdated")
        stale = updated is None or parse_ts(updated) < cutoff or status not in ("Present", "Unoccupied")
        bays.append(
            {
                "kerbsideid": int(r["kerbsideid"]),
                "lat": round(float(loc["lat"]), 6),
                "lon": round(float(loc["lon"]), 6),
                "free": status == "Unoccupied",
                "stale": stale,
            }
        )
    return bays


def parking_hourly(bays: list[dict]) -> dict:
    """CBD-wide parking totals. Stale bays are counted separately, not as free/occupied."""
    free = sum(1 for b in bays if not b["stale"] and b["free"])
    occupied = sum(1 for b in bays if not b["stale"] and not b["free"])
    stale = sum(1 for b in bays if b["stale"])
    counted = free + occupied
    return {
        "bays_free": free,
        "bays_occupied": occupied,
        "bays_stale": stale,
        "pct_free": round(free / counted, 4) if counted else None,
    }


def slim_sensors(rows: list[dict]) -> list[dict]:
    return sorted(
        (
            {
                "location_id": int(r["location_id"]),
                "name": r["sensor_description"],
                "lat": float(r["latitude"]),
                "lon": float(r["longitude"]),
                "indoor": r.get("location_type") == "Indoor",
            }
            for r in rows
            if r.get("latitude") is not None and r.get("longitude") is not None
        ),
        key=lambda s: s["location_id"],
    )
