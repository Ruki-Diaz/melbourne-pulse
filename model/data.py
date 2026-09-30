"""Download and clean hourly pedestrian history from the City of Melbourne."""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

# Share the pipeline's API client, DST handling and zero-filling rules.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))

from pulse import api  # noqa: E402
from pulse.history import complete_days  # noqa: E402

CACHE = Path(__file__).parent / ".cache"


def _month_starts(first: date, last: date) -> list[date]:
    months, d = [], first.replace(day=1)
    while d <= last:
        months.append(d)
        d = (d + timedelta(days=32)).replace(day=1)
    return months


def download(first: date, last: date, cache: bool = False) -> pd.DataFrame:
    """Raw rows for local dates [first, last], fetched a month at a time.

    Closed months are immutable, so with cache=True they are saved under
    model/.cache and only the current month is re-downloaded.
    """
    frames = []
    for start in _month_starts(first, last):
        end = min((start + timedelta(days=32)).replace(day=1), last + timedelta(days=1))
        path = CACHE / f"{start:%Y-%m}.csv.gz"
        closed = end <= last  # the month ended before `last`, so it won't change
        if cache and closed and path.exists():
            frames.append(pd.read_csv(path))
            continue
        lo = max(start, first)
        print(f"  downloading {lo} .. {end - timedelta(days=1)}")
        rows = api.export(
            api.PEDESTRIAN_HOURLY,
            select="location_id,sensing_date,hourday,pedestriancount",
            where=f"sensing_date >= date'{lo}' and sensing_date < date'{end}'",
        )
        frame = pd.DataFrame(rows, columns=["location_id", "sensing_date", "hourday", "pedestriancount"])
        if cache and closed:
            CACHE.mkdir(exist_ok=True)
            frame.to_csv(path, index=False)
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def clean(raw: pd.DataFrame) -> pd.DataFrame:
    """Complete up sensor-days with zeros; drop the partial newest day and DST-invalid hours.

    Returns columns: location_id, date (datetime64, local), hour (local 0-23),
    ts (UTC hour start), count.
    """
    dates = pd.to_datetime(raw["sensing_date"].astype(str).str[:10]).dt.date
    newest = dates.max()  # the city loads ~1 day behind: the newest day is partial
    keep = dates < newest
    rows = zip(
        raw["location_id"][keep].astype(int),
        dates[keep],
        raw["hourday"][keep].astype(int),
        raw["pedestriancount"][keep].astype(int),
    )
    out = pd.DataFrame(complete_days(rows), columns=["location_id", "date", "hour", "ts", "count"])
    out["date"] = pd.to_datetime(out["date"])
    out["ts"] = pd.to_datetime(out["ts"], utc=True)
    return out
