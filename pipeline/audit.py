"""Check the homepage numbers against the City of Melbourne API.

For the hour the site is showing, recompute from the city's own feeds (never
from our database) and print them next to what the database holds and what
the live page says:
  - pedestrian count total     per-minute feed, summed for that hour
  - % against typical          city's hourly dataset: median of the same weekday
                               and hour over the previous 8 weeks, same sensors
  - % of parking bays free     parking feed now, bays silent for 24 h left out
  - busiest sensor             per-minute feed

It then compares our stored hourly totals for the last few days with the
city's own hourly dataset (published about a day behind), sensor for sensor.
That is the check that tells a fault in the live feed from a real change: if
the city's hourly figures are higher than what the live feed gave us, the live
feed was incomplete.

Without --resolve it is read-only. With --resolve (run daily before the
forecast) it does only that last comparison and records the outcome for each
flagged hour: confirmed_real (unflagged) or confirmed_fault (stays flagged). Parking is a live reading, so the recomputed
figure is as of now while the database's is from the last hourly run.

    python audit.py                      # needs DATABASE_URL
    python audit.py --site https://melbourne-pulse-au.vercel.app
    python audit.py --resolve            # writes resolutions to feed_quality
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from statistics import median

import requests

from pulse import aggregate, api, db
from pulse.history import complete_days
from pulse.timeutil import HOUR, UTC, local, parse_ts
from pulse.typical import WEEKS

SITE = "https://melbourne-pulse-au.vercel.app"
# Our hourly totals normally sit within half a percent of the city's (a few late
# minutes), and the city revises a day upwards by 2-3% after first publishing it.
# A gap beyond this, in either direction, is reported as a mismatch; a feed
# fault is tens of percent.
HOURLY_TOLERANCE = 0.05
# Parking is a live reading: "now" may differ from the last hourly run by a few points.
PARKING_TOLERANCE_PTS = 5
HOURLY_DAYS = 4
RESOLVE_DAYS = 60  # how far back an unresolved flag is still looked up
# The first hour our table took from the live feed (Wed 30 Sep 2026, 3pm Melbourne).
# Everything before it was copied in from the city's hourly dataset by
# seed_history.py, so comparing it with that dataset proves nothing: it would
# always "agree". Flags on those hours are never resolved automatically.
LIVE_FEED_SINCE = datetime(2026, 9, 30, 5, tzinfo=UTC)


def recompute_counts(hour: datetime) -> dict[int, int]:
    """Count per sensor for the hour starting at `hour`, from the per-minute feed."""
    rows = api.export(
        api.PEDESTRIAN_MINUTES,
        where=f"sensing_datetime >= {api.odsql_ts(hour)} and sensing_datetime < {api.odsql_ts(hour + HOUR)}",
    )
    return {lid: count for (lid, _), count in aggregate.hourly_sums(rows).items()}


def recompute_typical(hour: datetime) -> dict[int, float]:
    """Median of the same local weekday and hour over the previous 8 weeks, from the city's hourly dataset."""
    day, hourday = local(hour).date(), local(hour).hour
    days = [day - timedelta(weeks=k) for k in range(1, WEEKS + 1)]
    wanted = " or ".join(f"sensing_date = date'{d}'" for d in days)
    raw = api.export(api.PEDESTRIAN_HOURLY, select="location_id,sensing_date,hourday,pedestriancount", where=wanted)
    # Same zero-filling as the pipeline: a sensor-day with any row is "up", its missing hours are 0.
    filled = complete_days(
        (int(r["location_id"]), date.fromisoformat(r["sensing_date"][:10]), int(r["hourday"]), int(r["pedestriancount"]))
        for r in raw
    )
    values: dict[int, list[int]] = defaultdict(list)
    for lid, _, h, _, count in filled:
        if h == hourday:
            values[lid].append(count)
    return {lid: float(median(v)) for lid, v in values.items()}


def versus(counts: dict[int, int], typical: dict[int, float], sensors: set[int]) -> int | None:
    """Percent against typical over `sensors` that have both a count and a typical."""
    both = [lid for lid in sensors if lid in typical]
    total = sum(typical[lid] for lid in both)
    return round((sum(counts.get(lid, 0) for lid in both) / total - 1) * 100) if total else None


