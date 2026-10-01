"""Hourly weather *forecasts* for the Melbourne CBD from Open-Meteo (free, no API key).

The model only ever sees forecasts, never observed weather, because a forecast
is all predict.py has when it runs. Three sources:

  history(lead="latest")  Historical Forecast API: the first few hours of each
                          past model run stitched together, so every value was
                          issued just before the hour it describes.
  history(lead="day1")    Previous Runs API: the value that was predicted 24 h
                          before the hour. predict.py's forecasts are 1-36 h
                          old when used, so "latest" is fresher than production
                          and "day1" is about as old as it gets. See REPORT.md.
  forecast()              the live forecast, for predict.py.

Open-Meteo labels local time with one fixed UTC offset per request, which is
wrong on one side of a DST change. So times are requested as unix seconds
(always UTC) and converted here: rows are keyed by Melbourne local date + hour
like the rest of the model, and the repeated 02:00 at the end of daylight
saving is dropped, as data.clean does.
"""

from __future__ import annotations

import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests

import data  # noqa: F401  (puts ../pipeline on sys.path)
from pulse.api import HEADERS
from pulse.timeutil import MEL

CACHE = data.CACHE
LATITUDE, LONGITUDE = -37.8136, 144.9631
VARIABLES = {"precipitation": "precipitation", "temperature_2m": "temperature", "wind_speed_10m": "wind"}
URLS = {
    "latest": "https://historical-forecast-api.open-meteo.com/v1/forecast",
    "day1": "https://previous-runs-api.open-meteo.com/v1/forecast",
}
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
SUFFIX = {"latest": "", "day1": "_previous_day1"}
FORECAST_HOURS = 48
RETRIES = 2  # retries after the first attempt
TIMEOUT_S = 30
COLUMNS = ["ts", "date", "hour", "precipitation", "temperature", "wind", "precip_3h"]


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


def _parse(hourly: dict, suffix: str = "") -> pd.DataFrame:
    """Open-Meteo's `hourly` block -> ts (UTC hour start) + one column per variable."""
    frame = pd.DataFrame({"ts": pd.to_datetime(hourly["time"], unit="s", utc=True)})
    for theirs, ours in VARIABLES.items():
        frame[ours] = pd.to_numeric(pd.Series(hourly[theirs + suffix]), errors="coerce").astype(float)
    return frame


def keyed(frame: pd.DataFrame) -> pd.DataFrame:
    """Add local date/hour keys and precip_3h; drop the repeated autumn 02:00.

    precip_3h is the rain forecast for this hour and the two real hours before
    it, so it is as old as the forecast itself and never looks past the hour.
    """
    frame = frame.drop_duplicates("ts").sort_values("ts").reset_index(drop=True)
    by_ts = frame.set_index("ts")["precipitation"]
    # Built from explicit timestamps, not row offsets, so a gap gives NaN rather than a wrong sum.
    frame["precip_3h"] = sum(by_ts.reindex(frame["ts"] - pd.Timedelta(hours=k)).to_numpy() for k in range(3))
    stamps = frame["ts"].dt.tz_convert(MEL)
    frame["date"] = pd.to_datetime(stamps.dt.tz_localize(None).dt.normalize())
    frame["hour"] = stamps.dt.hour
    frame = frame[~frame.duplicated(["date", "hour"], keep=False)]
    return frame[COLUMNS].reset_index(drop=True)


def history(first: date, last: date, lead: str = "latest", cache: bool = False) -> pd.DataFrame:
    """Past forecasts for local dates [first, last], fetched a month at a time.

    Closed months are immutable, so with cache=True they are saved under
    model/.cache and only the current month is re-downloaded.
    """
    suffix = SUFFIX[lead]
    frames = []
    first -= timedelta(days=1)  # precip_3h needs the two hours before `first`
    for start in data._month_starts(first, last):
        end = min((start + timedelta(days=32)).replace(day=1), last + timedelta(days=1))
        path = CACHE / f"weather-{lead}-{start:%Y-%m}.csv.gz"
        closed = end <= last
        if cache and closed and path.exists():
            frames.append(pd.read_csv(path, parse_dates=["ts"]))
            continue
        lo = max(start, first)
        print(f"  downloading {lead} weather {lo} .. {end - timedelta(days=1)}")
        # A day either side: Open-Meteo's day boundaries can be an hour off ours near DST.
        hourly = _get(
            URLS[lead],
            [name + suffix for name in VARIABLES],
            start_date=str(lo - timedelta(days=1)),
            end_date=str(end),
        )
        frame = _parse(hourly, suffix)
        local_day = frame["ts"].dt.tz_convert(MEL).dt.date
        frame = frame[(local_day >= lo) & (local_day < end)]
        if cache and closed:
            CACHE.mkdir(exist_ok=True)
            frame.to_csv(path, index=False)
        frames.append(frame)
    return keyed(pd.concat(frames, ignore_index=True))


def forecast() -> pd.DataFrame:
    """The live forecast for the next 48 hours (plus the 2 past hours precip_3h needs)."""
    return keyed(_parse(_get(FORECAST_URL, list(VARIABLES), forecast_hours=FORECAST_HOURS, past_hours=2)))
