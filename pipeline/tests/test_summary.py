import pytest

from datetime import datetime, timedelta, timezone

import summary
from conftest import utc
from fetch import Feeds, pedestrian_payload
from pulse.aggregate import HourCount, is_settled, sensor_watermarks
from summary import (
    MAX_WORDS, PROMPT, build_stats, clean_sentence, percentages_ok, prompt_facts, rain_outlook, sentence_ok,
    template, weather_ok, words, wording_ok,
)

PEDESTRIAN = {
    "hour": "2026-10-01T03:00:00+00:00",  # 1pm AEST, Thursday
    "sensors": [
        {"location_id": 3, "count": 1200, "typical": 1000},
        {"location_id": 5, "count": 900, "typical": 800},
        {"location_id": 11, "count": 300, "typical": None},
    ],
}
SENSORS = [
    {"location_id": 3, "name": "Melbourne Central"},
    {"location_id": 5, "name": "Princes Bridge"},
    {"location_id": 11, "name": "Docklands Waterfront City Building Side"},
]
PARKING = {"bays_free": 2000, "bays_occupied": 3000, "bays_stale": 900, "pct_free": 0.4}


def test_build_stats():
    stats = build_stats(PEDESTRIAN, SENSORS, PARKING)
    assert stats["pedestrians"] == 2400
    assert stats["vs_typical_pct"] == round((2100 / 1800 - 1) * 100)  # sensor 11 has no typical
    assert stats["day"] == "Thursday" and stats["hour_label"] == "1pm"
    assert [b["name"] for b in stats["busiest"]] == ["Melbourne Central", "Princes Bridge", SENSORS[2]["name"]]
    assert stats["pct_bays_free"] == 40 and stats["bays_reporting"] == 5000


def test_template_full():
    text = template(build_stats(PEDESTRIAN, SENSORS, PARKING))
    assert text == (
        "Melbourne's CBD is 17% busier than a typical Thursday at 1pm, "
        "40% of parking bays are free, and Melbourne Central is busiest."
    )


@pytest.mark.parametrize(
    "stats",
    [
        {},
        build_stats(PEDESTRIAN, SENSORS, None),
        build_stats(None, None, PARKING),
        {**build_stats(PEDESTRIAN, SENSORS, PARKING), "vs_typical_pct": None},
        {
            **build_stats(PEDESTRIAN, SENSORS, PARKING),
            "busiest": [{"name": "A Very Long Sensor Description That Goes On And On Near Somewhere", "count": 1}],
        },
    ],
)
def test_template_always_fits(stats):
    text = template(stats)
    assert text.endswith(".") and words(text) <= MAX_WORDS


def test_clean_sentence():
    assert clean_sentence('  "The CBD is buzzing today"\n') == "The CBD is buzzing today."
    assert clean_sentence("One sentence. Then another.") is None
    assert clean_sentence("word " * 31) is None
    assert clean_sentence("word " * 30) is not None  # the limit is 30 words
    assert clean_sentence("") is None
    assert clean_sentence("Around 2,400 people passed 99.5% of sensors!") == "Around 2,400 people passed 99.5% of sensors!"


def test_prompt_facts_are_pre_worded():
    facts = prompt_facts(build_stats(PEDESTRIAN, SENSORS, PARKING))
    assert facts["compared_with_usual"] == "17% busier than usual"
    assert facts["parking"] == "40% of parking bays are free"
    assert facts["time"] == "the hour from 1pm on Thursday"
    assert facts["pedestrian_counts"] == "2,400 across 3 sensors"


