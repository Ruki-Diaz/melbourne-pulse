"""Hours the pipeline flagged as a fault in the city's sensor feed (pipeline/feed_quality.py).

A flagged hour is not evidence of how busy the city was, so it is left out of
the model twice over: it is never a training example, and it is never used as
history ("same hour last week") for another hour. features.build falls back to
the next week that isn't flagged.

The flags live in the feed_quality table. Without DATABASE_URL (a dry run, CI)
nothing is excluded, and that is said in the log.
"""

from __future__ import annotations

import os

import numpy as np
import pandas as pd

import data  # noqa: F401  (puts ../pipeline on sys.path)
from pulse.timeutil import MEL


def keys(dates: pd.Series, hours) -> np.ndarray:
    """One integer per (local date, local hour): what features.build matches on."""
    days = pd.to_datetime(pd.Series(dates).reset_index(drop=True)).dt.normalize()
    return (days.astype("datetime64[s]").astype("int64") // 86_400 * 24 + np.asarray(hours, dtype="int64")).to_numpy()


def from_utc(hours: list) -> frozenset[int]:
    """Flagged UTC hour starts -> keys by Melbourne local date and hour."""
    if not hours:
        return frozenset()
    local = pd.Series(pd.to_datetime(hours, utc=True)).dt.tz_convert(MEL)
    return frozenset(keys(local.dt.tz_localize(None), local.dt.hour).tolist())


def flagged() -> frozenset[int]:
    """Keys of every flagged hour, or an empty set (logged) if the database isn't available."""
    if not os.environ.get("DATABASE_URL"):
        print("  DATABASE_URL not set: no feed-anomaly hours are excluded")
        return frozenset()
    from pulse import db

    with db.connect() as conn:
        hours = [row[0] for row in conn.execute("select hour from feed_quality where anomaly order by hour")]
    return from_utc(hours)
