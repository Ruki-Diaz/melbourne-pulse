"""Write the one-line summary shown at the top of the site.

Computes a few stats from what fetch.py just stored, sends *only those stats*
to Gemini Flash for one friendly sentence (max 30 words), and stores it in
latest as source='summary'. If Gemini is unavailable or returns something
unusable, a template sentence is stored instead, so the site never breaks.

Two rules protect the sentence from saying something the data doesn't:
- Only sensors that have finished reporting the hour are counted, and the
  comparison with "usual" uses the same sensors on both sides. If fewer than
  80% of sensors have reported, the sentence says so.
- Rain is mentioned only if the stored forecast has a rain-risk hour in the
  next 6, and its start time and percentage must match the forecast exactly.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta

import requests

from pulse import aggregate, openmeteo
from pulse.timeutil import HOUR, UTC, floor_hour, local, parse_ts

MAX_WORDS = 30
# Pinned versions, not a -latest alias, so output doesn't change under us.
# Tested 2026-10-01: 3.8 is Google's recommended Flash but often returns 503
# "high demand"; 3.5 is the fallback. The template is the last resort.
GEMINI_MODELS = os.getenv("GEMINI_MODELS", "gemini-3.8-flash,gemini-3.5-flash").split(",")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

# Below this share of sensors reporting, the sentence says so (and is always the template).
MIN_COVERAGE = 0.8
# Rain: the same thresholds as the Plan page (web/lib/plan-core.ts).
RAIN_HOURS = 6
RAIN_PROB_PCT = 50
RAIN_MM = 0.2
WEATHER_MAX_AGE = timedelta(hours=3)  # an older forecast is not mentioned at all

PROMPT = """You write the one-line status for "Melbourne Pulse", a live map of
pedestrian counts and parking in Melbourne's CBD. Using ONLY these facts, write
ONE friendly sentence of at most {max_words} words. Plain text, no emoji, no
hashtags, no quotes. Copy any percentage exactly as written; don't add numbers
that aren't here. You may round the pedestrian count. It is the total recorded
by street sensors, and one person can pass several sensors, so call it
"pedestrian counts" or "foot traffic" and never use the word "people". "Usual"
means the median for this weekday and hour over the last 8 weeks.
If there is a "rain" fact, add ONE short clause with it, using the word "rain"
and copying its time exactly, for example "rain likely from 3pm". If there is
no "rain" fact, do not mention the weather at all.

