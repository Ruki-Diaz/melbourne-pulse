"""Hours the pipeline flagged and nobody has settled yet (pipeline/feed_quality.py).

Until a flagged hour is resolved it is not known whether its counts can be
trusted, so it is left out of the model twice over: it is never a training
example, and it is never used as history ("same hour last week") for another
hour. features.build falls back to the next week that isn't flagged.

The flags live in the feed_quality table. Once the daily audit has compared an
hour with the city's published totals (pipeline/audit.py --resolve) it is used
again, whichever way it went: "confirmed real" is ordinary data, and "confirmed
fault" means our live table was short, while this model reads the city's final
figures, which are correct. Only unresolved hours are excluded. predict.py tolerates a missing DATABASE_URL in a dry run (nothing is
excluded, and the log says so); train.py refuses to run without it unless
told to with --no-quality-flags.
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


# Flagged and not yet compared with the city's figures: the only hours the model skips.
UNRESOLVED = "select hour from feed_quality where anomaly and resolution is null order by hour"


class FlagsUnavailable(RuntimeError):
    """The flags were required but the database isn't configured."""


def flagged(required: bool = False) -> frozenset[int]:
    """Keys of every flagged hour.

    Without DATABASE_URL: an empty set (logged), or FlagsUnavailable if `required`.
    """
    if not os.environ.get("DATABASE_URL"):
        if required:
            raise FlagsUnavailable(
                "DATABASE_URL is not set, so the hours flagged in feed_quality can't be read and would be "
                "trained on as if they were normal. Set DATABASE_URL, or pass --no-quality-flags to train without them."
            )
        print("  DATABASE_URL not set: no feed-anomaly hours are excluded")
        return frozenset()
    from pulse import db

    with db.connect() as conn:
        hours = [row[0] for row in conn.execute(UNRESOLVED)]
    return from_utc(hours)
