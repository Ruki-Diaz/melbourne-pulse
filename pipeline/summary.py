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
# Pinned versions, not a -latest alias, so output doesn't change under us.
# Tested 2026-10-01: 3.8 is Google's recommended Flash but often returns 503
# "high demand"; 3.5 is the fallback. The template is the last resort.
GEMINI_MODELS = os.getenv("GEMINI_MODELS", "gemini-3.8-flash,gemini-3.5-flash").split(",")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

PROMPT = """You write the one-line status for "Melbourne Pulse", a live map of
pedestrian counts and parking in Melbourne's CBD. Using ONLY these facts, write
ONE friendly sentence of at most {max_words} words. Plain text, no emoji, no
hashtags, no quotes. Copy any percentage exactly as written; don't add numbers
that aren't here. You may round the pedestrian count. It is the total recorded
by street sensors, and one person can pass several sensors, so call it
"pedestrian counts" or "foot traffic" and never use the word "people". "Usual"
means the median for this weekday and hour over the last 8 weeks.

{facts}"""


def prompt_facts(stats: dict) -> dict:
    """Stats pre-worded so the model can't misread a field (e.g. +26% as '26% of usual')."""
    facts: dict = {}
    if "pedestrians" in stats:
        pct = stats["vs_typical_pct"]
        facts["time"] = f"the hour from {stats['hour_label']} on {stats['day']}"
        facts["pedestrian_counts"] = f"{stats['pedestrians']:,} across {stats['sensors']} sensors"
        facts["compared_with_usual"] = (
            "unknown"
            if pct is None
            else "about the same as usual"
            if abs(pct) < 5
            else f"{abs(pct)}% {'busier' if pct > 0 else 'quieter'} than usual"
        )
        facts["busiest_spots"] = [b["name"] for b in stats["busiest"]]
    if "pct_bays_free" in stats:
        facts["parking"] = f"{stats['pct_bays_free']}% of parking bays are free"
    return facts


def percentages_ok(sentence: str, stats: dict) -> bool:
    """Every percentage in the sentence must be one we actually computed."""
    allowed = {float(abs(v)) for v in (stats.get("vs_typical_pct"), stats.get("pct_bays_free")) if v is not None}
    found = re.findall(r"(\d+(?:\.\d+)?)\s*(?:%|per ?cent)", sentence, flags=re.IGNORECASE)
    return all(float(x) in allowed for x in found)


def wording_ok(sentence: str) -> bool:
    """Sensor counts are not head counts (one person passes several sensors), so no "people"."""
    return re.search(r"\bpeople\b", sentence, flags=re.IGNORECASE) is None


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
            lead = f"Melbourne's CBD sensors logged {stats['pedestrians']:,} pedestrian counts at {stats['hour_label']}"
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
        "contents": [{"parts": [{"text": PROMPT.format(max_words=MAX_WORDS, facts=json.dumps(prompt_facts(stats), indent=1))}]}],
        "generationConfig": {"temperature": 0.7},
    }
    for model in GEMINI_MODELS:
        try:
            resp = requests.post(
                GEMINI_URL.format(model=model.strip()),
                headers={"x-goog-api-key": key},
                json=body,
                timeout=30,
            )
            resp.raise_for_status()
            parts = resp.json()["candidates"][0]["content"]["parts"]
            raw = "".join(p.get("text", "") for p in parts if not p.get("thought"))
        except Exception as exc:  # noqa: BLE001 - try the next model, then the template
            detail = getattr(getattr(exc, "response", None), "text", "")[:200]
            print(f"Gemini {model} failed ({exc}) {detail}", file=sys.stderr)
            continue
        sentence = clean_sentence(raw)
        if sentence is not None and percentages_ok(sentence, stats) and wording_ok(sentence):
            print(f"Gemini {model} ok")
            return sentence
        print(f"Gemini {model} reply rejected ({raw!r})", file=sys.stderr)
    print("no usable Gemini reply; using template", file=sys.stderr)
    return None


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