{facts}"""


def rain_phrase(rain: dict) -> str:
    """'rain likely from 3pm', or 'rain likely now' when it starts in the hour in progress."""
    return "rain likely now" if rain["start_label"] == "now" else f"rain likely from {rain['start_label']}"


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
    if stats.get("rain"):
        chance = stats["rain"]["max_prob"]
        facts["rain"] = rain_phrase(stats["rain"]) + (f" (up to {chance}% chance)" if chance is not None else "")
    return facts


def percentages_ok(sentence: str, stats: dict) -> bool:
    """Every percentage in the sentence must be one we actually computed."""
    values = [stats.get("vs_typical_pct"), stats.get("pct_bays_free"), (stats.get("rain") or {}).get("max_prob")]
    allowed = {float(abs(v)) for v in values if v is not None}
    found = re.findall(r"(\d+(?:\.\d+)?)\s*(?:%|per ?cent)", sentence, flags=re.IGNORECASE)
    return all(float(x) in allowed for x in found)


def wording_ok(sentence: str) -> bool:
    """Sensor counts are not head counts (one person passes several sensors), so no "people"."""
    return re.search(r"\bpeople\b", sentence, flags=re.IGNORECASE) is None


TIME = re.compile(r"\b(\d{1,2})(?::(\d{2}))?\s*([ap])\.?m\b\.?", flags=re.IGNORECASE)
WEATHER_WORDS = re.compile(r"\b(rain\w*|shower\w*|drizzl\w*|storm\w*|umbrella\w*|wet|dry|weather|forecast)\b", flags=re.IGNORECASE)


def times_in(sentence: str) -> set[str]:
    """Clock times in a sentence, normalised to '3pm' / '3:30pm'; 'noon' and 'midnight' count too."""
    found = {
        f"{int(h)}{':' + m if m and m != '00' else ''}{ap.lower()}m" for h, m, ap in TIME.findall(sentence)
    }
    lowered = sentence.lower()
    if re.search(r"\b(noon|midday)\b", lowered):
        found.add("12pm")
    if re.search(r"\bmidnight\b", lowered):
        found.add("12am")
    return found


def weather_ok(sentence: str, stats: dict) -> bool:
    """Rain is mentioned exactly when the forecast says so, and with the right start time.

    - Every clock time in the sentence must be the hour being described or the rain start.
    - With rain forecast, the sentence must say "rain" and give the start ("from 3pm", or "now").
    - With none, it must not mention the weather at all.
    (Percentages, including the rain chance, are checked by percentages_ok.)
    """
    rain = stats.get("rain")
    allowed = {stats.get("hour_label")} | ({rain["start_label"]} if rain else set())
    if not times_in(sentence) <= allowed:
        return False
    if not rain:
        return WEATHER_WORDS.search(sentence) is None
    if re.search(r"\brain", sentence, flags=re.IGNORECASE) is None:
        return False
    if rain["start_label"] == "now":
        return re.search(r"\b(now|already|currently)\b", sentence, flags=re.IGNORECASE) is not None
    return rain["start_label"] in times_in(sentence)


def hour_label(dt: datetime) -> str:
    h = local(dt).hour
    return f"{h % 12 or 12}{'am' if h < 12 else 'pm'}"


def rain_outlook(weather: list[dict] | None, now: datetime) -> dict | None:
    """The first rain-risk hour in the next 6, and the highest chance of rain in that time.

    `weather` rows have hour (UTC hour start), precipitation, precipitation_probability
    and fetched_at. An hour is a rain risk from a 50% chance or 0.2 mm. Returns None
    if there is no such hour, or the forecast is too old to quote.
    """
    first = floor_hour(now)
    rows = sorted((w for w in weather or [] if first <= w["hour"] < first + RAIN_HOURS * HOUR), key=lambda w: w["hour"])
    if not rows or max(w["fetched_at"] for w in rows) < now - WEATHER_MAX_AGE:
        return None
    risky = [
        w for w in rows
        if (w["precipitation_probability"] or 0) >= RAIN_PROB_PCT or (w["precipitation"] or 0) >= RAIN_MM
    ]
    if not risky:
        return None
    chances = [w["precipitation_probability"] for w in rows if w["precipitation_probability"] is not None]
    start = risky[0]["hour"]
    return {
        "start_hour": start.isoformat(),
        "start_label": "now" if start == first else hour_label(start),
        "max_prob": round(max(chances)) if chances else None,
    }


def build_stats(
    pedestrian: dict | None,
    sensors: list[dict] | None,
    parking: dict | None,
    weather: list[dict] | None = None,
    now: datetime | None = None,
) -> dict:
    stats: dict = {}
    if pedestrian and pedestrian.get("sensors"):
        hour = parse_ts(pedestrian["hour"])
        names = {s["location_id"]: s["name"] for s in sensors or []}
        # Only sensors that have finished reporting the hour (fetch.pedestrian_payload).
        rows = [r for r in pedestrian["sensors"] if r.get("settled", True)]
        active = (pedestrian.get("coverage") or {}).get("active", len(rows))
        # Actual and typical are summed over the SAME sensors: those that have both.
        known = [r for r in rows if r["typical"] is not None]
        typical_total = sum(r["typical"] for r in known)
        busiest = sorted(rows, key=lambda r: r["count"], reverse=True)[:3]
        stats.update(
            hour=hour.isoformat(),
            day=f"{local(hour):%A}",
            hour_label=hour_label(hour),
            pedestrians=sum(r["count"] for r in rows),
            sensors=len(rows),
            sensors_active=active,
            low_coverage=len(rows) < MIN_COVERAGE * active,
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
    rain = rain_outlook(weather, now) if now is not None else None
    if rain:
        stats["rain"] = rain
    return stats


def words(text: str) -> int:
    return len(text.split())


def template(stats: dict) -> str:
    """Deterministic fallback sentence; drops detail until it fits 30 words.

    Low sensor coverage and rain are never dropped: every candidate keeps them.
    """
    if stats.get("sensors"):
        when = f"a typical {stats['day']} at {stats['hour_label']}"
        pct = stats["vs_typical_pct"]
        if pct is None:
            lead = f"Melbourne's CBD sensors logged {stats['pedestrians']:,} pedestrian counts at {stats['hour_label']}"
        elif abs(pct) < 5:
            lead = f"Melbourne's CBD is about as busy as {when}"
        else:
            lead = f"Melbourne's CBD is {abs(pct)}% {'busier' if pct > 0 else 'quieter'} than {when}"
        if stats.get("low_coverage"):
            reporting = f"{stats['sensors']} of {stats['sensors_active']} sensors reporting so far"
            lead = (
                f"The {reporting} logged {stats['pedestrians']:,} pedestrian counts at {stats['hour_label']}"
                if pct is None
                else f"With {reporting}, {lead}"
            )
    else:
        lead = "Live pedestrian counts are catching up"
    parking = f"{stats['pct_bays_free']}% of parking bays are free" if "pct_bays_free" in stats else None
    busiest = f"{stats['busiest'][0]['name']} is busiest" if stats.get("busiest") else None
    rain = f", with {rain_phrase(stats['rain'])}" if stats.get("rain") else ""

    candidates = []
    if parking and busiest:
        candidates.append(f"{lead}, {parking}, and {busiest}{rain}.")
    if parking:
        candidates.append(f"{lead}, and {parking}{rain}.")
    if busiest:
        candidates.append(f"{lead}, and {busiest}{rain}.")
    candidates.append(f"{lead}{rain}.")
    return next((c for c in candidates if words(c) <= MAX_WORDS), candidates[-1])


def clean_sentence(text: str | None) -> str | None:
    """Normalise a model reply; None if it isn't one sentence of <= 30 words."""
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


