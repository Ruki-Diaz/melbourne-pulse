"""One feed failing is a warning; every feed, a repeat offender or the database failing is red."""

from datetime import datetime, timezone
from functools import partial

import pytest
import requests

import fetch
import weather_forecast
from conftest import utc
from pulse import api, feedstatus

NOW = utc(2026, 9, 29, 17, 30)  # just after the fixture's pedestrian minutes
DATASETS = {api.PEDESTRIAN_MINUTES: "pedestrian", api.PARKING: "parking", api.SENSOR_LOCATIONS: "sensors"}


class Result:
    rowcount = 0

    def __init__(self, row=None):
        self.row = row

    def fetchone(self):
        return self.row

    def fetchall(self):
        return []


class FakeDb:
    """Stands in for Postgres across runs: keeps feed_status in memory, records every other statement."""

    def __init__(self, break_on=None):
        self.status = {}  # feed -> [consecutive_failures, last_success_at]
        self.statements = []
        self.break_on = break_on

    def __call__(self):  # db.connect()
        return self

    def transaction(self):
        return self

    def cursor(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, sql, params=None):
        sql = " ".join(sql.split())
        if self.break_on and self.break_on in sql:
            raise RuntimeError("database write failed")
        if sql.startswith("insert into feed_status (feed, last_success_at"):
            self.status[params[0]] = [0, datetime.now(timezone.utc)]
        elif sql.startswith("insert into feed_status (feed, last_failure_at"):
            row = self.status.setdefault(params[0], [0, None])
            row[0] += 1
            return Result(tuple(row))
        elif "feed_status" not in sql:
            self.statements.append(sql)
        return Result()

    def executemany(self, sql, rows):
        self.execute(sql)

    def wrote(self, table):
        return any(s.startswith(f"insert into {table}") for s in self.statements)


@pytest.fixture
def city(monkeypatch, minute_rows, parking_rows, location_rows):
    """The city's API, with a set of feeds that are down. Returns that set."""
    down = set()
    rows = {"pedestrian": minute_rows, "parking": parking_rows, "sensors": location_rows}

    def export(dataset_id, **_):
        feed = DATASETS[dataset_id]
        if feed in down:
            raise requests.ConnectionError(f"{feed} timed out")
        return rows[feed]

    monkeypatch.setattr(api, "export", export)
    monkeypatch.setattr(fetch, "collect", partial(fetch.collect, now=NOW))
    monkeypatch.setattr("sys.argv", ["fetch.py"])
    return down


@pytest.fixture
def database(monkeypatch):
    db = FakeDb()
    monkeypatch.setattr("pulse.db.connect", db)
    return db


def annotations(capsys):
    return [line for line in capsys.readouterr().out.splitlines() if line.startswith("::")]


def test_every_feed_working_is_green_with_no_annotation(city, database, capsys):
    assert fetch.main() == 0
    assert annotations(capsys) == []
    assert database.wrote("pedestrian_hourly") and database.wrote("parking_hourly")
    assert {feed: runs for feed, (runs, _) in database.status.items()} == {"pedestrian": 0, "parking": 0, "sensors": 0}


@pytest.mark.parametrize("feed", fetch.FEEDS)
def test_one_feed_failing_is_a_warning_and_the_others_are_saved(city, database, capsys, feed):
    city.add(feed)
    assert fetch.main() == 0
    (warning,) = annotations(capsys)
    assert warning.startswith(f"::warning title=Feed failed: {feed}::") and "timed out" in warning
    assert database.wrote("pedestrian_hourly") == (feed != "pedestrian")
    assert database.wrote("parking_hourly") == (feed != "parking")
    assert database.status[feed][0] == 1


def test_a_feed_with_no_rows_is_a_warning(city, database, capsys, monkeypatch):
    working = api.export
    monkeypatch.setattr(api, "export", lambda dataset_id, **_: [] if dataset_id == api.PARKING else working(dataset_id))
    assert fetch.main() == 0
    (warning,) = annotations(capsys)
    assert warning.startswith("::warning title=Feed failed: parking::") and "no usable rows" in warning


def test_all_feeds_failing_is_red(city, database, capsys):
    city.update(fetch.FEEDS)
    assert fetch.main() == 1
    lines = annotations(capsys)
    assert sum(line.startswith("::warning") for line in lines) == 3
    assert lines[-1].startswith("::error title=All feeds failed::")


def test_the_third_failure_in_a_row_is_red_and_a_success_resets_the_count(city, database, capsys):
    city.add("parking")
    assert [fetch.main(), fetch.main()] == [0, 0]
    assert all(line.startswith("::warning") for line in annotations(capsys))

    assert fetch.main() == 1
    (error,) = annotations(capsys)
    assert error.startswith("::error title=Feed stale: parking::") and "3 runs in a row" in error
    assert database.wrote("pedestrian_hourly")  # the working feeds were still saved

    city.clear()
    assert fetch.main() == 0 and database.status["parking"][0] == 0
    city.add("parking")
    capsys.readouterr()
    assert fetch.main() == 0  # counting starts again
    assert "(1 in a row)" in annotations(capsys)[0]


def test_two_different_feeds_failing_in_turn_never_add_up(city, database):
    for feed in ("parking", "sensors", "parking", "sensors"):
        city.clear()
        city.add(feed)
        assert fetch.main() == 0


def test_a_database_write_failing_is_red(city, monkeypatch):
    monkeypatch.setattr("pulse.db.connect", FakeDb(break_on="insert into parking_hourly"))
    with pytest.raises(RuntimeError, match="database write failed"):
        fetch.main()  # an uncaught exception: Python exits 1


def test_a_dry_run_warns_without_a_database(city, capsys, monkeypatch):
    monkeypatch.setattr("sys.argv", ["fetch.py", "--dry-run"])
    monkeypatch.setattr("pulse.db.connect", lambda: pytest.fail("a dry run must not open the database"))
    city.add("sensors")
    assert fetch.main() == 0
    assert annotations(capsys)[0].startswith("::warning title=Feed failed: sensors::")
    city.update(fetch.FEEDS)
    assert fetch.main() == 1


def test_the_stale_error_says_when_the_feed_last_worked(capsys):
    last_ok = utc(2026, 10, 2, 14, 7)
    code = feedstatus.exit_code({"parking": "HTTPError: 503"}, {"parking": (3, last_ok)}, all_failed=False)
    assert code == 1
    assert "last success Sat 03 Oct 00:07 AEST" in capsys.readouterr().out


def test_an_annotation_stays_on_one_line(capsys):
    feedstatus.annotate("warning", "Feed failed: parking", "line one\nline two 100%")
    assert capsys.readouterr().out == "::warning title=Feed failed: parking::line one%0Aline two 100%25\n"


def down():
    raise requests.ConnectionError("open-meteo is down")


def test_open_meteo_down_is_a_warning_until_the_third_run(database, capsys):
    refresh = partial(weather_forecast.refresh, database, source=down)
    assert [refresh(), refresh()] == [0, 0]
    assert all(line.startswith("::warning title=Feed failed: weather::") for line in annotations(capsys))
    assert refresh() == 1
    assert annotations(capsys)[0].startswith("::error title=Feed stale: weather::")
    assert not database.wrote("weather_forecast")  # the last good rows are kept throughout
