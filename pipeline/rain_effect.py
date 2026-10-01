"""Measure how much rain changes pedestrian counts, over the last 12 months.

Runs monthly. This is for *explaining* the forecast on the Plan page ("rain
usually means about X% less foot traffic here"). It is never applied to the
forecast: the model already has the weather forecast as an input.

Method (matched wet vs dry):
  - Counts: the city's hourly dataset. Weather: Open-Meteo's observed history
    (the archive API), because this measures what rain actually did.
  - An hour is wet from 0.2 mm of rain and heavy from 2 mm.
  - Every sensor-hour belongs to a cell: sensor x local hour x day type
    (weekday, or weekend + public holiday) x month. A wet hour's expected count
    is the mean of the DRY hours in its own cell, so a wet Tuesday 9am in July
    is only ever compared with dry weekday 9ams in July at the same sensor.
    Cells with fewer than 3 dry hours are left out.
  - effect = sum(actual in wet hours) / sum(expected) - 1.
  - 95% interval: bootstrap over whole days (400 resamples, fixed seed), with
    the dry-hour means recomputed in every resample.
  - reliable = at least 100 wet hours AND the interval excludes zero.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from functools import lru_cache
from typing import Callable, Iterable

import holidays
import numpy as np

from pulse import api, openmeteo
from pulse.history import complete_days
from pulse.timeutil import UTC, local

WET_MM = 0.2
HEAVY_MM = 2.0
MIN_DRY_HOURS = 3  # dry hours a cell needs before its mean is trusted
COLD_BELOW_C = 12.0
WARM_ABOVE_C = 20.0
REPS = 400
SEED = 20261002
MIN_WET_HOURS = 100
CI = (2.5, 97.5)

Row = tuple[int, date, int, datetime, int]  # location_id, local date, local hour, UTC hour start, count


def window_for(last_day: date) -> tuple[date, date]:
    """The 12 months ending on `last_day`, both ends included."""
    try:
        year_before = last_day.replace(year=last_day.year - 1)
    except ValueError:  # 29 Feb
        year_before = last_day.replace(year=last_day.year - 1, day=28)
    return year_before + timedelta(days=1), last_day


@lru_cache(maxsize=None)
def _public_holidays(year: int) -> frozenset[date]:
    return frozenset(holidays.country_holidays("AU", subdiv="VIC", years=year, categories=("public",)))


def is_day_off(day: date) -> bool:
    """Weekend or Victorian public holiday: the 'weekend' day type."""
    return day.weekday() >= 5 or day in _public_holidays(day.year)


def reliable(n_wet_hours: int, ci_low: float | None, ci_high: float | None) -> bool:
    """The trust rule: enough wet hours, and an interval that excludes zero."""
    if ci_low is None or ci_high is None or n_wet_hours < MIN_WET_HOURS:
        return False
    return ci_low > 0 or ci_high < 0


@dataclass
class Table:
    """One entry per sensor-hour inside the window that has observed weather."""

    sensors: list[int]
    days: list[date]
    sensor: np.ndarray  # index into sensors
    day: np.ndarray  # index into days
    hour: np.ndarray  # local hour 0-23
    stamp: np.ndarray  # index of the real (UTC) hour, shared by every sensor
    count: np.ndarray
    precip: np.ndarray
    temp: np.ndarray  # NaN if unknown
    day_off: np.ndarray
    cell: np.ndarray  # sensor x hour x day type x month

    @property
    def wet(self) -> np.ndarray:
        return self.precip >= WET_MM


def build_table(
    rows: Iterable[Row],
    weather: Iterable[dict],
    start: date,
    end: date,
    day_off: Callable[[date], bool] = is_day_off,
) -> Table:
    """Join counts to weather on the UTC hour (DST-safe) and keep [start, end] only."""
    by_hour = {w["hour"]: w for w in weather if w["precipitation"] is not None}
    kept = [(r, by_hour[r[3]]) for r in rows if start <= r[1] <= end and r[3] in by_hour]
    sensors = sorted({r[0] for r, _ in kept})
    days = sorted({r[1] for r, _ in kept})
    stamps = sorted({r[3] for r, _ in kept})
    sensor_at = {s: i for i, s in enumerate(sensors)}
    day_at = {d: i for i, d in enumerate(days)}
    stamp_at = {s: i for i, s in enumerate(stamps)}
    off = {d: day_off(d) for d in days}

    sensor = np.array([sensor_at[r[0]] for r, _ in kept], dtype=np.int64)
    hour = np.array([r[2] for r, _ in kept], dtype=np.int64)
    is_off = np.array([off[r[1]] for r, _ in kept], dtype=bool)
    month = np.array([r[1].month for r, _ in kept], dtype=np.int64)
    return Table(
        sensors=sensors,
        days=days,
        sensor=sensor,
        day=np.array([day_at[r[1]] for r, _ in kept], dtype=np.int64),
        hour=hour,
        stamp=np.array([stamp_at[r[3]] for r, _ in kept], dtype=np.int64),
        count=np.array([r[4] for r, _ in kept], dtype=float),
        precip=np.array([w["precipitation"] for _, w in kept], dtype=float),
        temp=np.array([np.nan if w["temperature"] is None else w["temperature"] for _, w in kept], dtype=float),
        day_off=is_off,
        cell=((sensor * 24 + hour) * 2 + is_off) * 12 + (month - 1),
    )


def groupings(t: Table) -> dict[str, tuple[np.ndarray, list[str]]]:
    """For each breakdown: a group number per WET row (-1 = in no group) and the group names."""
    wet = t.wet
    precip, temp = t.precip[wet], t.temp[wet]
    band = np.where(np.isnan(temp), -1, np.where(temp < COLD_BELOW_C, 0, np.where(temp > WARM_ABOVE_C, 2, 1)))
    return {
        "overall": (np.zeros(int(wet.sum()), dtype=np.int64), ["all"]),
        "intensity": ((precip >= HEAVY_MM).astype(np.int64), ["light", "heavy"]),
        "daytype": (t.day_off[wet].astype(np.int64), ["weekday", "weekend"]),
        "temperature": (band.astype(np.int64), ["cold", "mild", "warm"]),
        "sensor": (t.sensor[wet], [str(s) for s in t.sensors]),
        "hour": (t.hour[wet], [str(h) for h in range(24)]),
    }


def matched(t: Table, day_weights: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Per wet row: weighted actual, weighted expected, and whether its cell had enough dry hours.

    `day_weights` is how many times each day appears in a bootstrap resample
    (all ones for the real data). Rows in cells that fail the test carry zeros.
    """
    weight = np.ones(len(t.count)) if day_weights is None else day_weights[t.day]
    wet = t.wet
    dry = ~wet
    cells = int(t.cell.max()) + 1 if len(t.cell) else 0
    dry_hours = np.bincount(t.cell[dry], weights=weight[dry], minlength=cells)
    dry_total = np.bincount(t.cell[dry], weights=weight[dry] * t.count[dry], minlength=cells)
    enough = dry_hours >= MIN_DRY_HOURS
    mean = np.divide(dry_total, dry_hours, out=np.zeros(cells), where=enough)

    used = enough[t.cell[wet]]
    actual = np.where(used, weight[wet] * t.count[wet], 0.0)
    expected = weight[wet] * mean[t.cell[wet]]
    return actual, expected, used


