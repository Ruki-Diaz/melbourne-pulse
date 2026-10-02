"""Check recent hours for a fault in the city's sensor feed and store the result.

Runs in the hourly job after fetch.py. For each of the last few finished hours
it compares every sensor with its typical count (pulse/quality.py) and writes
one row to feed_quality. The website, the summary sentence and the forecast
model read that table: a flagged hour is shown with a warning instead of "X%
quieter", and is left out of the forecast's history and of future training.

    python feed_quality.py                # the last 3 finished hours (hourly job)
    python feed_quality.py --backfill 14  # re-assess the last 14 days from stored counts
    python feed_quality.py --backfill 14 --dry-run
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from statistics import median

from pulse import db, openmeteo, quality
from pulse.quality import HeavyRain, Quality
from pulse.timeutil import HOUR, UTC, floor_hour, local, parse_ts
from pulse.typical import WEEKS
from rain_effect import HEAVY_MM, _public_holidays

RECENT_HOURS = 3  # late-arriving sensors can still change the hours just finished


def is_public_holiday(day) -> bool:
    return day in _public_holidays(day.year)


def heavy_rain(conn) -> HeavyRain | None:
    """The measured heavy-rain effect, if it has been computed and is reliable."""
    row = conn.execute(
        "select ci_low from rain_effect where scope = 'intensity' and key = 'heavy' and reliable and ci_low is not null"
    ).fetchone()
    return HeavyRain(HEAVY_MM, float(row[0])) if row else None


def typicals(history: dict, flagged: set[datetime], hour: datetime) -> dict[int, float]:
    """Typical count per sensor for `hour`: the median of the same local weekday and hour
    over the previous 8 weeks, leaving out hours already flagged as anomalies."""
    at = local(hour)
    first = at.date() - timedelta(weeks=WEEKS)
    out = {}
    for lid, by_day in history[(at.weekday(), at.hour)].items():
        values = [count for (day, stamp), count in by_day.items() if first <= day < at.date() and stamp not in flagged]
        if values:
            out[lid] = float(median(values))
    return out


def assess_range(conn, first: datetime, last: datetime, rain_by_hour: dict[datetime, float], settled=None) -> list[Quality]:
    """Assess every hour in [first, last] in order, from the counts stored in pedestrian_hourly.

    `settled(lid, hour)` says whether a sensor has finished reporting an hour; by
    default every stored, non-partial row counts.
    """
    rows = conn.execute(
        "select location_id, hour, count from pedestrian_hourly where not is_partial and hour >= %s and hour <= %s",
        (first - timedelta(weeks=WEEKS, days=1), last),
    ).fetchall()
    history: dict = defaultdict(lambda: defaultdict(dict))
    by_hour: dict[datetime, dict[int, int]] = defaultdict(dict)
    for lid, hour, count in rows:
        at = local(hour)
        history[(at.weekday(), at.hour)][lid][(at.date(), hour)] = count
        by_hour[hour][lid] = count
    known = {
        hour: Quality(hour, judged, low, anomaly, reason, heavy)
        for hour, judged, low, anomaly, reason, heavy in conn.execute(
            "select hour, sensors_judged, sensors_low, anomaly, reason, heavy_rain from feed_quality where hour < %s", (first,)
        )
    }
    flagged = {hour for hour, q in known.items() if q.anomaly}
    heavy = heavy_rain(conn)

    out: list[Quality] = []
    previous = known.get(first - HOUR)
    hour = first
    while hour <= last:
        counts = {lid: c for lid, c in by_hour.get(hour, {}).items() if settled is None or settled(lid, hour)}
        previous = quality.assess(
            hour, local(hour).date(), counts, typicals(history, flagged, hour),
            previous=previous, rain_mm=rain_by_hour.get(hour), heavy=heavy, is_public_holiday=is_public_holiday,
        )
        if previous.anomaly:
            flagged.add(hour)
        out.append(previous)
        hour += HOUR
    return out


def save(conn, assessments: list[Quality]) -> None:
    with conn.transaction(), conn.cursor() as cur:
        cur.executemany(
            """
            insert into feed_quality (hour, sensors_judged, sensors_low, share_low, anomaly, reason, heavy_rain, checked_at)
            values (%s, %s, %s, %s, %s, %s, %s, now())
            on conflict (hour) do update
              set sensors_judged = excluded.sensors_judged, sensors_low = excluded.sensors_low,
                  share_low = excluded.share_low, anomaly = excluded.anomaly, reason = excluded.reason,
                  heavy_rain = excluded.heavy_rain, checked_at = excluded.checked_at
            """,
            [(q.hour, q.judged, q.low, q.share, q.anomaly, q.reason, q.heavy_rain) for q in assessments],
        )


def stored_rain(conn, first: datetime) -> dict[datetime, float]:
    """Rain per hour from the stored forecast (the last forecast made before each hour)."""
    rows = conn.execute("select hour, precipitation from weather_forecast where hour >= %s and precipitation is not null", (first,))
    return {hour: float(mm) for hour, mm in rows}


def observed_rain(first: datetime, last: datetime) -> dict[datetime, float]:
    """Observed rain per hour, for a backfill. Hours the archive hasn't published yet are simply absent."""
    rows = openmeteo.observed(local(first).date(), local(last).date())
    return {w["hour"]: float(w["precipitation"]) for w in rows if w["precipitation"] is not None}


