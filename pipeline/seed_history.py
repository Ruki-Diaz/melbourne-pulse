"""One-off: load the last 8 weeks of hourly counts from the city's history dataset.

Until the hourly job has collected 8 weeks of its own data, 'typical' would have
nothing to compare against. This backfills pedestrian_hourly from
pedestrian-counting-system-monthly-counts-per-hour, so the same typical query
works from day one. Safe to re-run: it never overwrites a complete row the
hourly job already wrote, only fills gaps and replaces partial hours.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta

from pulse import api
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
    rows, skipped_dst, skipped_partial = [], 0, 0
    for r in raw:
        day = date.fromisoformat(r["sensing_date"][:10])
        if day >= newest:
            skipped_partial += 1
            continue
        hour = local_hour_to_utc(day, int(r["hourday"]))
        if hour is None:  # repeated/skipped 02:00 at a DST change
            skipped_dst += 1
            continue
        rows.append((int(r["location_id"]), hour, int(r["pedestriancount"])))
    info = {
        "downloaded": len(raw),
        "kept": len(rows),
        "from": first.isoformat(),
        "to": (newest - timedelta(days=1)).isoformat(),
        "sensors": len({r[0] for r in rows}),
        "skipped_newest_day": skipped_partial,
        "skipped_dst_hour": skipped_dst,
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
