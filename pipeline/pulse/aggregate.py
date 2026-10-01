"""Turn raw feed rows into the small shapes we store. Pure functions, no I/O."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta

from .timeutil import HOUR, floor_hour, local, parse_ts

STALE_AFTER = timedelta(hours=24)


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
