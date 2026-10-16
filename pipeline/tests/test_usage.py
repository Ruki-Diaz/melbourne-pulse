"""The daily Neon budget check: green, yellow warning, or red, from the project's usage so far."""

import pytest

import usage
from conftest import utc

START = "2026-11-01T00:00:00Z"


def project(gb: float, cu_hours: float = 10, start: str = START, end: str | None = None) -> dict:
    p = {"consumption_period_start": start, "data_transfer_bytes": int(gb * 1e9), "compute_time_seconds": cu_hours * 3600}
    if end:
        p["consumption_period_end"] = end
    return p


def annotations(capsys):
    return [line for line in capsys.readouterr().out.splitlines() if line.startswith("::")]


def test_a_month_on_budget_is_green(capsys):
    # Half way through November with 1 GB used: on track for 2 GB, 40% of the allowance.
    rows = usage.assess(project(1.0), utc(2026, 11, 16))
    assert usage.exit_code(rows) == 0 and annotations(capsys) == []
    transfer = rows[0]
    assert transfer["projected_share"] == pytest.approx(0.4) and transfer["used_share"] == pytest.approx(0.2)


def test_on_track_for_more_than_half_is_a_warning(capsys):
    assert usage.exit_code(usage.assess(project(1.5), utc(2026, 11, 16))) == 0  # on track for 3 GB, 60%
    (warning,) = annotations(capsys)
    assert warning.startswith("::warning title=Neon data transfer budget::") and "on track for 60%" in warning


def test_on_track_to_run_out_is_red_days_before_neon_suspends(capsys):
    # This October's real pattern: 4 GB by the 16th is on track for ~8 GB.
    assert usage.exit_code(usage.assess(project(4.0, start="2026-10-01T00:00:00Z"), utc(2026, 10, 16))) == 1
    assert annotations(capsys)[0].startswith("::error title=Neon data transfer budget::")


def test_compute_is_checked_too(capsys):
    assert usage.exit_code(usage.assess(project(0.5, cu_hours=60), utc(2026, 11, 16))) == 1  # on track for 120 CU-hours
    assert annotations(capsys)[0].startswith("::error title=Neon compute budget::")


def test_early_in_the_month_a_small_amount_isnt_projected_wildly():
    # 10 minutes in, the elapsed time is counted as at least an hour.
    rows = usage.assess(project(0.001), utc(2026, 11, 1, 0, 10))
    assert rows[0]["projected_share"] < 0.2


def test_the_period_end_comes_from_neon_when_given():
    start, end = usage.period(project(1, start="2026-11-15T00:00:00Z", end="2026-12-15T00:00:00Z"))
    assert (end - start).days == 30
    _, end = usage.period(project(1, start="2027-01-31T00:00:00Z"))  # no end given: a month on, clamped
    assert end == utc(2027, 2, 28)


def test_a_changed_api_response_says_so():
    with pytest.raises(KeyError, match="data_transfer_bytes"):
        usage.assess({"consumption_period_start": START, "compute_time_seconds": 0}, utc(2026, 11, 2))


def test_without_a_key_it_warns_and_never_blocks_the_forecast(monkeypatch, capsys):
    monkeypatch.delenv("NEON_API_KEY", raising=False)
    assert usage.main() == 0
    assert annotations(capsys)[0].startswith("::warning title=Neon usage not checked::")
