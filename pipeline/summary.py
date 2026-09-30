"""Write the one-line summary shown at the top of the site.

Computes a few stats from what fetch.py just stored, sends *only those stats*
to Gemini Flash for one friendly sentence (max 25 words), and stores it in
latest as source='summary'. If Gemini is unavailable or returns something
unusable, a template sentence is stored instead, so the site never breaks.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime

import requests

from pulse import aggregate
from pulse.timeutil import local, parse_ts

MAX_WORDS = 25
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

PROMPT = """You write the one-line status for "Melbourne Pulse", a live map of
Melbourne's CBD. Using ONLY these stats, write ONE friendly sentence of at most
{max_words} words. Plain text, no emoji, no hashtags, no quotes. Don't invent
numbers, and round any you use. vs_typical_pct compares pedestrians with the
median for the same weekday and hour over the last 8 weeks (null = unknown).

{stats}"""


def hour_label(dt: datetime) -> str:
    h = local(dt).hour
    return f"{h % 12 or 12}{'am' if h < 12 else 'pm'}"


def build_stats(pedestrian: dict | None, sensors: list[dict] | None, parking: dict | None) -> dict:
    stats: dict = {}
    if pedestrian and pedestrian.get("sensors"):
        hour = parse_ts(pedestrian["hour"])
        names = {s["location_id"]: s["name"] for s in sensors or []}
        rows = pedestrian["sensors"]
        known = [r for r in rows if r["typical"] is not None]
        typical_total = sum(r["typical"] for r in known)
        busiest = sorted(rows, key=lambda r: r["count"], reverse=True)[:3]
        stats.update(
            hour=hour.isoformat(),
            day=f"{local(hour):%A}",
            hour_label=hour_label(hour),
            pedestrians=sum(r["count"] for r in rows),
            sensors=len(rows),
            vs_typical_pct=(
                round((sum(r["count"] for r in known) / typical_total - 1) * 100)
                if typical_total
                else None
            ),
            busiest=[
                {"name": names.get(r["location_id"], f"Sensor {r['location_id']}"), "count": r["count"]}
                for r in busiest
            ],
        )
    if parking and parking.get("pct_free") is not None:
        stats.update(
            pct_bays_free=round(parking["pct_free"] * 100),
            bays_reporting=parking["bays_free"] + parking["bays_occupied"],
        )
    return stats


def words(text: str) -> int:
    return len(text.split())


def template(stats: dict) -> str:
    """Deterministic fallback sentence; drops detail until it fits 25 words."""
    if "pedestrians" in stats:
        when = f"a typical {stats['day']} at {stats['hour_label']}"
        pct = stats["vs_typical_pct"]
        if pct is None:
            lead = f"Melbourne's CBD counted {stats['pedestrians']:,} people at {stats['hour_label']}"
        elif abs(pct) < 5:
            lead = f"Melbourne's CBD is about as busy as {when}"
        else:
            lead = f"Melbourne's CBD is {abs(pct)}% {'busier' if pct > 0 else 'quieter'} than {when}"
    else:
        lead = "Live pedestrian counts are catching up"
    parking = f"{stats['pct_bays_free']}% of parking bays are free" if "pct_bays_free" in stats else None
    busiest = f"{stats['busiest'][0]['name']} is busiest" if stats.get("busiest") else None

    candidates = []
    if parking and busiest:
        candidates.append(f"{lead}, {parking}, and {busiest}.")
    if parking:
        candidates.append(f"{lead}, and {parking}.")
    if busiest:
        candidates.append(f"{lead}, and {busiest}.")
    candidates.append(f"{lead}.")
    return next(c for c in candidates if words(c) <= MAX_WORDS)


def clean_sentence(text: str | None) -> str | None:
    """Normalise a model reply; None if it isn't one sentence of <= 25 words."""
    if not text:
        return None
    text = re.sub(r"\s+", " ", text).strip().strip('"“”\'').strip()
    if not text or words(text) > MAX_WORDS:
        return None
    if len(re.findall(r"[.!?](?=\s+\S)", text)) > 0:  # more than one sentence
        return None
    if text[-1] not in ".!?":
        text += "."
    return text


def ask_gemini(stats: dict) -> str | None:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        print("GEMINI_API_KEY not set; using template")
        return None
    body = {
        "contents": [{"parts": [{"text": PROMPT.format(max_words=MAX_WORDS, stats=json.dumps(stats, indent=1))}]}],
        "generationConfig": {"temperature": 0.7},
    }
    try:
        resp = requests.post(
            GEMINI_URL.format(model=GEMINI_MODEL),
            headers={"x-goog-api-key": key},
            json=body,
            timeout=30,
        )
        resp.raise_for_status()
        parts = resp.json()["candidates"][0]["content"]["parts"]
        raw = "".join(p.get("text", "") for p in parts if not p.get("thought"))
    except Exception as exc:  # noqa: BLE001 - any failure falls back to the template
        detail = getattr(getattr(exc, "response", None), "text", "")[:200]
        print(f"Gemini failed ({exc}) {detail}; using template", file=sys.stderr)
        return None
    sentence = clean_sentence(raw)
    if sentence is None:
        print(f"Gemini reply rejected ({raw!r}); using template", file=sys.stderr)
    return sentence


def compose(stats: dict) -> dict:
    sentence = ask_gemini(stats)
    return {
        "text": sentence or template(stats),
        "source": "gemini" if sentence else "template",
        "hour": stats.get("hour"),
        "stats": stats,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="use live feeds instead of the database; write nothing")
    args = parser.parse_args()

    if args.dry_run:
        from fetch import collect, pedestrian_payload

        feeds = collect()
        pedestrian = pedestrian_payload(feeds, {}) if feeds.complete_hour else None
        parking = aggregate.parking_hourly(feeds.bays) if feeds.bays else None
        summary = compose(build_stats(pedestrian, feeds.sensors, parking))
        print(json.dumps(summary, indent=2))
        print("dry run: nothing written")
        return 0

    from pulse import db

    with db.connect() as conn:
        pedestrian = db.get_latest(conn, "pedestrian")
        sensors = db.get_latest(conn, "sensors")
        parking = conn.execute(
            "select bays_free, bays_occupied, bays_stale, pct_free from parking_hourly "
            "order by hour desc limit 1"
        ).fetchone()
        stats = build_stats(
            pedestrian[1] if pedestrian else None,
            sensors[1] if sensors else None,
            dict(zip(("bays_free", "bays_occupied", "bays_stale", "pct_free"), parking)) if parking else None,
        )
        summary = compose(stats)
        with conn.transaction():
            db.upsert_latest(conn, "summary", summary)
    print(f"[summary] ({summary['source']}) {summary['text']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
