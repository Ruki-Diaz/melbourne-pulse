"""Shared fixtures.

tests/fixtures/ holds real API responses saved on 2026-10-01 (see docs/data.md):
  pedestrian_minutes.json  per-minute feed, 2026-09-29 14:00-17:00Z, sensors 3, 4
                           (1-minute) and 5, 41 (5-minute), zero minutes omitted
  monthly_hours.json       the city's own hourly totals for the same hours
                           (local 2026-09-30 00:00-03:00) - ground truth
  parking.json             40 oldest + 40 newest bays by lastupdated
  sensor_locations.json    metadata for the four sensors
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str):
    return json.loads((FIXTURES / name).read_text())


def utc(*args) -> datetime:
    return datetime(*args, tzinfo=timezone.utc)


@pytest.fixture
def minute_rows():
    return load("pedestrian_minutes.json")


@pytest.fixture
def monthly_rows():
    return load("monthly_hours.json")


@pytest.fixture
def parking_rows():
    return load("parking.json")


@pytest.fixture
def location_rows():
    return load("sensor_locations.json")
