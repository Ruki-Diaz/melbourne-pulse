import pytest

from summary import (
    MAX_WORDS, PROMPT, build_stats, clean_sentence, percentages_ok, prompt_facts, template, words, wording_ok,
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
    assert clean_sentence("word " * 26) is None
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
