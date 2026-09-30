"""One-off: load the last 8 weeks of hourly counts from the city's history dataset.

Until the hourly job has collected 8 weeks of its own data, 'typical' would have
nothing to compare against. This backfills pedestrian_hourly from
pedestrian-counting-system-monthly-counts-per-hour, so the same typical query
works from day one. Zero hours the city omits are filled in (pulse.history).
Safe to re-run: it never overwrites a complete row the hourly job already
wrote, only fills gaps and replaces partial hours.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta

from pulse import api
from pulse.history import complete_days
from pulse.timeutil import UTC, local, local_hour_to_utc
from pulse.typical import WEEKS


def load(weeks: int) -> tuple[list[tuple[int, datetime, int]], dict]:
    today = local(datetime.now(UTC)).date()
    first = today - timedelta(weeks=weeks, days=1)
    raw = api.export(
        api.PEDESTRIAN_HOURLY,
        select="location_id,sensing_date,hourday,pedestriancount",
        where=f"sensing_date >= date'{first.isoformat()}'",
    )
    # The newest day in the dataset is only partly loaded (~1 day lag): skip it.
    newest = max(date.fromisoformat(r["sensing_date"][:10]) for r in raw)
    parsed = [
        (int(r["location_id"]), date.fromisoformat(r["sensing_date"][:10]), int(r["hourday"]), int(r["pedestriancount"]))
        for r in raw
    ]
    complete = complete_days(r for r in parsed if r[1] < newest)
    rows = [(lid, start, count) for lid, _, _, start, count in complete]
    info = {
        "downloaded": len(raw),
        "kept": len(rows),
        "zero_hours_filled": len(rows) - sum(1 for r in parsed if r[1] < newest and local_hour_to_utc(r[1], r[2])),
        "from": first.isoformat(),
        "to": (newest - timedelta(days=1)).isoformat(),
        "sensors": len({r[0] for r in rows}),
        "skipped_newest_day": sum(1 for r in parsed if r[1] >= newest),
    }
    return rows, info


def save(rows: list[tuple[int, datetime, int]]) -> int:
    from pulse import db

    with db.connect() as conn, conn.transaction():
        conn.execute(
            "create temp table seed (location_id int, hour timestamptz, count int) on commit drop"
        )
        with conn.cursor().copy("copy seed (location_id, hour, count) from stdin") as copy:
            for row in rows:
                copy.write_row(row)
        cur = conn.execute(
            """
            insert into pedestrian_hourly (location_id, hour, count, is_partial)
            select location_id, hour, count, false from seed
            on conflict (location_id, hour) do update
              set count = excluded.count, is_partial = false
              where pedestrian_hourly.is_partial
            """
        )
        return cur.rowcount


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--weeks", type=int, default=WEEKS)
    parser.add_argument("--dry-run", action="store_true", help="download and convert only; no database")
    args = parser.parse_args()

    rows, info = load(args.weeks)
    for key, value in info.items():
        print(f"{key:>20}: {value:,}" if isinstance(value, int) else f"{key:>20}: {value}")
    if args.dry_run:
        print("dry run: nothing written")
        return 0
    print(f"{'written':>20}: {save(rows):,}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
