"""Hourly ingest of City of Melbourne live pedestrian and parking data.

Pulls three feeds, aggregates them to hourly rows, and upserts:
  pedestrian_hourly  every hour of the last 24 per sensor (newest one is_partial),
                     so missed runs and partial hours heal on the next run
  parking_hourly     CBD-wide free/occupied/stale counts for this hour
  latest             slim current state for the website
Rows older than 90 days are trimmed. If a feed fails the others are still
saved and the script exits 1 so the GitHub Action shows red.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from datetime import datetime

from pulse import aggregate, api
from pulse.aggregate import HourCount
from pulse.timeutil import HOUR, UTC, floor_hour, local

# The per-minute feed holds ~26 h (~10 MB). Re-reading 24 h every run means a
# run GitHub skipped, or a cron that fired late, costs nothing: the next run
# re-writes every hour it missed. Upserts make re-writing idempotent.
WINDOW_HOURS = 24


@dataclass
class Feeds:
    now: datetime
    pedestrian: list[HourCount] | None = None
    bays: list[dict] | None = None
    sensors: list[dict] | None = None
    failures: list[str] = field(default_factory=list)

    @property
    def complete_hour(self) -> datetime | None:
        done = [h.hour for h in self.pedestrian or [] if not h.is_partial]
        return max(done) if done else None


def collect(now: datetime | None = None) -> Feeds:
    """Download and aggregate every feed; record failures instead of raising."""
    feeds = Feeds(now=now or datetime.now(UTC))
    window_start = floor_hour(feeds.now) - WINDOW_HOURS * HOUR

    def attempt(name, fn):
        print(f"[{name}] fetching")
        try:
            result = fn()
        except Exception as exc:  # noqa: BLE001 - one bad feed must not block the rest
            print(f"[{name}] FAILED: {exc}", file=sys.stderr)
            feeds.failures.append(name)
            return None
        if not result:
            print(f"[{name}] FAILED: no usable rows", file=sys.stderr)
            feeds.failures.append(name)
            return None
        return result

    feeds.pedestrian = attempt(
        "pedestrian",
        lambda: aggregate.pedestrian_hourly(
            api.export(
                api.PEDESTRIAN_MINUTES,
                where=f"sensing_datetime >= {api.odsql_ts(window_start)}",
            ),
            window_start,
        ),
    )
    feeds.bays = attempt(
        "parking", lambda: aggregate.slim_parking(api.export(api.PARKING), feeds.now)
    )
    feeds.sensors = attempt(
        "sensors", lambda: aggregate.slim_sensors(api.export(api.SENSOR_LOCATIONS))
    )
    return feeds


def pedestrian_payload(feeds: Feeds, typicals: dict[int, float]) -> dict:
    hour = feeds.complete_hour
    return {
        "hour": hour.isoformat(),
        "sensors": [
            {
                "location_id": h.location_id,
                "count": h.count,
                "typical": round(typicals[h.location_id]) if h.location_id in typicals else None,
            }
            for h in feeds.pedestrian
            if h.hour == hour
        ],
    }


def report(feeds: Feeds) -> None:
    if feeds.pedestrian:
        by_hour: dict[datetime, list[HourCount]] = {}
        for h in feeds.pedestrian:
            by_hour.setdefault(h.hour, []).append(h)
        ordered = sorted(by_hour.items())
        print(
            f"[pedestrian] {len(ordered)} hours ({local(ordered[0][0]):%a %H:00} - "
            f"{local(ordered[-1][0]):%a %H:00 %Z}), {len(feeds.pedestrian):,} sensor-hours"
        )
        for hour, rows in ordered[-2:]:
            flag = "partial" if rows[0].is_partial else "complete"
            print(
                f"[pedestrian] {local(hour):%a %d %b %H:00 %Z} ({flag}): "
                f"{len(rows)} sensors, {sum(r.count for r in rows):,} people"
            )
    if feeds.bays:
        stats = aggregate.parking_hourly(feeds.bays)
        pct = f"{stats['pct_free']:.0%}" if stats["pct_free"] is not None else "n/a"
        print(
            f"[parking] {len(feeds.bays):,} bays: {stats['bays_free']:,} free, "
            f"{stats['bays_occupied']:,} occupied, {stats['bays_stale']:,} stale -> {pct} free"
        )
        print(f"[parking] latest payload row: {feeds.bays[0]}")
    if feeds.sensors:
        print(f"[sensors] {len(feeds.sensors)} locations, e.g. {feeds.sensors[0]}")


def save(feeds: Feeds) -> None:
    from pulse import db

    with db.connect() as conn:
        # One transaction per source so a failure in one can't roll back another.
        if feeds.pedestrian:
            with conn.transaction():
                db.upsert_pedestrian_hours(conn, feeds.pedestrian)
                typicals = db.typicals_for(conn, feeds.complete_hour) if feeds.complete_hour else {}
                if feeds.complete_hour:
                    db.upsert_latest(conn, "pedestrian", pedestrian_payload(feeds, typicals))
            reporting = {h.location_id for h in feeds.pedestrian}
            print(
                f"[pedestrian] saved {len(feeds.pedestrian)} hourly rows; "
                f"typical known for {len(reporting & typicals.keys())} of {len(reporting)} sensors"
            )
        if feeds.bays:
            with conn.transaction():
                db.upsert_parking_hour(conn, floor_hour(feeds.now), aggregate.parking_hourly(feeds.bays))
                db.upsert_latest(conn, "parking", feeds.bays)
            print(f"[parking] saved {len(feeds.bays):,} bays")
        if feeds.sensors:
            with conn.transaction():
                db.upsert_latest(conn, "sensors", feeds.sensors)
            print(f"[sensors] saved {len(feeds.sensors)} locations")
        with conn.transaction():
            deleted = db.trim(conn)
        print(f"trimmed rows older than {db.RETENTION_DAYS} days: {deleted}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="fetch and aggregate only; no database")
    args = parser.parse_args()

    feeds = collect()
    report(feeds)
    if args.dry_run:
        print("dry run: nothing written")
    else:
        save(feeds)

    if feeds.failures:
        print(f"failed feeds: {', '.join(feeds.failures)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