def compare_hours(
    ours: dict[datetime, dict[int, int]], city: dict[datetime, dict[int, int]], flagged: set[datetime] = frozenset()
) -> list[dict]:
    """Hour by hour, our total against the city's over the sensors both have.

    Only hours present in both are compared (the city publishes about a day
    behind). `mismatch` is true when the totals differ by more than the tolerance.
    """
    out = []
    for hour in sorted(set(ours) & set(city)):
        shared = set(ours[hour]) & set(city[hour])
        mine, theirs = sum(ours[hour][s] for s in shared), sum(city[hour][s] for s in shared)
        gap = (mine - theirs) / theirs if theirs else (0.0 if mine == 0 else float("inf"))
        out.append(
            {
                "hour": hour,
                "sensors": len(shared),
                "ours": mine,
                "city": theirs,
                "gap": gap,
                "mismatch": abs(gap) > HOURLY_TOLERANCE,
                "flagged": hour in flagged,
            }
        )
    return out


def city_hourly(first: date) -> dict[datetime, dict[int, int]]:
    """The city's hourly dataset from `first`, leaving out its newest day (still loading)."""
    raw = api.export(
        api.PEDESTRIAN_HOURLY, select="location_id,sensing_date,hourday,pedestriancount", where=f"sensing_date >= date'{first}'"
    )
    parsed = [
        (int(r["location_id"]), date.fromisoformat(r["sensing_date"][:10]), int(r["hourday"]), int(r["pedestriancount"]))
        for r in raw
    ]
    newest = max((p[1] for p in parsed), default=first)
    out: dict[datetime, dict[int, int]] = defaultdict(dict)
    for lid, _, _, stamp, count in complete_days(p for p in parsed if p[1] < newest):
        out[stamp][lid] = count
    return out


def resolution(row: dict) -> str | None:
    """What the city's published total says about a flagged hour.

      confirmed_real   ours agrees with the city's within the tolerance: the low
                       counts are what the city recorded too, so the hour was
                       really that quiet (a storm, an event). It is unflagged and
                       counts as normal data again.
      confirmed_fault  ours is more than the tolerance below the city's: the live
                       feed was incomplete. The hour stays flagged.

    None for an hour that isn't flagged, or where ours is above the city's
    (neither explanation fits; it is reported as a mismatch and left as it is),
    or that was seeded from the city's dataset rather than taken from the live
    feed (the comparison would be circular, so the flag stands until someone
    removes it by hand).
    """
    if not row["flagged"] or row["hour"] < LIVE_FEED_SINCE:
        return None
    if abs(row["gap"]) <= HOURLY_TOLERANCE:
        return "confirmed_real"
    return "confirmed_fault" if row["gap"] < 0 else None


def hourly_comparison(conn) -> tuple[list[dict], set[datetime]]:
    """Our stored hourly totals beside the city's hourly dataset, and the hours still flagged and unresolved."""
    today = local(datetime.now(UTC)).date()
    # Unresolved flags are compared however old they are (within what the tables keep).
    flagged = {
        row[0]
        for row in conn.execute(
            "select hour from feed_quality where anomaly and resolution is null and hour >= %s",
            (today - timedelta(days=RESOLVE_DAYS),),
        )
    }
    first = min([today - timedelta(days=HOURLY_DAYS)] + [local(h).date() for h in flagged])
    ours: dict[datetime, dict[int, int]] = defaultdict(dict)
    for lid, hour, count in conn.execute(
        "select location_id, hour, count from pedestrian_hourly where not is_partial and hour >= %s", (first,)
    ):
        ours[hour][lid] = count
    return compare_hours(ours, city_hourly(first), flagged), flagged


def resolve(conn, hours: list[dict]) -> dict[str, int]:
    """Record what the city's figures say about each flagged hour that can now be compared.

    A confirmed_real hour is unflagged (anomaly = false), so everything uses it
    again. A confirmed_fault hour stays flagged for the website, whose live
    table holds the incomplete counts; the model and the rain effect read the
    city's final figures, which are right, so they use it (they skip only
    unresolved hours). Only unresolved rows are touched, so a resolution is final.
    """
    done = {"confirmed_real": 0, "confirmed_fault": 0}
    with conn.transaction():
        for row in hours:
            verdict = resolution(row)
            if verdict is None:
                continue
            changed = conn.execute(
                "update feed_quality set resolution = %s, anomaly = %s, checked_at = now() where hour = %s and resolution is null",
                (verdict, verdict == "confirmed_fault", row["hour"]),
            ).rowcount
            done[verdict] += changed
    return done


