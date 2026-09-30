"""Train and evaluate the pedestrian forecast; write model.txt.gz, REPORT.md and chart.png.

Split (strictly by time, never shuffled):
  train       everything before the last 16 weeks
  validation  weeks 16-9 from the end (early stopping + choosing the objective)
  test        the last 8 weeks, touched once for the final comparison
The shipped model is then refit on all data with the chosen settings.
"""

from __future__ import annotations

import argparse
import gzip
import json
from datetime import date, datetime, timedelta
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

import data
import features
import report

HERE = Path(__file__).parent
TEST_WEEKS = 8
VAL_WEEKS = 8
MAPE_MIN = 10  # MAPE is undefined at 0 and explodes near it: only score hours with >= 10 people
OBJECTIVES = ["l1", "poisson", "tweedie"]
PARAMS = {
    "learning_rate": 0.1,
    "num_leaves": 63,
    "min_data_in_leaf": 200,
    "feature_fraction": 0.9,
    "bagging_fraction": 0.8,
    "bagging_freq": 1,
    "lambda_l2": 1.0,
    "verbose": -1,
    "seed": 7,
    "num_threads": 0,
}


def mae(y, p) -> float:
    return float(np.mean(np.abs(y - p)))


def mape(y, p) -> float:
    m = y >= MAPE_MIN
    return float(np.mean(np.abs(y[m] - p[m]) / y[m]) * 100)


def fit(X, y, objective, rounds, valid=None):
    params = {**PARAMS, "objective": objective, "metric": "l1"}
    train_set = lgb.Dataset(X, y, categorical_feature=["sensor"], free_raw_data=False)
    kwargs = {}
    if valid is not None:
        kwargs["valid_sets"] = [lgb.Dataset(*valid, categorical_feature=["sensor"], reference=train_set)]
        kwargs["callbacks"] = [lgb.early_stopping(50, verbose=False)]
    return lgb.train(params, train_set, num_boost_round=rounds, **kwargs)


def run(hist: pd.DataFrame, columns: list[str]) -> dict:
    X_all = features.build(hist, hist, columns)
    y_all = hist["count"].to_numpy(dtype=float)
    d = hist["date"].reset_index(drop=True)
    last = d.max()
    test_start = last - pd.Timedelta(weeks=TEST_WEEKS) + pd.Timedelta(days=1)
    val_start = test_start - pd.Timedelta(weeks=VAL_WEEKS)

    usable = (X_all["weeks_available"] > 0).to_numpy()  # need at least one past week
    train = usable & (d < val_start).to_numpy()
    val = usable & ((d >= val_start) & (d < test_start)).to_numpy()
    test = usable & (d >= test_start).to_numpy()

    # 1. pick the objective and number of trees on validation
    trials = {}
    for objective in OBJECTIVES:
        booster = fit(X_all[train], y_all[train], objective, 1500, valid=(X_all[val], y_all[val]))
        pred = np.clip(booster.predict(X_all[val], num_iteration=booster.best_iteration), 0, None)
        trials[objective] = {"val_mae": mae(y_all[val], pred), "rounds": booster.best_iteration}
        print(f"  {objective:>8}: val MAE {trials[objective]['val_mae']:.2f} at {booster.best_iteration} trees")
    objective = min(trials, key=lambda k: trials[k]["val_mae"])
    rounds = trials[objective]["rounds"]

    # 2. refit on train+validation, score the untouched test weeks once
    booster = fit(X_all[train | val], y_all[train | val], objective, rounds)
    Xt, yt = X_all[test], y_all[test]
    pred = np.clip(booster.predict(Xt), 0, None)

    # Compare on the same hours: those where every method has an answer.
    fair = np.isfinite(Xt["lag_1w"].to_numpy()) & np.isfinite(Xt["typical_8w"].to_numpy())
    preds = {
        "Seasonal naive (same hour last week)": Xt["lag_1w"].to_numpy(),
        "Typical (8-week median, the app's baseline)": Xt["typical_8w"].to_numpy(),
        "LightGBM": pred,
    }
    y = yt[fair]
    test_hours = pd.Series(Xt["hour"].to_numpy()[fair])
    results = {
        name: {
            "mae": mae(y, p[fair]),
            "mape": mape(y, p[fair]),
            "by_hour": {
                int(h): {"mae": mae(y[m], p[fair][m]), "mape": mape(y[m], p[fair][m])}
                for h in range(24)
                for m in [(test_hours == h).to_numpy()]
            },
        }
        for name, p in preds.items()
    }
    test_frame = hist[test].reset_index(drop=True)[fair].reset_index(drop=True)
    test_frame["lightgbm"] = pred[fair]
    test_frame["typical"] = Xt["typical_8w"].to_numpy()[fair]
    return {
        "columns": columns,
        "objective": objective,
        "rounds": rounds,
        "trials": trials,
        "results": results,
        "split": {
            "train": [str(d[train].min().date()), str(d[train].max().date())],
            "validation": [str(val_start.date()), str((test_start - pd.Timedelta(days=1)).date())],
            "test": [str(test_start.date()), str(last.date())],
            "train_rows": int(train.sum()),
            "test_rows_scored": int(fair.sum()),
            "test_rows_total": int(test.sum()),
            "sensors": int(hist["location_id"].nunique()),
        },
        "importance": dict(zip(columns, booster.feature_importance("gain").tolist())),
        "test_frame": test_frame,
        "X_all": X_all,
        "y_all": y_all,
        "usable": usable,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--no-cache", action="store_true", help="re-download every month")
    args = parser.parse_args()

    today = date.today()
    print("loading history")
    raw = data.download(today - timedelta(days=2 * 365), today, cache=not args.no_cache)
    hist = data.clean(raw)
    print(f"  {len(raw):,} raw rows -> {len(hist):,} clean hourly rows, {hist['location_id'].nunique()} sensors")

    attempts = []
    for label, columns in [("base", features.BASE), ("base + extra", features.BASE + features.EXTRA)]:
        print(f"training with {label} features")
        outcome = run(hist, columns)
        outcome["label"] = label
        attempts.append(outcome)
        lgbm = outcome["results"]["LightGBM"]["mae"]
        typical = outcome["results"]["Typical (8-week median, the app's baseline)"]["mae"]
        print(f"  test MAE: LightGBM {lgbm:.2f} vs typical {typical:.2f}")

    best = min(attempts, key=lambda a: a["results"]["LightGBM"]["mae"])

    # Ship: refit the best setup on all usable history.
    X, y, usable = best["X_all"], best["y_all"], best["usable"]
    booster = fit(X[usable], y[usable], best["objective"], best["rounds"])
    # LightGBM's text format compresses ~3x; gzip keeps the file small enough to commit.
    model_path = HERE / "model.txt.gz"
    with gzip.open(model_path, "wt", compresslevel=9) as f:
        f.write(booster.model_to_string())
    meta = {
        "trained_at": datetime.now().isoformat(timespec="seconds"),
        "columns": best["columns"],
        "objective": best["objective"],
        "rounds": best["rounds"],
        "history_to": str(hist["date"].max().date()),
        "size_bytes": model_path.stat().st_size,
    }
    (HERE / "model_meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(f"saved {model_path.name}: {meta['size_bytes'] / 1e6:.2f} MB")

    report.write(attempts, best, meta, HERE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
