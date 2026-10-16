"""Daily check that Neon's free plan will last the month.

Reads this billing period's usage from the Neon API (GET /projects/{id}) and
projects it to the end of the period at the current rate:

  data transfer  5 GB a month. Over it, Neon suspends the database until next month.
  compute        100 CU-hours a month.

    under 50% projected   nothing to do
    50-80% projected      warning annotation, run stays green
    over 80% projected,   error annotation, the run goes red and GitHub emails you,
    or over 80% used      days before Neon would suspend anything

Needs NEON_API_KEY (secret) and NEON_PROJECT_ID (variable). Without them it
only prints a warning: the check is an alarm, it must never block the forecast.

    python usage.py            # prints the numbers; exit 1 only at the red level
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta

import requests

from pulse.feedstatus import annotate
from pulse.timeutil import UTC, parse_ts

API = "https://console.neon.tech/api/v2"
FREE = {
    "data_transfer_bytes": ("data transfer", 5e9, "GB", 1e9),
    "compute_time_seconds": ("compute", 100 * 3600, "CU-hours", 3600),
}
WARN, FAIL = 0.5, 0.8


def period(project: dict) -> tuple[datetime, datetime]:
    """The billing period: start and end from Neon, or one calendar month from the start."""
    start = parse_ts(project["consumption_period_start"])
    end = project.get("consumption_period_end")
    if end and parse_ts(end) > start:
        return start, parse_ts(end)
    year, month = start.year + (start.month == 12), start.month % 12 + 1
    last_day = (datetime(year + (month == 12), month % 12 + 1, 1) - timedelta(days=1)).day
    return start, start.replace(year=year, month=month, day=min(start.day, last_day))


def assess(project: dict, now: datetime) -> list[dict]:
    """For each limit: used so far, projected to the period's end, both as shares of the allowance."""
    start, end = period(project)
    elapsed = max(now - start, timedelta(hours=1)) / (end - start)
    out = []
    for field, (name, allowance, unit, scale) in FREE.items():
        if field not in project:
            raise KeyError(f"Neon's project response has no {field}; the API may have changed")
        used = float(project[field])
        out.append({
            "name": name, "unit": unit, "used": used / scale, "allowance": allowance / scale,
            "used_share": used / allowance, "projected_share": used / allowance / min(elapsed, 1.0),
            "period_end": end,
        })
    return out


def exit_code(rows: list[dict]) -> int:
    code = 0
    for r in rows:
        line = (
            f"{r['name']}: {r['used']:.2f} of {r['allowance']:.0f} {r['unit']} used ({r['used_share']:.0%}), "
            f"on track for {r['projected_share']:.0%} by {r['period_end']:%d %b}"
        )
        print(f"[usage] {line}")
        if r["projected_share"] > FAIL or r["used_share"] > FAIL:
            annotate("error", f"Neon {r['name']} budget", line)
            code = 1
        elif r["projected_share"] > WARN:
            annotate("warning", f"Neon {r['name']} budget", line)
    return code


def fetch(project_id: str, key: str) -> dict:
    resp = requests.get(
        f"{API}/projects/{project_id}", headers={"Authorization": f"Bearer {key}", "Accept": "application/json"}, timeout=30
    )
    resp.raise_for_status()
    return resp.json()["project"]


def main() -> int:
    key, project_id = os.environ.get("NEON_API_KEY"), os.environ.get("NEON_PROJECT_ID")
    if not key or not project_id:
        annotate("warning", "Neon usage not checked", "set the NEON_API_KEY secret and NEON_PROJECT_ID variable (docs/MAINTENANCE.md)")
        return 0
    try:
        project = fetch(project_id, key)
    except Exception as exc:  # noqa: BLE001 - the Neon API being down is not a budget problem
        annotate("warning", "Neon usage not checked", f"{type(exc).__name__}: {exc}")
        return 0
    return exit_code(assess(project, datetime.now(UTC)))


if __name__ == "__main__":
    sys.exit(main())