def report_hourly(hours: list[dict], flagged: set[datetime]) -> bool:
    """Print the comparison with the city's hourly dataset. True if every compared hour matched."""
    bad = [h for h in hours if h["mismatch"]]
    print(f"\nour hourly totals vs the city's hourly dataset: {len(hours)} hours compared, {len(bad)} mismatched (over {HOURLY_TOLERANCE:.0%})")
    if hours:
        print(f"  compared {local(hours[0]['hour']):%a %d %b %H:00} to {local(hours[-1]['hour']):%a %d %b %H:00 %Z}")
    for h in bad:
        print(
            f"  MISMATCH {local(h['hour']):%a %d %b %H:00}: ours {h['ours']:,} vs city {h['city']:,} "
            f"({h['gap']:+.0%}, {h['sensors']} sensors){'  [flagged]' if h['flagged'] else ''}"
        )
    for verdict, meaning in (
        ("confirmed_real", "match the city's own figures: really that quiet, to be unflagged"),
        ("confirmed_fault", "are well below the city's own figures: the live feed was incomplete, to stay flagged on the site"),
    ):
        found = [h for h in hours if resolution(h) == verdict]
        if found:
            print(f"  {len(found)} flagged hours {meaning} ({local(found[0]['hour']):%a %d %b %H:00} to {local(found[-1]['hour']):%a %d %b %H:00})")
    seeded = sorted(h["hour"] for h in hours if h["flagged"] and h["hour"] < LIVE_FEED_SINCE)
    if seeded:
        print(
            f"  {len(seeded)} flagged hours ({local(seeded[0]):%a %d %b %H:00} to {local(seeded[-1]):%a %d %b %H:00}) were seeded from the "
            "city's dataset, not taken from the live feed: they are never resolved automatically and stay flagged."
        )
    waiting = sorted(flagged - {h["hour"] for h in hours})
    if waiting:
        print(
            f"  {len(waiting)} flagged hours ({local(waiting[0]):%a %d %b %H:00} to {local(waiting[-1]):%a %d %b %H:00}) are not in the "
            "city's hourly dataset yet. They will be resolved once it publishes them."
        )
    return not bad


def resolve_flagged() -> int:
    """`--resolve`: compare flagged hours with the city's figures and record the outcome.

    Runs before the daily forecast. A problem reaching the city's API is logged
    and the run still exits 0: an unresolved hour simply stays flagged for another day.
    """
    with db.connect() as conn:
        try:
            hours, flagged = hourly_comparison(conn)
        except Exception as exc:  # noqa: BLE001 - never block the forecast on this
            print(f"[resolve] could not compare with the city's hourly dataset ({exc}); nothing resolved", file=sys.stderr)
            return 0
        report_hourly(hours, flagged)
        done = resolve(conn, hours)
    print(f"[resolve] {done['confirmed_real']} hours confirmed real and unflagged; {done['confirmed_fault']} confirmed as a feed fault")
    return 0


