"""Open-Meteo client for the Melbourne CBD (free, no API key).

Two feeds:
  forecast()  the next 48 hours, for the Plan page (weather_forecast.py)
  observed()  what the weather actually was, for measuring the rain effect
              (rain_effect.py). The forecast *model* never uses this; see
              model/weather.py.

Two things Open-Meteo does that this module corrects:

- Local time is labelled with one fixed UTC offset per request, which is wrong
  on one side of a DST change. Times are requested as unix seconds (always
  UTC), the same way model/weather.py does it.
- Rain is reported for the hour *before* each timestamp ("preceding hour
  sum"), while a pedestrian count belongs to the hour *after* its timestamp.
  Rain values are moved back one hour here, so every row describes the hour
  that starts at `hour`. Temperature, wind and weather code are readings at
  the timestamp and are left where they are.
"""

from __future__ import annotations

import time
from datetime import date, datetime, timedelta

import requests

from .api import HEADERS
from .timeutil import HOUR, UTC

LATITUDE, LONGITUDE = -37.8136, 144.9631
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_HOURS = 48
RETRIES = 2  # retries after the first attempt
TIMEOUT_S = 30

# Open-Meteo name -> our name. PRECEDING variables cover the hour before their timestamp.
FORECAST_VARIABLES = {
    "precipitation": "precipitation",
    "precipitation_probability": "precipitation_probability",
    "temperature_2m": "temperature",
    "wind_speed_10m": "wind_speed",
    "weather_code": "weather_code",
}
OBSERVED_VARIABLES = {"precipitation": "precipitation", "temperature_2m": "temperature"}
PRECEDING = {"precipitation", "precipitation_probability"}


def _get(url: str, hourly: list[str], **params) -> dict:
    query = {
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "timezone": "Australia/Melbourne",
        "timeformat": "unixtime",
        "hourly": ",".join(hourly),
        **params,
    }
    for attempt in range(RETRIES + 1):
        try:
            resp = requests.get(url, params=query, headers=HEADERS, timeout=TIMEOUT_S)
            resp.raise_for_status()
            body = resp.json()
            if "time" not in body.get("hourly", {}):
                raise ValueError(f"no hourly data in response: {str(body)[:200]}")
            return body["hourly"]
        except (requests.RequestException, ValueError) as exc:
            if attempt == RETRIES:
                raise
            wait = 2 ** (attempt + 1)
            print(f"  open-meteo: attempt {attempt + 1} failed ({exc}); retrying in {wait}s")
            time.sleep(wait)
    raise AssertionError("unreachable")


def hourly_rows(hourly: dict, variables: dict[str, str]) -> list[dict]:
    """Open-Meteo's `hourly` block -> one dict per hour: {"hour": UTC hour start, <our names>}.

    Only hours whose own timestamp is in the response are returned. A missing
    value is None, never 0, so "no data" can't be mistaken for "no rain".
    """
    stamps = [datetime.fromtimestamp(t, UTC) for t in hourly["time"]]
    rows = {stamp: {"hour": stamp, **{ours: None for ours in variables.values()}} for stamp in stamps}
    for theirs, ours in variables.items():
        shift = HOUR if ours in PRECEDING else timedelta(0)
        for stamp, value in zip(stamps, hourly[theirs]):
            row = rows.get(stamp - shift)
            if row is not None:
                row[ours] = value
    return [rows[stamp] for stamp in sorted(rows)]


def forecast() -> list[dict]:
    """The next 48 hours, starting with the hour now in progress."""
    # One extra timestamp: the rain for the 48th hour is stamped at the 49th.
    hourly = _get(FORECAST_URL, list(FORECAST_VARIABLES), forecast_hours=FORECAST_HOURS + 1)
    return hourly_rows(hourly, FORECAST_VARIABLES)[:FORECAST_HOURS]


def observed(first: date, last: date) -> list[dict]:
    """Observed rain and temperature for every hour of local dates [first, last].

    Asks for a day either side, because Open-Meteo's day boundaries can be an
    hour off ours near DST and the rain for the last hour is stamped an hour
    later. Callers match rows to counts by `hour`, so the extra rows are harmless.
    The newest few days may not be published yet; their values are None.
    """
    # The archive rejects dates after today (UTC).
    newest = datetime.now(UTC).date()
    hourly = _get(
        ARCHIVE_URL,
        list(OBSERVED_VARIABLES),
        start_date=str(min(first - timedelta(days=1), newest)),
        end_date=str(min(last + timedelta(days=1), newest)),
    )
    return hourly_rows(hourly, OBSERVED_VARIABLES)
