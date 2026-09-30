"""City of Melbourne Open Data (Opendatasoft Explore v2.1) client.

Field names and quirks are documented in docs/data.md.
"""

from __future__ import annotations

import os
import time

import requests

BASE_URL = os.getenv(
    "COM_API_BASE",
    "https://data.melbourne.vic.gov.au/api/explore/v2.1/catalog/datasets",
)

PARKING = "on-street-parking-bay-sensors"
PEDESTRIAN_MINUTES = "pedestrian-counting-system-past-hour-counts-per-minute"
SENSOR_LOCATIONS = "pedestrian-counting-system-sensor-locations"
PEDESTRIAN_HOURLY = "pedestrian-counting-system-monthly-counts-per-hour"

RETRIES = 3  # retries after the first attempt
TIMEOUT_S = 90
HEADERS = {"User-Agent": "melbourne-pulse (github.com/Ruki-Diaz/melbourne-pulse)"}


def export(dataset_id: str, **params: str) -> list[dict]:
    """Fetch a dataset through /exports/json (no row limit), retrying with backoff.

    `params` are passed through as ODSQL (`where`, `select`, `order_by`, ...).
    """
    url = f"{BASE_URL}/{dataset_id}/exports/json"
    for attempt in range(RETRIES + 1):
        try:
            resp = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT_S)
            resp.raise_for_status()
            data = resp.json()
            if not isinstance(data, list):
                raise ValueError(f"expected a JSON list, got {type(data).__name__}")
            return data
        except (requests.RequestException, ValueError) as exc:
            if attempt == RETRIES:
                raise
            wait = 2 ** (attempt + 1)
            print(f"  {dataset_id}: attempt {attempt + 1} failed ({exc}); retrying in {wait}s")
            time.sleep(wait)
    raise AssertionError("unreachable")


def odsql_ts(dt) -> str:
    """Format an aware datetime as an ODSQL date literal."""
    return f"date'{dt.strftime('%Y-%m-%dT%H:%M:%SZ')}'"
