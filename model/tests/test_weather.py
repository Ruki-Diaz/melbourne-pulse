from datetime import date, datetime, timedelta, timezone

import lightgbm as lgb
import numpy as np
import pandas as pd
import pytest
import requests

import features
import predict
import weather
from test_features import synthetic_history

PLUS_10 = timezone(timedelta(hours=10))


class FakeOpenMeteo:
    """Stands in for requests.get: answers like Open-Meteo and records every call.

    Like the real service it uses one fixed offset (+10) for day boundaries,
    and each value encodes its own UTC hour so a wrong join is visible:
    precipitation = hours since 2020-01-01 UTC.
    """

    def __init__(self, now=datetime(2026, 10, 3, 3, 37, tzinfo=timezone.utc), drop_last=0):
        self.calls, self.now, self.drop_last = [], now, drop_last

    def __call__(self, url, params, **_):
        self.calls.append((url, params))
        if "start_date" in params:
            start = datetime.fromisoformat(params["start_date"]).replace(tzinfo=PLUS_10)
            end = datetime.fromisoformat(params["end_date"]).replace(tzinfo=PLUS_10) + timedelta(days=1)
        else:
            this_hour = self.now.replace(minute=0, second=0, microsecond=0)
            start = this_hour - timedelta(hours=params["past_hours"])
            end = this_hour + timedelta(hours=params["forecast_hours"] - self.drop_last)
        times = [int(start.timestamp()) + 3600 * i for i in range(int((end - start).total_seconds() // 3600))]
        hourly = {"time": times}
        for name in params["hourly"].split(","):
            hourly[name] = [float(code(t)) for t in times]
        response = requests.Response()
        response.status_code = 200
        response.json = lambda: {"hourly": hourly}
        return response


def code(unix_seconds) -> int:
    return (int(unix_seconds) - 1577836800) // 3600


def code_of(ts: pd.Series) -> np.ndarray:
    return np.array([code(t.timestamp()) for t in ts])


@pytest.fixture
def open_meteo(monkeypatch):
    fake = FakeOpenMeteo()
    monkeypatch.setattr(weather.requests, "get", fake)
    return fake


@pytest.fixture
def unreachable(monkeypatch):
    def refuse(*_, **__):
        raise requests.ConnectionError("open-meteo is down")

    monkeypatch.setattr(weather.requests, "get", refuse)
    monkeypatch.setattr(weather.time, "sleep", lambda _: None)


@pytest.mark.parametrize(
    "first, last, change_day",
    [
        (date(2026, 9, 28), date(2026, 10, 8), date(2026, 10, 4)),  # clocks go forward: 23-hour day
        (date(2026, 3, 30), date(2026, 4, 9), date(2026, 4, 5)),  # clocks go back: 25-hour day
    ],
)
def test_weather_joins_to_the_same_real_hour_across_a_dst_change(open_meteo, first, last, change_day):
    """Every pedestrian row must get the forecast for its own UTC hour, on both sides of the change."""
    hist = synthetic_history(first=first, last=last, sensors=(1,))
    w = weather.history(first, last)
    X = features.build(hist, hist, features.WEATHER, w)

    assert not X.isna().any().any()
    np.testing.assert_array_equal(X["precipitation"], code_of(hist["ts"]))
    # precip_3h covers this hour and the two real hours before it, whatever the clocks say.
    np.testing.assert_array_equal(X["precip_3h"], 3 * code_of(hist["ts"]) - 3)

    # The same hours exist on the change day as in the pedestrian data: no 02:00.
    hours = w.loc[w["date"] == pd.Timestamp(change_day), "hour"].tolist()
    assert hours == hist.loc[hist["date"] == pd.Timestamp(change_day), "hour"].tolist()
    assert len(hours) == 23 and 2 not in hours
    # A month boundary inside the range fetches each month separately, with no duplicate hours.
    assert len(open_meteo.calls) == 2 and not w.duplicated(["date", "hour"]).any()


def test_wet_flag_and_missing_weather():
    w = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-10-15"] * 3),
            "hour": [9, 10, 11],
            "precipitation": [0.1, 0.2, 2.5],
            "precip_3h": [0.1, 0.3, 2.8],
            "temperature": [14.0, 13.5, 12.0],
            "wind": [10.0, 12.0, 20.0],
        }
    )
    targets = pd.DataFrame({"location_id": [1] * 4, "date": pd.to_datetime(["2026-10-15"] * 4), "hour": [9, 10, 11, 12]})
    X = features.build(targets, synthetic_history(), features.WEATHER, w)
    assert X["wet"].tolist()[:3] == [0.0, 1.0, 1.0]
    assert X.iloc[3].isna().all()  # an hour with no forecast is missing, never "dry"
    with pytest.raises(ValueError):
        features.build(targets, synthetic_history(), features.WEATHER)


def test_no_weather_feature_uses_anything_later_than_the_hour_it_describes(open_meteo):
    """Deleting or changing every forecast value after a target hour must not change its features."""
    hist = synthetic_history(first=date(2026, 9, 1), last=date(2026, 10, 8), sensors=(1,))
    w = weather.history(date(2026, 9, 28), date(2026, 10, 8))
    for day, hour in [("2026-10-03", 23), ("2026-10-04", 3), ("2026-10-06", 12)]:
        target = hist[(hist["date"] == day) & (hist["hour"] == hour)].reset_index(drop=True)
        cutoff = target["ts"].iloc[0]
        full = features.build(target, hist, features.WEATHER, w)

        truncated = features.build(target, hist, features.WEATHER, w[w["ts"] <= cutoff])
        pd.testing.assert_frame_equal(full, truncated)

        scrambled = w.copy()
        later = scrambled["ts"] > cutoff
        scrambled.loc[later, ["precipitation", "precip_3h", "temperature", "wind"]] = 999.0
        pd.testing.assert_frame_equal(full, features.build(target, hist, features.WEATHER, scrambled))


def test_only_forecast_endpoints_are_used_never_observed_weather(open_meteo):
    """Training reads forecasts as issued; prediction reads the live forecast. No archive/observed API."""
    weather.history(date(2026, 9, 28), date(2026, 9, 30), "latest")
    weather.history(date(2026, 9, 28), date(2026, 9, 30), "day1")
    weather.forecast()
    (latest_url, _), (day1_url, day1), (live_url, live) = open_meteo.calls

    assert latest_url == "https://historical-forecast-api.open-meteo.com/v1/forecast"
    assert day1_url == "https://previous-runs-api.open-meteo.com/v1/forecast"
    # day1 = every variable as it was predicted 24 h before the hour, older than predict.py's forecast
    assert all(name.endswith("_previous_day1") for name in day1["hourly"].split(","))
    assert live_url == "https://api.open-meteo.com/v1/forecast" and live["forecast_hours"] == 48
    assert not any("archive" in url for url, _ in open_meteo.calls)


def test_live_forecast_covers_every_predicted_hour(open_meteo):
    hist = synthetic_history(last=date(2026, 10, 3))
    forecasts = predict.weather_for(hist, open_meteo.now)  # raises if any of the 36 hours is uncovered
    targets = predict.targets_for(hist, open_meteo.now)
    X = features.build(targets, hist, features.WEATHER, forecasts)
    np.testing.assert_array_equal(X["precipitation"], code_of(targets["ts"]))  # across the 4 Oct change


def tiny_model(history: pd.DataFrame, columns: list[str], path) -> None:
    X = features.build(history, history, columns)
    booster = lgb.train(
        {"objective": "l1", "verbose": -1, "num_threads": 1},
        lgb.Dataset(X, history["count"].to_numpy(dtype=float), categorical_feature=["sensor"]),
        num_boost_round=5,
    )
    booster.save_model(str(path))


WEATHER_META = {
    "columns": features.BASE + features.WEATHER,
    "fallback": {"file": "model_base.txt.gz", "columns": features.BASE},
}
NOW = datetime(2026, 10, 3, 3, 37, tzinfo=timezone.utc)


def test_falls_back_to_the_base_model_when_open_meteo_is_unreachable(unreachable, capsys, tmp_path):
    hist = synthetic_history(last=date(2026, 10, 3))

    model_file, columns, forecasts = predict.choose_model(WEATHER_META, hist, NOW)

    assert (model_file, columns, forecasts) == ("model_base.txt.gz", features.BASE, None)
    assert "weather forecast unavailable" in capsys.readouterr().out  # logged, not raised
    # ...and the run still produces a full set of forecasts with that model.
    tiny_model(hist, features.BASE, tmp_path / "base.txt")
    rows = predict.forecast(hist, NOW, lgb.Booster(model_file=str(tmp_path / "base.txt")), columns, forecasts)
    assert len(rows) == 2 * predict.HORIZON_HOURS and rows["predicted_count"].notna().all()


def test_falls_back_when_the_forecast_does_not_cover_every_hour(monkeypatch, capsys):
    monkeypatch.setattr(weather.requests, "get", FakeOpenMeteo(now=NOW, drop_last=20))
    hist = synthetic_history(last=date(2026, 10, 3))
    assert predict.choose_model(WEATHER_META, hist, NOW)[0] == "model_base.txt.gz"
    assert "missing" in capsys.readouterr().out


def test_uses_the_weather_model_when_open_meteo_answers(open_meteo):
    hist = synthetic_history(last=date(2026, 10, 3))
    model_file, columns, forecasts = predict.choose_model(WEATHER_META, hist, NOW)
    assert model_file == "model.txt.gz" and columns == WEATHER_META["columns"] and forecasts is not None


def test_a_model_without_weather_never_calls_open_meteo(unreachable, capsys):
    hist = synthetic_history(last=date(2026, 10, 3))
    meta = {"columns": features.BASE + features.EXTRA}
    assert predict.choose_model(meta, hist, NOW) == ("model.txt.gz", meta["columns"], None)
    assert capsys.readouterr().out == ""


def test_placebo_attaches_every_forecast_to_the_wrong_fortnight(open_meteo):
    import train

    w = weather.history(date(2026, 9, 28), date(2026, 10, 8))
    shifted = train.placebo_weather(w)
    assert (shifted["date"] - w["date"]).eq(pd.Timedelta(days=14)).all()
    pd.testing.assert_frame_equal(shifted.drop(columns="date"), w.drop(columns="date"))