def test_wording_is_pedestrian_counts_never_people():
    assert wording_ok("Foot traffic is 17% above usual, with 2,400 pedestrian counts this hour.")
    assert not wording_ok("About 2,400 people are in the CBD right now.")
    assert not wording_ok("People are out in force this afternoon.")
    assert '"pedestrian counts"' in PROMPT and "people_counted" not in str(prompt_facts(build_stats(PEDESTRIAN, SENSORS, PARKING)))
    # The fallback sentence follows the same rule, including when there is no typical to compare with.
    no_typical = {**build_stats(PEDESTRIAN, SENSORS, PARKING), "vs_typical_pct": None}
    for stats in (build_stats(PEDESTRIAN, SENSORS, PARKING), no_typical):
        assert wording_ok(template(stats))
    assert "2,400 pedestrian counts" in template(no_typical)


def test_percentages_must_match_the_real_stats():
    # Real case from 2026-10-01: stats said +26% and 72% free; Gemini wrote otherwise.
    stats = {"vs_typical_pct": 26, "pct_bays_free": 72}
    assert percentages_ok("The CBD is 26% busier than usual and 72% of bays are free.", stats)
    assert percentages_ok("A quiet night with plenty of parking.", stats)
    assert not percentages_ok("Melbourne has about 25% of the usual crowd, with 70% of bays free.", stats)
    assert not percentages_ok("Foot traffic is 26 percent above typical and 70 per cent of bays are free.", stats)
    assert percentages_ok("Crowds are 17% lighter than usual.", {"vs_typical_pct": -17})


# ------------------------------------------------- only finished hours are compared

HOUR = utc(2026, 10, 1, 3)  # Thu 1pm AEST: the latest complete hour of the feed as a whole


def minute(sensor: int, at: datetime, count: int) -> dict:
    return {"location_id": sensor, "sensing_datetime": at.isoformat(), "total_of_directions": count}


def test_a_sensor_has_settled_once_its_own_newest_minute_reaches_the_end_of_the_hour():
    assert is_settled(HOUR + timedelta(minutes=59), HOUR)  # a 1-minute sensor's last minute
    assert is_settled(HOUR + timedelta(minutes=55), HOUR)  # a 5-minute sensor's last bucket
    assert is_settled(HOUR + timedelta(hours=1, minutes=20), HOUR)  # already into the next hour
    assert not is_settled(HOUR + timedelta(minutes=20), HOUR)  # still uploading this hour
    assert not is_settled(HOUR - timedelta(minutes=5), HOUR)  # hasn't started it
    assert not is_settled(None, HOUR)


def feeds_with_a_lagging_sensor() -> Feeds:
    """Sensors 3 and 5 have reported the whole 1pm hour. Sensor 11 has only sent its first 20 minutes."""
    rows = (
        [minute(3, HOUR + timedelta(minutes=m), 20) for m in range(60)]  # 1,200
        + [minute(5, HOUR + timedelta(minutes=m), 75) for m in range(0, 60, 5)]  # 900
        + [minute(11, HOUR + timedelta(minutes=m), 5) for m in range(20)]  # 100 so far; typical 600
        + [minute(3, HOUR + timedelta(hours=1, minutes=10), 4)]  # the feed is into the 2pm hour
    )
    hours = [
        HourCount(3, HOUR, 1200, False), HourCount(5, HOUR, 900, False), HourCount(11, HOUR, 100, False),
        HourCount(3, HOUR + timedelta(hours=1), 4, True),
    ]
    return Feeds(now=HOUR + timedelta(hours=1, minutes=35), pedestrian=hours, watermarks=sensor_watermarks(rows))


def test_the_latest_hour_marks_which_sensors_have_finished_reporting():
    payload = pedestrian_payload(feeds_with_a_lagging_sensor(), {3: 1000, 5: 800, 11: 600})
    assert payload["hour"] == HOUR.isoformat()  # never the 2pm hour, which is still filling up
    assert {s["location_id"]: s["settled"] for s in payload["sensors"]} == {3: True, 5: True, 11: False}
    assert payload["coverage"] == {"reporting": 2, "active": 3}