def sentence_ok(sentence: str, stats: dict) -> bool:
    """Every check a model-written sentence must pass; otherwise the template is used."""
    return percentages_ok(sentence, stats) and wording_ok(sentence) and weather_ok(sentence, stats)


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
        if sentence is not None and sentence_ok(sentence, stats):
            print(f"Gemini {model} ok")
            return sentence
        print(f"Gemini {model} reply rejected ({raw!r})", file=sys.stderr)
    print("no usable Gemini reply; using template", file=sys.stderr)
    return None


def compose(stats: dict) -> dict:
    # With few sensors reporting, the sentence has to say so: only the template guarantees that.
    if stats.get("low_coverage") or not stats.get("sensors", 1):
        print("low sensor coverage; using the template")
        sentence = None
    else:
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
        now = datetime.now(UTC)
        try:
            weather = [{**w, "fetched_at": now} for w in openmeteo.forecast()]
        except Exception as exc:  # noqa: BLE001 - weather is optional
            print(f"weather forecast unavailable ({exc}); no rain clause", file=sys.stderr)
            weather = None
        summary = compose(build_stats(pedestrian, feeds.sensors, parking, weather, now))
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
            db.upcoming_weather(conn),
            datetime.now(UTC),
        )
        summary = compose(stats)
        with conn.transaction():
            db.upsert_latest(conn, "summary", summary)
    print(f"[summary] ({summary['source']}) {summary['text']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
