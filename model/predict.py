"""Forecast the next 36 hours for every active sensor and write them to `forecasts`.

Runs daily from GitHub Actions (~4am Melbourne). 36 hours, not 24, so the site
always has at least 24 hours ahead even just before the next daily run. Re-running is safe: rows are
upserted on (sensor_id, hour), and forecasts more than 2 days old are removed.
History comes from the same city dataset the model was trained on.

If the shipped model uses weather features, the Open-Meteo forecast is fetched
here. If that fails, this run uses the weather-free fallback model instead, so
the daily job never fails because of the weather service.
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

import data  # also puts ../pipeline on sys.path
import features
import weather
from pulse.timeutil import HOUR, UTC, floor_hour, hours_from, local

HERE = Path(__file__).parent
HISTORY_WEEKS = features.WEEKS + 2  # 8 for 'typical', plus slack for the data lag
ACTIVE_DAYS = 14  # sensors with no data for 2 weeks are treated as retired
HORIZON_HOURS = 36


def targets_for(history: pd.DataFrame, now: datetime) -> pd.DataFrame:
    """Next HORIZON_HOURS real hours x active sensors, keyed by local date/hour for features."""
    hours = hours_from(floor_hour(now) + HOUR, HORIZON_HOURS)
    recent = history["date"] >= history["date"].max() - pd.Timedelta(days=ACTIVE_DAYS - 1)
    sensors = sorted(history.loc[recent, "location_id"].unique())
    return pd.DataFrame(
        [
            (int(lid), pd.Timestamp(local(h).date()), local(h).hour, h)
            for lid in sensors
            for h in hours
        ],
        columns=["location_id", "date", "hour", "ts"],
    )


def forecast(
    history: pd.DataFrame,
    now: datetime,
    booster: lgb.Booster,
    columns: list[str],
    forecasts: pd.DataFrame | None = None,
) -> pd.DataFrame:
    targets = targets_for(history, now)
    X = features.build(targets, history, columns, forecasts)
    baseline = features.build(targets, history, ["typical_8w"])["typical_8w"].to_numpy()
    return pd.DataFrame(
        {
            "sensor_id": targets["location_id"],
            "hour": targets["ts"],
            "predicted_count": np.clip(booster.predict(X), 0, None).round(1),
            "baseline_count": np.where(np.isfinite(baseline), baseline, np.nan),
        }
    )


def load_model(name: str) -> lgb.Booster:
    with gzip.open(HERE / name, "rt") as f:
        return lgb.Booster(model_str=f.read())


def weather_for(history: pd.DataFrame, now: datetime) -> pd.DataFrame:
    """The Open-Meteo forecast, checked to cover every hour being predicted."""
    forecasts = weather.forecast()
    hours = targets_for(history, now).drop_duplicates("ts")
    covered = features.build(hours, history, features.WEATHER, forecasts)
    missing = int(covered.isna().any(axis=1).sum())
    if missing:
        raise ValueError(f"weather forecast is missing {missing} of the {len(hours)} hours")
    return forecasts


def choose_model(meta: dict, history: pd.DataFrame, now: datetime) -> tuple[str, list[str], pd.DataFrame | None]:
    """(model file, feature columns, weather forecast) for this run.

    A model without weather features never calls Open-Meteo. One with them
    falls back to the weather-free model if the forecast can't be fetched.
    """
    if not set(meta["columns"]) & set(features.WEATHER):
        return "model.txt.gz", meta["columns"], None
    try:
        return "model.txt.gz", meta["columns"], weather_for(history, now)
    except Exception as exc:  # noqa: BLE001 - any weather problem must not stop the daily job
        fallback = meta["fallback"]
        print(f"WARNING: weather forecast unavailable ({exc}); using the fallback model {fallback['file']}")
        return fallback["file"], fallback["columns"], None


def save(rows: pd.DataFrame) -> None:
    from pulse import db

    records = [
        (int(r.sensor_id), r.hour.to_pydatetime(), float(r.predicted_count),
         None if pd.isna(r.baseline_count) else float(r.baseline_count))
        for r in rows.itertuples()
    ]
    with db.connect() as conn, conn.transaction():
        with conn.cursor() as cur:
            cur.executemany(
                """
                insert into forecasts (sensor_id, hour, predicted_count, baseline_count, generated_at)
                values (%s, %s, %s, %s, now())
                on conflict (sensor_id, hour) do update
                  set predicted_count = excluded.predicted_count,
                      baseline_count = excluded.baseline_count,
                      generated_at = excluded.generated_at
                """,
                records,
            )
        deleted = conn.execute("delete from forecasts where hour < now() - interval '2 days'").rowcount
    print(f"saved {len(records):,} forecasts; removed {deleted:,} older than 2 days")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="forecast and print; no database")
    args = parser.parse_args()

    meta = json.loads((HERE / "model_meta.json").read_text())

    now = datetime.now(UTC)
    today = local(now).date()
    print(f"loading {HISTORY_WEEKS} weeks of history")
    history = data.clean(data.download(today - timedelta(weeks=HISTORY_WEEKS), today))
    model_file, columns, forecasts = choose_model(meta, history, now)
    rows = forecast(history, now, load_model(model_file), columns, forecasts)

    first, last = local(rows["hour"].min()), local(rows["hour"].max())
    print(
        f"{rows['sensor_id'].nunique()} sensors x {rows['hour'].nunique()} hours "
        f"({first:%a %d %b %H:00} - {last:%a %d %b %H:00 %Z}); history to {history['date'].max().date()}"
    )
    totals = rows.groupby("hour")[["predicted_count", "baseline_count"]].sum()
    peak = totals["predicted_count"].idxmax()
    print(
        f"busiest hour {local(peak):%a %H:00}: {totals.loc[peak, 'predicted_count']:,.0f} people forecast "
        f"across all sensors (typical {totals.loc[peak, 'baseline_count']:,.0f})"
    )

    if args.dry_run:
        print(rows.head(3).to_string(index=False))
        print("dry run: nothing written")
        return 0
    save(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
