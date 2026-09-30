import pytest

from summary import MAX_WORDS, build_stats, clean_sentence, template, words

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
