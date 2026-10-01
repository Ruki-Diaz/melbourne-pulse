"""Store the next 48 hours of weather forecast for the Plan page.

Runs in the hourly job. Every run replaces the future hours in
weather_forecast with the newest Open-Meteo forecast and keeps the last two
days of past hours. If Open-Meteo can't be reached, the rows already stored
are left untouched and the script still exits 0: a weather outage must never
fail the hourly job.
"""

from __future__ import annotations

import argparse
import sys

from pulse import openmeteo
from pulse.timeutil import local

KEEP_PAST_DAYS = 2  # same as the forecasts table


def fetch(source=openmeteo.forecast) -> list[dict] | None:
    """The new forecast, or None (logged) if Open-Meteo failed or sent nothing usable."""
    try:
        rows = source()
        if not rows or all(r["temperature"] is None for r in rows):
            raise ValueError("no usable rows")
        return rows
    except Exception as exc:  # noqa: BLE001 - a weather outage must not fail the hourly job
        print(f"[weather] FAILED: {exc}; keeping the last good rows", file=sys.stderr)
        return None


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


def refresh(connect, source=openmeteo.forecast) -> bool:
    """Fetch, then save. The database is only opened once there is something to write."""
    rows = fetch(source)
    if rows is None:
        return False
    with connect() as conn:
        save(conn, rows)
    print(f"[weather] saved {len(rows)} forecast hours from {local(rows[0]['hour']):%a %d %b %H:00 %Z}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="fetch and print; no database")
    args = parser.parse_args()

    if args.dry_run:
        rows = fetch() or []
        for row in rows[:3]:
            print({**row, "hour": f"{local(row['hour']):%a %H:00 %Z}"})
        wet = sum(1 for r in rows if (r["precipitation"] or 0) >= 0.2)
        print(f"[weather] {len(rows)} forecast hours, {wet} with rain; dry run: nothing written")
        return 0

    from pulse import db

    refresh(db.connect)
    return 0


if __name__ == "__main__":
    sys.exit(main())