def _by_group(values: np.ndarray, group: np.ndarray, n: int) -> np.ndarray:
    inside = group >= 0
    return np.bincount(group[inside], weights=values[inside], minlength=n)


def _effects(actual: np.ndarray, expected: np.ndarray, group: np.ndarray, n: int) -> np.ndarray:
    a, e = _by_group(actual, group, n), _by_group(expected, group, n)
    return np.divide(a, e, out=np.full(n, np.nan), where=e > 0) - 1


def compute(t: Table, reps: int = REPS, seed: int = SEED) -> list[dict]:
    """Every stored row: overall, each breakdown, each sensor, and the hourly profile."""
    groups = groupings(t)
    actual, expected, used = matched(t)
    point = {name: _effects(actual, expected, ids, len(names)) for name, (ids, names) in groups.items()}

    # Wet hours behind each estimate: distinct real hours, not sensor-hours.
    wet_stamp = t.stamp[t.wet]
    wet_hours = {}
    for name, (ids, names) in groups.items():
        keep = used & (ids >= 0)
        pairs = np.unique(np.stack([ids[keep], wet_stamp[keep]]), axis=1)
        wet_hours[name] = np.bincount(pairs[0], minlength=len(names))

    rng = np.random.default_rng(seed)
    n_days = len(t.days)
    draws = {name: np.full((reps, len(names)), np.nan) for name, (_, names) in groups.items() if name != "hour"}
    for rep in range(reps):
        weights = np.bincount(rng.integers(0, n_days, n_days), minlength=n_days).astype(float)
        a, e, _ = matched(t, weights)
        for name in draws:
            ids, names = groups[name]
            draws[name][rep] = _effects(a, e, ids, len(names))

    out = []
    for name, sample in draws.items():
        names = groups[name][1]
        for i, key in enumerate(names):
            value = point[name][i]
            if np.isnan(value):
                continue  # no wet hour with a usable cell
            valid = sample[:, i][~np.isnan(sample[:, i])]
            # An interval needs most resamples to have produced an estimate.
            low, high = (
                (float(x) for x in np.percentile(valid, CI)) if len(valid) >= reps * 0.9 and reps > 0 else (None, None)
            )
            n = int(wet_hours[name][i])
            out.append(
                {
                    "scope": name,
                    "key": key,
                    "effect": float(value),
                    "ci_low": low,
                    "ci_high": high,
                    "n_wet_hours": n,
                    "reliable": reliable(n, low, high),
                    "detail": None,
                }
            )

    # Average CBD total per wet hour of the day, next to what dry hours matched
    # to the same sensors, day type and month would have given.
    ids, names = groups["hour"]
    a, e = _by_group(actual, ids, 24), _by_group(expected, ids, 24)
    overall = next((r for r in out if r["scope"] == "overall"), None)
    profile = [
        {
            "hour": h,
            "wet": round(float(a[h] / wet_hours["hour"][h]), 1),
            "dry": round(float(e[h] / wet_hours["hour"][h]), 1),
            "n_wet_hours": int(wet_hours["hour"][h]),
        }
        for h in range(24)
        if wet_hours["hour"][h] > 0
    ]
    out.append(
        {
            "scope": "profile",
            "key": "cbd",
            "effect": None,
            "ci_low": None,
            "ci_high": None,
            "n_wet_hours": overall["n_wet_hours"] if overall else 0,
            "reliable": bool(overall and overall["reliable"]),
            "detail": profile,
        }
    )
    return out


