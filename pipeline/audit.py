"""Check the homepage numbers against the City of Melbourne API.

For the hour the site is showing, recompute from the city's own feeds (never
from our database) and print them next to what the database holds and what
the live page says:
  - pedestrian count total     per-minute feed, summed for that hour
  - % against typical          city's hourly dataset: median of the same weekday
                               and hour over the previous 8 weeks, same sensors
  - % of parking bays free     parking feed now, bays silent for 24 h left out
  - busiest sensor             per-minute feed

Read-only: it writes nothing. Parking is a live reading, so the recomputed
figure is as of now while the database's is from the last hourly run.

    python audit.py                      # needs DATABASE_URL
    python audit.py --site https://melbourne-pulse-au.vercel.app
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
    args = parser.parse_args()

    with db.connect() as conn:
        updated, payload = db.get_latest(conn, "pedestrian")
        names = {s["location_id"]: s["name"] for s in db.get_latest(conn, "sensors")[1]}
        summary = db.get_latest(conn, "summary")[1]
        parking_hour, pct_free = conn.execute("select hour, pct_free from parking_hourly order by hour desc limit 1").fetchone()
    hour = parse_ts(payload["hour"])
    stored = [s for s in payload["sensors"] if s.get("settled", True)]
    stored_ids = {s["location_id"] for s in stored}
    with_typical = [s for s in stored if s["typical"] is not None]
    db_typical = sum(s["typical"] for s in with_typical)
    db_top = max(stored, key=lambda s: s["count"])

    print(f"hour audited: {local(hour):%a %d %b %H:00 %Z} (database written {local(updated):%H:%M})")
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
            abs(round(now_pct * 100) - round(pct_free * 100)) <= 2 and site["pct_free"] == round(pct_free * 100),
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
    return 0 if all(r[-1] for r in rows) and same_hour else 1


if __name__ == "__main__":
    sys.exit(main())