def test_actual_and_typical_use_the_same_finished_sensors():
    payload = pedestrian_payload(feeds_with_a_lagging_sensor(), {3: 1000, 5: 800, 11: 600})
    stats = build_stats(payload, SENSORS, PARKING)
    # Sensor 11's part-hour (100 against a typical 600) is left out of BOTH sides.
    assert stats["pedestrians"] == 2100 and stats["sensors"] == 2 and stats["sensors_active"] == 3
    assert stats["vs_typical_pct"] == round((2100 / 1800 - 1) * 100) == 17
    assert [b["name"] for b in stats["busiest"]] == ["Melbourne Central", "Princes Bridge"]
    # Counting the part-hour as if it were complete would have read as quieter than usual:
    assert round((2200 / 2400 - 1) * 100) == -8


def test_a_sensor_without_a_typical_is_left_out_of_both_sides_too():
    payload = pedestrian_payload(feeds_with_a_lagging_sensor(), {3: 1000})  # sensor 5 has no baseline yet
    stats = build_stats(payload, SENSORS, PARKING)
    assert stats["pedestrians"] == 2100  # the count shown still includes sensor 5
    assert stats["vs_typical_pct"] == 20  # 1,200 against 1,000: sensor 3 alone on both sides


def test_low_coverage_is_said_in_the_sentence_and_never_left_to_gemini(monkeypatch):
    payload = pedestrian_payload(feeds_with_a_lagging_sensor(), {3: 1000, 5: 800, 11: 600})
    stats = build_stats(payload, SENSORS, PARKING)
    assert stats["low_coverage"]  # 2 of 3 is under 80%
    monkeypatch.setattr(summary, "ask_gemini", lambda _: pytest.fail("Gemini must not be asked"))
    result = summary.compose(stats)
    assert result["source"] == "template"
    assert result["text"].startswith("With 2 of 3 sensors reporting so far, Melbourne's CBD is 17% busier than a typical Thursday at 1pm")
    assert words(result["text"]) <= MAX_WORDS

    full = build_stats(PEDESTRIAN, SENSORS, PARKING)  # an older payload without the flags: every sensor counts
    assert not full["low_coverage"] and full["sensors"] == full["sensors_active"] == 3


# ------------------------------------------------------------------- rain clause

NOW = utc(2026, 10, 1, 3, 20)  # Thu 1:20pm AEST


def forecast(*hours: tuple[float | None, float | None], fetched_at: datetime = NOW) -> list[dict]:
    """Weather rows from the hour in progress: (chance of rain %, mm) per hour."""
    start = NOW.replace(minute=0)
    return [
        {"hour": start + timedelta(hours=i), "precipitation_probability": prob, "precipitation": mm, "fetched_at": fetched_at}
        for i, (prob, mm) in enumerate(hours)
    ]


def test_rain_outlook_is_the_first_rain_risk_hour_in_the_next_six():
    dry, wet = (10, 0.0), (80, 1.2)
    assert rain_outlook(forecast(dry, dry, wet, (65, 0.4), dry, dry), NOW) == {
        "start_hour": "2026-10-01T05:00:00+00:00", "start_label": "3pm", "max_prob": 80}
    assert rain_outlook(forecast(dry, (49, 0.1), dry, dry, dry, dry), NOW) is None  # just under both thresholds
    assert rain_outlook(forecast(dry, (20, 0.2), dry, dry, dry, dry), NOW)["start_label"] == "2pm"  # by amount
    assert rain_outlook(forecast(dry, (50, 0.0), dry, dry, dry, dry), NOW)["max_prob"] == 50  # by chance
    assert rain_outlook(forecast(wet, dry, dry, dry, dry, dry), NOW)["start_label"] == "now"
    assert rain_outlook(forecast(dry, dry, dry, dry, dry, dry, wet), NOW) is None  # the 7th hour is too far off
    assert rain_outlook(forecast(dry, (None, 0.5), dry), NOW) == {
        "start_hour": "2026-10-01T04:00:00+00:00", "start_label": "2pm", "max_prob": 10}
    assert rain_outlook([], NOW) is None and rain_outlook(None, NOW) is None