def download_counts(first: date, last: date) -> list[Row]:
    """Complete sensor-days for local dates [first, last], a month per request."""
    parsed = []
    start = first.replace(day=1)
    while start <= last:
        end = (start + timedelta(days=32)).replace(day=1)
        print(f"  counts {max(start, first)} .. {min(end - timedelta(days=1), last)}")
        raw = api.export(
            api.PEDESTRIAN_HOURLY,
            select="location_id,sensing_date,hourday,pedestriancount",
            where=f"sensing_date >= date'{max(start, first)}' and sensing_date < date'{min(end, last + timedelta(days=1))}'",
        )
        parsed += [
            (int(r["location_id"]), date.fromisoformat(r["sensing_date"][:10]), int(r["hourday"]), int(r["pedestriancount"]))
            for r in raw
        ]
        start = end
    # The newest day in the dataset is only partly loaded (~1 day lag): skip it.
    newest = max(r[1] for r in parsed)
    return complete_days(r for r in parsed if r[1] < newest)


def last_full_day(rows: list[Row], weather: list[dict]) -> date:
    """Newest local date that has counts and observed rain for the whole day."""
    known = {w["hour"] for w in weather if w["precipitation"] is not None}
    stamps_by_day: dict[date, set[datetime]] = {}
    for _, day, _, stamp, _ in rows:
        stamps_by_day.setdefault(day, set()).add(stamp)
    return max(day for day, stamps in stamps_by_day.items() if stamps <= known)


def load(today: date) -> tuple[Table, date, date]:
    """Download counts and weather and build the table for the newest 12-month window."""
    first = window_for(today)[0] - timedelta(days=10)  # slack for the data lag
    rows = download_counts(first, today)
    print(f"  observed weather {first} .. {today}")
    weather = openmeteo.observed(first, today)
    start, end = window_for(last_full_day(rows, weather))
    return build_table(rows, weather, start, end), start, end


def save(conn, results: list[dict], start: date, end: date, computed_at: datetime) -> None:
    """Replace the whole table in one transaction, so a retired sensor's row can't linger."""
    from psycopg.types.json import Jsonb

    with conn.transaction():
        conn.execute("delete from rain_effect")
        with conn.cursor() as cur:
            cur.executemany(
                """
                insert into rain_effect
                  (scope, key, effect, ci_low, ci_high, n_wet_hours, reliable, detail,
                   window_start, window_end, computed_at)
                values (%(scope)s, %(key)s, %(effect)s, %(ci_low)s, %(ci_high)s, %(n_wet_hours)s,
                        %(reliable)s, %(detail)s, %(start)s, %(end)s, %(at)s)
                """,
                [
                    {**r, "detail": Jsonb(r["detail"]) if r["detail"] is not None else None,
                     "start": start, "end": end, "at": computed_at}
                    for r in results
                ],
            )


def describe(results: list[dict]) -> None:
    def pct(x):
        return "n/a" if x is None else f"{x * 100:+.1f}%"

    for r in results:
        if r["scope"] in ("sensor", "profile"):
            continue
        print(
            f"  {r['scope']:>11} {r['key']:<8} {pct(r['effect']):>7}  "
            f"95% CI {pct(r['ci_low'])} to {pct(r['ci_high'])}  "
            f"{r['n_wet_hours']:>4} wet hours  {'reliable' if r['reliable'] else 'not reliable'}"
        )
    sensors = [r for r in results if r["scope"] == "sensor"]
    print(f"  sensors: {sum(r['reliable'] for r in sensors)} of {len(sensors)} reliable")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="download and compute; no database")
    args = parser.parse_args()

    now = datetime.now(UTC)
    print("loading the last 12 months")
    table, start, end = load(local(now).date())
    print(
        f"  window {start} .. {end}: {len(table.count):,} sensor-hours, {len(table.sensors)} sensors, "
        f"{int(table.wet.sum()):,} wet sensor-hours"
    )
    print(f"computing effects ({REPS} bootstrap resamples over {len(table.days)} days)")
    results = compute(table)
    describe(results)

    if args.dry_run:
        print("dry run: nothing written")
        return 0
    from pulse import db

    with db.connect() as conn:
        save(conn, results, start, end, now)
    print(f"saved {len(results)} rain_effect rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