def read_site(url: str) -> dict:
    """The numbers the page was rendered with (they are in its HTML as component props)."""
    html = requests.get(url, headers=api.HEADERS, timeout=30).text.replace('\\"', '"')

    def find(pattern: str):
        match = re.search(pattern, html)
        return match.group(1) if match else None

    busiest = find(r'"busiestSpot":(\{[^}]*\})')
    return {
        "hour": find(r'"hourIso":"([^"]+)"'),
        "total": int(find(r'"totalPedestrians":(\d+)') or -1),
        "pct_free": int(find(r'"pctParkingFree":(\d+)') or -1),
        "busiest": json.loads(busiest) if busiest else None,
        "sentence": find(r'"description":"([^"]+)"'),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--site", default=SITE, help="live site to read (default: %(default)s)")
    parser.add_argument(
        "--resolve", action="store_true",
        help="only compare flagged hours with the city's hourly dataset and record the outcome in feed_quality",
    )
    args = parser.parse_args()
    if args.resolve:
        return resolve_flagged()

    with db.connect() as conn:
        updated, payload = db.get_latest(conn, "pedestrian")
        names = {s["location_id"]: s["name"] for s in db.get_latest(conn, "sensors")[1]}
        summary = db.get_latest(conn, "summary")[1]
        parking_hour, pct_free = conn.execute("select hour, pct_free from parking_hourly order by hour desc limit 1").fetchone()
        anomaly = db.feed_anomaly(conn, parse_ts(payload["hour"]))
        hourly_ok = report_hourly(*hourly_comparison(conn))
    hour = parse_ts(payload["hour"])
    stored = [s for s in payload["sensors"] if s.get("settled", True)]
    stored_ids = {s["location_id"] for s in stored}
    with_typical = [s for s in stored if s["typical"] is not None]
    db_typical = sum(s["typical"] for s in with_typical)
    db_top = max(stored, key=lambda s: s["count"])

    print(f"\nhour audited: {local(hour):%a %d %b %H:00 %Z} (database written {local(updated):%H:%M})")
    if anomaly:
        print(f"  this hour is flagged as a feed anomaly ({anomaly['low']} of {anomaly['judged']} sensors low): the site shows a warning, not a comparison")
    counts = recompute_counts(hour)
    typical = recompute_typical(hour)
    bays = aggregate.slim_parking(api.export(api.PARKING), datetime.now(UTC))
    now_pct = aggregate.parking_hourly(bays)["pct_free"]
    top = max(counts, key=counts.get)
    site = read_site(args.site)
    same_hour = site["hour"] is not None and parse_ts(site["hour"]) == hour
    site_pct = re.search(r"(\d+)% (busier|quieter)", site["sentence"] or "")
    site_vs = None if not site_pct else int(site_pct.group(1)) * (1 if site_pct.group(2) == "busier" else -1)

    rows = [
        (
            "Pedestrian count total",
            f"{site['total']:,}",
            f"{sum(s['count'] for s in stored):,} ({len(stored)} sensors)",
            f"{sum(counts.get(lid, 0) for lid in stored_ids):,} (same {len(stored)} sensors); {sum(counts.values()):,} over all {len(counts)} in the feed now",
            sum(counts.get(lid, 0) for lid in stored_ids) == sum(s["count"] for s in stored) == site["total"],
        ),
        (
            "% against typical",
            "n/a" if site_vs is None else f"{site_vs:+d}%",
            f"{summary['stats'].get('vs_typical_pct'):+d}%" if summary["stats"].get("vs_typical_pct") is not None else "n/a",
            f"{versus(counts, typical, {s['location_id'] for s in with_typical}):+d}% (city hourly data, same {len(with_typical)} sensors; typical {sum(typical.get(s['location_id'], 0) for s in with_typical):,.0f} vs ours {db_typical:,})",
            versus(counts, typical, {s["location_id"] for s in with_typical}) == summary["stats"].get("vs_typical_pct") == site_vs,
        ),
        (
            "% parking bays free",
            f"{site['pct_free']}%",
            f"{round(pct_free * 100)}% (at {local(parking_hour):%H:00})",
            f"{round(now_pct * 100)}% (now, {sum(1 for b in bays if not b['stale']):,} bays reporting, {sum(1 for b in bays if b['stale']):,} stale left out)",
            abs(round(now_pct * 100) - round(pct_free * 100)) <= PARKING_TOLERANCE_PTS and site["pct_free"] == round(pct_free * 100),
        ),
        (
            "Busiest sensor",
            f"{site['busiest']['name']} ({site['busiest']['count']})" if site["busiest"] else "n/a",
            f"{names.get(db_top['location_id'])} ({db_top['count']})",
            f"{names.get(top)} ({counts[top]})",
            bool(site["busiest"]) and names.get(top) == names.get(db_top["location_id"]) == site["busiest"]["name"] and counts[top] == db_top["count"],
        ),
    ]
    print(f"live site shows hour {site['hour']}{'' if same_hour else '  (NOT the hour in the database: the page is from another run)'}")
    print(f"live sentence: {site['sentence']}\n")
    print("| Number | Live site | Database | Recomputed from the city API | Match? |")
    print("|---|---|---|---|---|")
    for name, live, stored_value, fresh, ok in rows:
        print(f"| {name} | {live} | {stored_value} | {fresh} | {'yes' if ok else 'NO'} |")
    return 0 if all(r[-1] for r in rows) and same_hour and hourly_ok else 1


if __name__ == "__main__":
    sys.exit(main())
