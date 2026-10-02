"""Postgres (Neon) access. Only fetch.py, summary.py and seed_history.py write."""

from __future__ import annotations

import os
from datetime import datetime

import psycopg
from psycopg.types.json import Jsonb

from .aggregate import HourCount
from .typical import history_since, typical_by_sensor

RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", "90"))


def connect() -> psycopg.Connection:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL is not set (use --dry-run to test without a database)")
    # prepare_threshold=None: Neon's pooled URL goes through PgBouncer in
    # transaction mode, where server-side prepared statements aren't reliable.
    # connect_timeout covers Neon waking from scale-to-zero (usually < 1 s).
    return psycopg.connect(url, prepare_threshold=None, connect_timeout=30)


def upsert_latest(conn: psycopg.Connection, source: str, payload) -> None:
    conn.execute(
        """
        insert into latest (source, updated_at, payload) values (%s, now(), %s)
        on conflict (source) do update
          set updated_at = excluded.updated_at, payload = excluded.payload
        """,
        (source, Jsonb(payload)),
    )


def get_latest(conn: psycopg.Connection, source: str) -> tuple[datetime, object] | None:
    row = conn.execute(
        "select updated_at, payload from latest where source = %s", (source,)
    ).fetchone()
    return (row[0], row[1]) if row else None


def upsert_pedestrian_hours(conn: psycopg.Connection, hours: list[HourCount]) -> None:
    with conn.cursor() as cur:
        cur.executemany(
            """
            insert into pedestrian_hourly (location_id, hour, count, is_partial)
            values (%s, %s, %s, %s)
            on conflict (location_id, hour) do update
              set count = excluded.count, is_partial = excluded.is_partial
            """,
            [(h.location_id, h.hour, h.count, h.is_partial) for h in hours],
        )


def upsert_parking_hour(conn: psycopg.Connection, hour: datetime, stats: dict) -> None:
    conn.execute(
        """
        insert into parking_hourly (hour, bays_free, bays_occupied, bays_stale, pct_free)
        values (%(hour)s, %(bays_free)s, %(bays_occupied)s, %(bays_stale)s, %(pct_free)s)
        on conflict (hour) do update
          set bays_free = excluded.bays_free, bays_occupied = excluded.bays_occupied,
              bays_stale = excluded.bays_stale, pct_free = excluded.pct_free
        """,
        {"hour": hour, **stats},
    )


def typicals_for(conn: psycopg.Connection, target: datetime) -> dict[int, float]:
    """Typical count per sensor for the hour starting at `target`.

    SQL narrows to the right local hour and date range; the exact weekday,
    8-week window and median are done in Python (pulse.typical, unit-tested).
    """
    rows = conn.execute(
        """
        select location_id, hour, count, is_partial
        from pedestrian_hourly
        where hour >= %(since)s and hour < %(target)s
          and not is_partial
          -- an hour when the feed itself looked faulty says nothing about what is typical
          and not exists (select 1 from feed_quality q where q.hour = pedestrian_hourly.hour and q.anomaly)
          and extract(hour from hour at time zone 'Australia/Melbourne')
              = extract(hour from %(target)s at time zone 'Australia/Melbourne')
        """,
        {"since": history_since(target), "target": target},
    ).fetchall()
    return typical_by_sensor(rows, target)


def feed_anomaly(conn: psycopg.Connection, hour: datetime) -> dict | None:
    """The feed-quality assessment for `hour` if it was flagged as an anomaly, else None."""
    row = conn.execute(
        "select sensors_judged, sensors_low, share_low, reason from feed_quality where hour = %s and anomaly", (hour,)
    ).fetchone()
    return dict(zip(("judged", "low", "share", "reason"), row)) if row else None


def upcoming_weather(conn: psycopg.Connection, hours: int = 12) -> list[dict]:
    """Stored forecast rows from the hour in progress onwards (see weather_forecast.py)."""
    rows = conn.execute(
        """
        select hour, precipitation, precipitation_probability, fetched_at
        from weather_forecast
        where hour >= date_trunc('hour', now()) and hour < date_trunc('hour', now()) + make_interval(hours => %s)
        order by hour
        """,
        (hours,),
    ).fetchall()
    return [dict(zip(("hour", "precipitation", "precipitation_probability", "fetched_at"), r)) for r in rows]


def trim(conn: psycopg.Connection) -> dict[str, int]:
    deleted = {}
    for table in ("pedestrian_hourly", "parking_hourly"):
        cur = conn.execute(
            f"delete from {table} where hour < now() - make_interval(days => %s)",
            (RETENTION_DAYS,),
        )
        deleted[table] = cur.rowcount
    return deleted
