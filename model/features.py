"""Feature engineering, shared by train.py and predict.py.

Rule: a forecast is made up to 24 h ahead, so every feature must be known 24 h
before the hour it predicts. All history features look back whole weeks (>= 7
days), never "yesterday" or "an hour ago". Lags are matched on local date and
local hour, so "same hour last week" stays 9am-to-9am across a DST change,
exactly like the app's 'typical'.
"""

from __future__ import annotations

import warnings
from functools import lru_cache

import holidays
import numpy as np
import pandas as pd

WEEKS = 8  # the app's 'typical' window

BASE = [
    "sensor",
    "hour",
    "dow",
    "month",
    "public_holiday",
    "lag_1w",
    "lag_2w",
    "typical_8w",
    "mean_4w",
    "weeks_available",
    "day_total_1w",
    "lag_1w_holiday",
]
# Extra features tried if BASE doesn't beat 'typical'. See REPORT.md.
EXTRA = ["school_holiday", "down_days_4w"]

# Victorian school holidays, the gaps between terms listed at
# vic.gov.au/school-term-dates-and-holidays-victoria (checked 2026-10-01).
# The `holidays` package only covers 2026+, so 2024-25 are listed here.
SCHOOL_HOLIDAYS_2024_25 = [
    ("2024-09-21", "2024-10-06"),
    ("2024-12-21", "2025-01-27"),
    ("2025-04-05", "2025-04-21"),
    ("2025-07-05", "2025-07-20"),
    ("2025-09-20", "2025-10-05"),
    ("2025-12-20", "2025-12-31"),
]


@lru_cache(maxsize=None)
def _holiday_dates(category: str, years: tuple[int, ...]) -> frozenset:
    days = set(holidays.country_holidays("AU", subdiv="VIC", years=years, categories=(category,)))
    if category == "school":
        for start, end in SCHOOL_HOLIDAYS_2024_25:
            days.update(pd.date_range(start, end).date)
    return frozenset(days)


def is_holiday(dates: pd.Series, category: str = "public") -> np.ndarray:
    years = tuple(sorted(set(dates.dt.year) | set((dates - pd.Timedelta(days=7)).dt.year)))
    days = _holiday_dates(category, years)
    return dates.dt.date.isin(days).to_numpy()


def build(targets: pd.DataFrame, history: pd.DataFrame, columns: list[str] = BASE) -> pd.DataFrame:
    """Features for each (location_id, date, hour) in `targets`, using `history`.

    `history` has location_id, date, hour, count (cleaned by data.clean: up
    sensor-days complete with zeros, down sensor-days absent).
    """
    counts = history.set_index(["location_id", "date", "hour"])["count"]
    day_totals = history.groupby(["location_id", "date"])["count"].sum()

    sensor = targets["location_id"].to_numpy()
    date = pd.to_datetime(targets["date"]).reset_index(drop=True)
    hour = targets["hour"].to_numpy()

    def weeks_back(k: int) -> pd.Series:
        return date - pd.Timedelta(days=7 * k)

    lags = np.column_stack(
        [
            counts.reindex(pd.MultiIndex.from_arrays([sensor, weeks_back(k), hour])).to_numpy(dtype=float)
            for k in range(1, WEEKS + 1)
        ]
    )
    with warnings.catch_warnings():  # all-NaN rows (new sensor) are expected -> NaN
        warnings.simplefilter("ignore", RuntimeWarning)
        typical = np.nanmedian(lags, axis=1)
        mean_4w = np.nanmean(lags[:, :4], axis=1)

    def day_total(k: int) -> np.ndarray:
        return day_totals.reindex(pd.MultiIndex.from_arrays([sensor, weeks_back(k)])).to_numpy(dtype=float)

    all_features = {
        "sensor": sensor,
        "hour": hour,
        "dow": date.dt.dayofweek.to_numpy(),
        "month": date.dt.month.to_numpy(),
        "public_holiday": is_holiday(date),
        "lag_1w": lags[:, 0],
        "lag_2w": lags[:, 1],
        "typical_8w": typical,
        "mean_4w": mean_4w,
        "weeks_available": np.isfinite(lags).sum(axis=1),
        "day_total_1w": day_total(1),
        "lag_1w_holiday": is_holiday(weeks_back(1)),
        "school_holiday": is_holiday(date, "school"),
        # sensor-days with no data among the 4 same-weekdays used for mean_4w
        "down_days_4w": sum(np.isnan(day_total(k)) for k in range(1, 5)),
    }
    return pd.DataFrame({name: all_features[name] for name in columns})