def describe(assessments: list[Quality]) -> None:
    flagged = quality.ranges(assessments)
    print(f"[quality] {len(assessments)} hours assessed, {sum(q.anomaly for q in assessments)} flagged")
    for start, end, share in flagged:
        print(f"[quality]   anomaly {local(start):%a %d %b %H:00} to {local(end + HOUR):%a %d %b %H:00 %Z}, up to {share:.0%} of sensors under half their typical")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--backfill", type=int, metavar="DAYS", help="re-assess this many days instead of the last few hours")
    parser.add_argument("--dry-run", action="store_true", help="assess and print; write nothing")
    parser.add_argument("--verbose", action="store_true", help="print every hour")
    args = parser.parse_args()

    now = datetime.now(UTC)
    with db.connect() as conn:
        newest = conn.execute("select max(hour) from pedestrian_hourly where not is_partial").fetchone()[0]
        if newest is None:
            print("[quality] no finished hours yet")
            return 0
        if args.backfill:
            first = floor_hour(now) - timedelta(days=args.backfill)
            if not args.dry_run:
                with conn.transaction():  # a backfill starts clean, so old flags can't steer the new ones
                    conn.execute("delete from feed_quality where hour >= %s", (first,))
            try:
                rain = observed_rain(first, newest)
            except Exception as exc:  # noqa: BLE001 - rain only relaxes the test; without it the test is stricter
                print(f"[quality] observed rain unavailable ({exc}); assessing without it", file=sys.stderr)
                rain = {}
            rain = {**stored_rain(conn, first), **rain}
            settled = None
        else:
            first = newest - (RECENT_HOURS - 1) * HOUR
            rain = stored_rain(conn, first)
            # In the newest hour some sensors are still uploading; fetch.py recorded which have finished.
            latest = db.get_latest(conn, "pedestrian")
            payload = latest[1] if latest else {"hour": None, "sensors": []}
            latest_hour = parse_ts(payload["hour"]) if payload["hour"] else None
            finished = {s["location_id"] for s in payload["sensors"] if s.get("settled", True)}
            settled = lambda lid, hour: hour != latest_hour or lid in finished  # noqa: E731
        assessments = assess_range(conn, first, newest, rain, settled)
        if args.verbose:
            for q in assessments:
                print(f"  {local(q.hour):%a %d %b %H:00}  judged {q.judged:3d}  low {q.low:3d}  {q.share or 0:5.0%}  {'ANOMALY' if q.anomaly else '':7s} {q.reason}{' (heavy rain)' if q.heavy_rain else ''}")
        describe(assessments)
        if args.dry_run:
            print("dry run: nothing written")
        else:
            save(conn, assessments)
    return 0


if __name__ == "__main__":
    sys.exit(main())
