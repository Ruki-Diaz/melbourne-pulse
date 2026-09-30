"""Melbourne Pulse - hourly ingest of City of Melbourne live sensor data.

Pulls the parking-bay sensor and pedestrian past-hour datasets, stores a raw
snapshot of each, keeps a `latest` row per source for the live map, and trims
snapshots older than RETENTION_DAYS so the free database never fills up.

Raw JSON is stored on purpose: if the city renames a field, ingest keeps
working and only the frontend/model code needs a tweak.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import requests

if TYPE_CHECKING:
    import psycopg

BASE_URL = os.getenv(
    "COM_API_BASE",
    "https://data.melbourne.vic.gov.au/api/explore/v2.1/catalog/datasets",
)

# Dataset IDs are the last part of each dataset's URL on data.melbourne.vic.gov.au.
# Override with env vars if the city ever renames one.
DATASETS = {
    "parking": os.getenv("PARKING_DATASET_ID", "on-street-parking-bay-sensors"),
    "pedestrian": os.getenv(
        "PEDESTRIAN_DATASET_ID",
        "pedestrian-counting-system-past-hour-counts-per-minute",
    ),
}

RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", "3"))
TIMEOUT_S = 60
RETRIES = 3


def fetch_dataset(dataset_id: str) -> list[dict]:
    """Download every record of a dataset via the Opendatasoft JSON export."""
    url = f"{BASE_URL}/{dataset_id}/exports/json"
    headers = {"User-Agent": "melbourne-pulse/0.1 (portfolio project)"}

    for attempt in range(1, RETRIES + 1):
        try:
            resp = requests.get(url, headers=headers, timeout=TIMEOUT_S)
            resp.raise_for_status()
            data = resp.json()
            if not isinstance(data, list):
                raise ValueError(f"expected a JSON list, got {type(data).__name__}")
            return data
        except (requests.RequestException, ValueError) as exc:
            if attempt == RETRIES:
                raise
            wait = 2**attempt
            print(f"  attempt {attempt} failed ({exc}); retrying in {wait}s")
            time.sleep(wait)
    return []  # unreachable


def save(conn: psycopg.Connection, source: str, records: list[dict]) -> None:
    from psycopg.types.json import Jsonb

    now = datetime.now(timezone.utc)
    payload = Jsonb(records)
    with conn.cursor() as cur:
        cur.execute(
            "insert into snapshots (source, fetched_at, record_count, payload) "
            "values (%s, %s, %s, %s)",
            (source, now, len(records), payload),
        )
        cur.execute(
            """
            insert into latest (source, fetched_at, record_count, payload)
            values (%s, %s, %s, %s)
            on conflict (source) do update
              set fetched_at = excluded.fetched_at,
                  record_count = excluded.record_count,
                  payload = excluded.payload
            """,
            (source, now, len(records), payload),
        )


def trim_old(conn: psycopg.Connection) -> int:
    with conn.cursor() as cur:
        cur.execute(
            "delete from snapshots where fetched_at < now() - make_interval(days => %s)",
            (RETENTION_DAYS,),
        )
        return cur.rowcount


def dry_run() -> int:
    """Fetch each feed and print its shape without touching the database."""
    failures = []
    for source, dataset_id in DATASETS.items():
        print(f"[{source}] fetching {dataset_id}")
        try:
            records = fetch_dataset(dataset_id)
        except Exception as exc:
            print(f"[{source}] FAILED: {exc}", file=sys.stderr)
            failures.append(source)
            continue
        print(f"[{source}] {len(records)} records")
        if not records:
            failures.append(source)
            continue
        print(f"[{source}] first record keys: {list(records[0].keys())}")

    if failures:
        print(f"failed sources: {', '.join(failures)}", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="fetch and print record counts and field names; no database needed",
    )
    if parser.parse_args().dry_run:
        return dry_run()

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL is not set", file=sys.stderr)
        return 1

    import psycopg

    failures = []
    with psycopg.connect(db_url) as conn:
        for source, dataset_id in DATASETS.items():
            print(f"[{source}] fetching {dataset_id}")
            try:
                records = fetch_dataset(dataset_id)
            except Exception as exc:  # keep going so one bad feed doesn't block the other
                print(f"[{source}] FAILED: {exc}", file=sys.stderr)
                failures.append(source)
                continue

            if not records:
                print(f"[{source}] WARNING: 0 records returned, skipping save")
                failures.append(source)
                continue

            save(conn, source, records)
            conn.commit()
            print(f"[{source}] saved {len(records)} records")

        deleted = trim_old(conn)
        conn.commit()
        print(f"trimmed {deleted} snapshots older than {RETENTION_DAYS} days")

    if failures:
        print(f"failed sources: {', '.join(failures)}", file=sys.stderr)
        return 1  # makes the GitHub Action show red so you notice
    return 0


if __name__ == "__main__":
    sys.exit(main())
