from datetime import datetime, timedelta, timezone

import pytest
import requests

import weather_forecast
from pulse import openmeteo
from pulse.timeutil import local

START = datetime(2026, 10, 3, 3, tzinfo=timezone.utc)  # Sat 13:00 AEST, the day before clocks go forward


def hourly(n: int, start: datetime = START) -> dict:
    """An Open-Meteo `hourly` block: each value encodes its own position."""
    return {
        "time": [int((start + timedelta(hours=i)).timestamp()) for i in range(n)],
        "precipitation": [i / 10 for i in range(n)],
        "precipitation_probability": [i for i in range(n)],
        "temperature_2m": [10 + i for i in range(n)],
        "wind_speed_10m": [20 + i for i in range(n)],
        "weather_code": [61] * n,
    }


class Response:
    def __init__(self, body):
        self.body = body

    def raise_for_status(self):
        pass

    def json(self):
        return self.body


@pytest.fixture
def unreachable(monkeypatch):
    def refuse(*_, **__):
        raise requests.ConnectionError("open-meteo is down")

    monkeypatch.setattr(openmeteo.requests, "get", refuse)
    monkeypatch.setattr(openmeteo.time, "sleep", lambda _: None)


def test_rain_is_moved_to_the_hour_it_fell_in():
    """Open-Meteo stamps rain at the END of its hour; temperature is a reading AT the stamp."""
    rows = openmeteo.hourly_rows(hourly(4), openmeteo.FORECAST_VARIABLES)
    assert [r["hour"] for r in rows] == [START + timedelta(hours=i) for i in range(4)]
    assert [r["precipitation"] for r in rows] == [0.1, 0.2, 0.3, None]  # stamped one hour later
    assert [r["precipitation_probability"] for r in rows] == [1, 2, 3, None]
    assert [r["temperature"] for r in rows] == [10, 11, 12, 13]
    assert [r["wind_speed"] for r in rows] == [20, 21, 22, 23]


def test_forecast_is_48_real_hours_across_the_dst_change(monkeypatch):
    calls = []

    def get(url, params, **_):
        calls.append((url, params))
        return Response({"hourly": hourly(params["forecast_hours"])})

    monkeypatch.setattr(openmeteo.requests, "get", get)
    rows = openmeteo.forecast()

    url, params = calls[0]
    assert url == "https://api.open-meteo.com/v1/forecast"
    assert params["timeformat"] == "unixtime" and params["forecast_hours"] == 49
    assert len(rows) == 48 and all(r["precipitation"] is not None for r in rows)
    assert all(b["hour"] - a["hour"] == timedelta(hours=1) for a, b in zip(rows, rows[1:]))
    local_hours = [(local(r["hour"]).day, local(r["hour"]).hour) for r in rows]
    assert (4, 2) not in local_hours and (4, 1) in local_hours and (4, 3) in local_hours  # 02:00 doesn't exist


class FakeConn:
    """Records statements; stands in for psycopg in save()."""

    def __init__(self):
        self.statements = []

    def transaction(self):
        return self

    def cursor(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, sql, params=None):
        self.statements.append((" ".join(sql.split()), params))

    def executemany(self, sql, rows):
        self.statements.append((" ".join(sql.split()), list(rows)))


def test_save_replaces_future_hours_and_keeps_two_days():
    conn = FakeConn()
    rows = openmeteo.hourly_rows(hourly(49), openmeteo.FORECAST_VARIABLES)[:48]
    weather_forecast.save(conn, rows)
    (delete, since), (insert, written), (trim, keep) = conn.statements
    assert delete == "delete from weather_forecast where hour >= %s" and since == (START,)
    assert insert.startswith("insert into weather_forecast") and len(written) == 48
    assert trim.startswith("delete from weather_forecast where hour < now()") and keep == (2,)


def test_open_meteo_failure_keeps_the_old_rows(unreachable, capsys):
    def connect():
        raise AssertionError("the database must not be touched when Open-Meteo fails")

    assert weather_forecast.refresh(connect) is False
    assert "keeping the last good rows" in capsys.readouterr().err


def test_an_empty_or_null_forecast_is_treated_as_a_failure(capsys):
    def connect():
        raise AssertionError("the database must not be touched")

    assert weather_forecast.refresh(connect, source=lambda: []) is False
    blank = [{"hour": START, "precipitation": None, "precipitation_probability": None,
              "temperature": None, "wind_speed": None, "weather_code": None}]
    assert weather_forecast.refresh(connect, source=lambda: blank) is False


def test_the_hourly_step_exits_0_when_open_meteo_is_down(unreachable, monkeypatch):
    monkeypatch.setattr("sys.argv", ["weather_forecast.py"])
    monkeypatch.setattr("pulse.db.connect", lambda: (_ for _ in ()).throw(AssertionError("no database")))
    assert weather_forecast.main() == 0


def test_observed_weather_never_asks_for_a_future_date(monkeypatch):
    calls = []

    def get(url, params, **_):
        calls.append((url, params))
        return Response({"hourly": {"time": [], "precipitation": [], "temperature_2m": []}})

    monkeypatch.setattr(openmeteo.requests, "get", get)
    today = datetime.now(timezone.utc).date()
    openmeteo.observed(today - timedelta(days=3), today + timedelta(days=1))
    url, params = calls[0]
    assert url == "https://archive-api.open-meteo.com/v1/archive"
    assert params["end_date"] == str(today) and params["hourly"] == "precipitation,temperature_2m"
