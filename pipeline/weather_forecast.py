"""Store the next 48 hours of weather forecast for the Plan page.

Runs in the hourly job. Every run replaces the future hours in
weather_forecast with the newest Open-Meteo forecast and keeps the last two
days of past hours. If Open-Meteo can't be reached, the rows already stored
are left untouched, the run gets a warning annotation and the script exits 0.
It exits 1 (red) only if Open-Meteo has failed three runs in a row or the
database fails (see pulse/feedstatus.py).
"""

from __future__ import annotations

import argparse
import sys

from pulse import feedstatus, openmeteo
from pulse.timeutil import local

KEEP_PAST_DAYS = 2  # same as the forecasts table


FEED = "weather"


def fetch(source=openmeteo.forecast) -> tuple[list[dict] | None, str | None]:
    """(rows, None), or (None, why) if Open-Meteo failed or sent nothing usable."""
    try:
        rows = source()
        if not rows or all(r["temperature"] is None for r in rows):
            raise ValueError("no usable rows")
        return rows, None
    except Exception as exc:  # noqa: BLE001 - one weather outage must not fail the hourly job
        print(f"[weather] FAILED: {exc}; keeping the last good rows", file=sys.stderr)
        return None, f"{type(exc).__name__}: {exc}"


def save(conn, rows: list[dict]) -> None:
    """Replace every stored hour from the first fetched hour onwards."""
    with conn.transaction():
        conn.execute("delete from weather_forecast where hour >= %s", (rows[0]["hour"],))
        with conn.cursor() as cur:
            cur.executemany(
                """
                insert into weather_forecast
                  (hour, precipitation, precipitation_probability, temperature, wind_speed, weather_code, fetched_at)
                values (%(hour)s, %(precipitation)s, %(precipitation_probability)s, %(temperature)s,
                        %(wind_speed)s, %(weather_code)s, now())
                """,
                rows,
            )
        conn.execute(
            "delete from weather_forecast where hour < now() - make_interval(days => %s)", (KEEP_PAST_DAYS,)
        )


def refresh(connect, source=openmeteo.forecast, record=None) -> int:
    """Fetch, save if there is anything to save, note the outcome; return the exit code.

    A database error is not caught: it ends the run red.
    """
    if record is None:
        from pulse.db import record_feed_runs as record

    rows, reason = fetch(source)
    with connect() as conn:
        if rows:
            save(conn, rows)
            print(f"[weather] saved {len(rows)} forecast hours from {local(rows[0]['hour']):%a %d %b %H:00 %Z}")
        with conn.transaction():
            streaks = record(conn, ok=[FEED] if rows else [], failed=[] if rows else [FEED])
    # One feed, so "every feed failed" is just an ordinary outage here: a warning until it repeats.
    return feedstatus.exit_code({} if rows else {FEED: reason}, streaks, all_failed=False)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="fetch and print; no database")
    args = parser.parse_args()

    if args.dry_run:
        rows, reason = fetch()
        if rows is None:
            feedstatus.exit_code({FEED: reason}, {}, all_failed=False)
            rows = []
        for row in rows[:3]:
            print({**row, "hour": f"{local(row['hour']):%a %H:00 %Z}"})
        wet = sum(1 for r in rows if (r["precipitation"] or 0) >= 0.2)
        print(f"[weather] {len(rows)} forecast hours, {wet} with rain; dry run: nothing written")
        return 0

    from pulse import db

    return refresh(db.connect)


if __name__ == "__main__":
    sys.exit(main())