def test_a_stale_forecast_is_never_quoted():
    old = forecast((10, 0.0), (90, 2.0), fetched_at=NOW - timedelta(hours=4))
    assert rain_outlook(old, NOW) is None
    assert "rain" not in build_stats(PEDESTRIAN, SENSORS, PARKING, old, NOW)


RAINY = build_stats(PEDESTRIAN, SENSORS, PARKING, forecast((10, 0.0), (10, 0.0), (80, 1.2)), NOW)
DRY = build_stats(PEDESTRIAN, SENSORS, PARKING, forecast((10, 0.0), (20, 0.0)), NOW)


def test_gemini_is_given_the_rain_fact_only_when_there_is_rain():
    assert prompt_facts(RAINY)["rain"] == "rain likely from 3pm (up to 80% chance)"
    assert "rain" not in prompt_facts(DRY)
    assert "rain" in PROMPT and str(MAX_WORDS) == "30"


def test_rain_time_and_percentage_must_match_the_forecast_exactly():
    good = "Foot traffic is 17% above usual at 1pm, with rain likely from 3pm."
    assert sentence_ok(good, RAINY)
    assert sentence_ok("Foot traffic is 17% above usual, 40% of bays are free, and rain is likely from 3 pm (80% chance).", RAINY)
    assert not sentence_ok("Foot traffic is 17% above usual at 1pm, with rain likely from 4pm.", RAINY)  # wrong time
    assert not sentence_ok("Foot traffic is 17% above usual, with a 70% chance of rain from 3pm.", RAINY)  # wrong %
    assert not sentence_ok("Foot traffic is 17% above usual at 1pm, with rain on the way.", RAINY)  # no start time
    assert not sentence_ok("Foot traffic is 17% above usual and 40% of parking bays are free.", RAINY)  # rain left out
    assert not sentence_ok("Foot traffic is 17% above usual at 1pm, with rain likely from noon.", RAINY)


def test_no_rain_forecast_means_no_weather_in_the_sentence():
    assert sentence_ok("Foot traffic is 17% above usual at 1pm and 40% of parking bays are free.", DRY)
    assert not weather_ok("Foot traffic is 17% above usual at 1pm, with rain likely from 3pm.", DRY)
    assert not weather_ok("Foot traffic is 17% above usual on a dry afternoon.", DRY)
    assert not weather_ok("Foot traffic is 17% above usual at 2pm.", DRY)  # the data is for 1pm


def test_rain_starting_this_hour_reads_as_now():
    stats = build_stats(PEDESTRIAN, SENSORS, PARKING, forecast((90, 2.0)), NOW)
    assert prompt_facts(stats)["rain"] == "rain likely now (up to 90% chance)"
    assert sentence_ok("Foot traffic is 17% above usual at 1pm, and rain is likely now.", stats)
    assert not sentence_ok("Foot traffic is 17% above usual at 1pm, and rain is likely later.", stats)


def test_the_template_carries_the_rain_clause_and_passes_its_own_checks():
    text = template(RAINY)
    assert text == (
        "Melbourne's CBD is 17% busier than a typical Thursday at 1pm, "
        "40% of parking bays are free, and Melbourne Central is busiest, with rain likely from 3pm."
    )
    assert words(text) <= MAX_WORDS and sentence_ok(text, RAINY)
    assert sentence_ok(template(DRY), DRY) and "rain" not in template(DRY)
    # When space runs out, other detail goes first; the rain clause stays.
    long_name = {**RAINY, "busiest": [{"name": "A Very Long Sensor Description That Goes On And On Near Somewhere Else Again", "count": 1}]}
    assert template(long_name).endswith("with rain likely from 3pm.") and words(template(long_name)) <= MAX_WORDS
