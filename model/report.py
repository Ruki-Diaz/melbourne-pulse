"""Write model/metrics.json, model/chart.png and model/REPORT.md from a training run."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import holidays  # noqa: E402
import pandas as pd  # noqa: E402

import data  # noqa: E402,F401  (puts ../pipeline on sys.path)
from pulse import api  # noqa: E402
from pulse.timeutil import MEL  # noqa: E402

NAIVE = "Seasonal naive (same hour last week)"
TYPICAL = "Typical (8-week median, the app's baseline)"
LGBM = "LightGBM"

# Reference categorical slots 1-3 (validated all-pairs, light surface).
INK, INK_2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
COLORS = {"Actual": "#2a78d6", "LightGBM forecast": "#eb6834", "Typical (8-week median)": "#1baf7a"}

FEATURE_NAMES = {
    "sensor": "Which sensor (each location has its own pattern)",
    "hour": "Hour of the day",
    "dow": "Day of the week",
    "month": "Month (season)",
    "public_holiday": "Is it a Victorian public holiday?",
    "lag_1w": "Count at the same hour last week",
    "lag_2w": "Count at the same hour two weeks ago",
    "typical_8w": "Median of the same hour over the last 8 weeks",
    "mean_4w": "Average of the same hour over the last 4 weeks",
    "weeks_available": "How many of the last 8 weeks the sensor was working",
    "day_total_1w": "Sensor's whole-day total on the same day last week",
    "lag_1w_holiday": "Was the same day last week a public holiday?",
    "school_holiday": "Is it a Victorian school holiday?",
    "down_days_4w": "Days the sensor was down in the last 4 weeks",
    "precipitation": "Rain forecast for the hour (mm)",
    "wet": "Is the hour forecast to be wet (0.2 mm or more)?",
    "precip_3h": "Rain forecast for the hour and the two before it",
    "temperature": "Temperature forecast for the hour",
    "wind": "Wind speed forecast for the hour",
}


def write(attempts: list[dict], best: dict, meta: dict, out: Path, decision: dict) -> None:
    keys = ("label", "lead", "columns", "objective", "rounds", "trials", "results", "split", "importance")
    metrics = {
        "model": meta,
        "decision": decision,
        "attempts": [{k: a[k] for k in keys} for a in attempts],
    }
    (out / "metrics.json").write_text(json.dumps(metrics, indent=1) + "\n")
    (out / ".cache").mkdir(exist_ok=True)
    best["test_frame"].to_pickle(out / ".cache" / "test_frame.pkl")
    names = sensor_names()
    sensors, week_start = chart(best["test_frame"], names, out / "chart.png")
    labels = [names.get(s, f"Sensor {s}") for s in sensors]
    (out / "REPORT.md").write_text(markdown(attempts, best, meta, labels, week_start, decision))
    print("wrote metrics.json, chart.png, REPORT.md")


def sensor_names() -> dict[int, str]:
    try:
        rows = api.export(api.SENSOR_LOCATIONS, select="location_id,sensor_description")
        return {int(r["location_id"]): r["sensor_description"] for r in rows}
    except Exception:  # noqa: BLE001 - names are cosmetic
        return {}


def chart(frame: pd.DataFrame, names: dict[int, str], path: Path) -> tuple[list[int], pd.Timestamp]:
    """Actual vs forecast vs typical for the 3 busiest sensors over the last full test week."""
    frame = frame.copy()
    frame["local"] = frame["ts"].dt.tz_convert(MEL)
    mondays = sorted(d for d in frame["date"].unique() if pd.Timestamp(d).dayofweek == 0)
    start = next(m for m in reversed(mondays) if pd.Timestamp(m) + pd.Timedelta(days=6) <= frame["date"].max())
    week = frame[(frame["date"] >= start) & (frame["date"] < start + pd.Timedelta(days=7))]
    sensors = week.groupby("location_id")["count"].sum().nlargest(3).index.tolist()

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10})
    fig, axes = plt.subplots(3, 1, figsize=(11, 8.2), sharex=True, facecolor=SURFACE)
    for ax, lid in zip(axes, sensors):
        s = week[week["location_id"] == lid].sort_values("ts")
        ax.set_facecolor(SURFACE)
        ax.plot(s["local"], s["count"], color=COLORS["Actual"], lw=2, label="Actual")
        ax.plot(s["local"], s["lightgbm"], color=COLORS["LightGBM forecast"], lw=2, label="LightGBM forecast")
        ax.plot(s["local"], s["typical"], color=COLORS["Typical (8-week median)"], lw=2, ls=(0, (4, 2)),
                label="Typical (8-week median)")
        ax.set_title(names.get(lid, f"Sensor {lid}"), loc="left", color=INK, fontsize=11, fontweight="bold")
        ax.grid(axis="y", color=GRID, lw=0.8)
        ax.set_axisbelow(True)
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
        ax.spines["bottom"].set_color(GRID)
        ax.tick_params(colors=INK_2, length=0)
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
        ax.set_ylim(bottom=0)
        ax.set_ylabel("People per hour", color=INK_2)
    axes[-1].xaxis.set_major_locator(mdates.DayLocator(tz=MEL))
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%a %d %b", tz=MEL))
    fig.legend(*axes[0].get_legend_handles_labels(), loc="upper right", ncol=3, frameon=False,
               labelcolor=INK, bbox_to_anchor=(0.98, 0.995))
    fig.suptitle(f"One test week the model never saw ({pd.Timestamp(start):%d %b %Y})",
                 x=0.015, y=0.99, ha="left", color=INK, fontsize=12, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(path, dpi=110, facecolor=SURFACE)
    plt.close(fig)
    return sensors, pd.Timestamp(start)


def pct(a: float, b: float) -> str:
    return f"{(1 - a / b) * 100:.0f}%"


def week_note(start: pd.Timestamp) -> str:
    """Name any Victorian public holiday in the chart week (they explain the misses)."""
    days = holidays.country_holidays("AU", subdiv="VIC", years=sorted({start.year, (start + pd.Timedelta(days=6)).year}))
    found = [(d, n) for d, n in sorted(days.items()) if start.date() <= d <= (start + pd.Timedelta(days=6)).date()]
    if not found:
        return ""
    listed = " and ".join(f"{n} ({d:%a %d %b})" for d, n in found)
    return (
        f" This week includes a public holiday: {listed}. The model knows the day is a holiday, "
        "but most holidays make the CBD quieter, so it can't know when an event (like a parade or "
        "a big match) makes it busier or pulls people elsewhere. That is where the biggest misses are."
    )


def weather_section(attempts: list[dict], decision: dict) -> str:
    """The "Does weather help?" section: one table, the decision, and why."""
    by_label = {a["label"]: a for a in attempts}
    control = by_label[decision["control"]]
    latest, day1 = (by_label[label] for label in decision["candidates"])
    c, fresh, old = (a["results"][LGBM] for a in (control, latest, day1))
    typ = control["results"][TYPICAL]

    def row(name: str, r: dict) -> str:
        return f"| {name} | {r['mae']:.1f} | {r['wet_mae']:.1f} |"

    table = "\n".join(
        [
            row("Typical (8-week median)", typ),
            row("BASE: LightGBM without weather", c),
            row("BASE + WEATHER, forecast issued just before the hour", fresh),
            row("BASE + WEATHER, forecast issued 24 h before the hour", old),
        ]
    )
    wet_hours, caught = decision["test_wet_hours"], decision["test_wet_hours_also_wet_day1"]
    missed = (
        f"of the {wet_hours} wet hours in the test weeks, the forecast made a day earlier "
        f"called only {caught} wet"
    )
    if decision["ship_weather"]:
        verdict = (
            f"**Decision: ship BASE + WEATHER.** It beats BASE on overall test error with both sets of "
            f"forecasts ({fresh['mae']:.1f} and {old['mae']:.1f} against {c['mae']:.1f}). The shipped model is "
            "the one trained on day-old forecasts, so the daily job never relies on forecasts fresher than "
            "it was tested with."
        )
        why = (
            f"Why: rain does thin the crowds and the model picks that up, but the gain is limited by the "
            f"weather forecast itself: {missed}."
        )
    elif fresh["mae"] < c["mae"]:
        verdict = (
            f"**Decision: keep BASE; weather is not shipped.** Weather wins only with forecasts issued just "
            f"before each hour ({fresh['mae']:.1f} against {c['mae']:.1f}). With forecasts issued a day "
            f"earlier it scores {old['mae']:.1f}, no better than BASE, and the daily job's forecasts are "
            "up to a day old for the hours the site shows."
        )
        why = (
            f"Why: rain does thin the crowds, but the model can only use it if the rain is forecast, and "
            f"{missed}."
        )
    else:
        verdict = (
            f"**Decision: keep BASE; weather is not shipped.** BASE + WEATHER does not beat BASE on overall "
            f"test error ({fresh['mae']:.1f} with the freshest forecasts and {old['mae']:.1f} with day-old "
            f"ones, against {c['mae']:.1f})."
        )
        why = (
            f"Why: only {wet_hours} of the {decision['test_hours']:,} test hours were wet, so rain moves the "
            f"overall average very little, and the forecasts are too unreliable to make up for it: {missed}."
        )

    return f"""## Does weather help?

A separate study of the same sensors (*Rain or Shine*, 2025) found about 18%
fewer pedestrians in a wet hour and about 30% fewer in heavy rain. So the
model was given the weather **forecast** for each hour (rain, rain over the
last three hours, a wet/dry flag, temperature and wind, from Open-Meteo) and
retrained with the same settings, the same split and the same test hours.

| Method | All test hours (MAE) | Wet test hours only (MAE) |
|---|---:|---:|
{table}

*"BASE" is the best model without weather ({decision['control']} in the
Attempts table). Wet hours are the {control['split']['wet_rows_scored']:,}
test sensor-hours ({wet_hours} of {decision['test_hours']:,} hours) where the
freshest forecast had at least 0.2 mm of rain.*

{verdict}

{why}

The two weather rows differ only in how old the forecast is. Observed weather
was never used, because the model won't have it when it runs. Open-Meteo's
Historical Forecast API joins up the first few hours of every past forecast
run, so its values were issued just before the hour they describe. The daily
job runs only once a day, at about 4am, and the site shows each of its
predictions for up to 24 hours, so the weather forecast behind a prediction
can be up to a day old. The last row uses the forecast issued 24 hours before
each hour (Open-Meteo's Previous Runs API), which is as old as it gets. A
model that only won on the fresher row would look better in this test than it
would be on the site.
"""


def markdown(attempts: list[dict], best: dict, meta: dict, chart_sensors: list[str], week_start: pd.Timestamp,
             decision: dict) -> str:
    r, split = best["results"], best["split"]
    lgbm, typ, naive = r[LGBM], r[TYPICAL], r[NAIVE]
    beat = lgbm["mae"] < typ["mae"]

    rows = "\n".join(
        f"| {name} | {r[name]['mae']:.1f} | {r[name]['mape']:.1f}% |" for name in (NAIVE, TYPICAL, LGBM)
    )
    tries = "\n".join(
        f"| {a['label']} ({len(a['columns'])} features) | {a['results'][TYPICAL]['mae']:.1f} | "
        f"{a['results'][LGBM]['mae']:.1f} | {a['objective']}, {a['rounds']} trees |"
        for a in attempts
    )
    by_hour = "\n".join(
        f"| {h:02d}:00 | {naive['by_hour'][h]['mae']:.0f} | {typ['by_hour'][h]['mae']:.0f} | "
        f"{lgbm['by_hour'][h]['mae']:.0f} | {naive['by_hour'][h]['mape']:.0f}% | "
        f"{typ['by_hour'][h]['mape']:.0f}% | {lgbm['by_hour'][h]['mape']:.0f}% |"
        for h in range(24)
    )
    total_gain = sum(best["importance"].values())
    top = sorted(best["importance"].items(), key=lambda kv: kv[1], reverse=True)
    features = "\n".join(
        f"| {i} | {FEATURE_NAMES.get(k, k)} | {v / total_gain * 100:.0f}% |" for i, (k, v) in enumerate(top[:8], 1)
    )
    daytime = [h for h in range(7, 20)]
    day_gain = sum(1 for h in daytime if lgbm["by_hour"][h]["mae"] < typ["by_hour"][h]["mae"])
    biggest = max(range(24), key=lambda h: typ["by_hour"][h]["mae"] - lgbm["by_hour"][h]["mae"])
    sensors_text = ", ".join(f"**{s}**" for s in chart_sensors[:-1]) + f" and **{chart_sensors[-1]}**"

    verdict = (
        f"**LightGBM beats the app's own baseline.** Its average error is **{lgbm['mae']:.1f} people per hour**, "
        f"against {typ['mae']:.1f} for the 8-week typical ({pct(lgbm['mae'], typ['mae'])} lower) and "
        f"{naive['mae']:.1f} for \"same as last week\" ({pct(lgbm['mae'], naive['mae'])} lower). "
        f"It is more accurate than typical in {'every one' if day_gain == len(daytime) else day_gain} of the "
        f"{len(daytime)} daytime hours (7am to 8pm), "
        f"with the biggest gain at {biggest:02d}:00 ({typ['by_hour'][biggest]['mae']:.0f} down to "
        f"{lgbm['by_hour'][biggest]['mae']:.0f} people)."
        if beat
        else f"**LightGBM does not beat the app's own baseline.** Its average error is {lgbm['mae']:.1f} people "
        f"per hour, against {typ['mae']:.1f} for the 8-week typical. The forecast adds nothing over the typical "
        "line, so the site should show typical only."
    )

    weather_limit = (
        """- Weather comes from a free forecast service (Open-Meteo). If it can't be
  reached, that day's run uses the model without weather (`model_base.txt.gz`),
  so those forecasts are as accurate as BASE, not better.
"""
        if decision["ship_weather"]
        else ""
    )

    return f"""# Forecast model report

*Generated by `model/train.py` on {meta['trained_at'][:10]}. Numbers come from `metrics.json`.*

## The question

Melbourne Pulse shows how busy each pedestrian sensor is compared with a
**typical** level: the median count for the same hour and weekday over the last
8 weeks. Can a machine-learning model predict the **next 24 hours** better than
that simple rule? If it can't, a forecast adds nothing and shouldn't be on the
site.

## The answer

{verdict}

| Method (test set: {split['test'][0]} to {split['test'][1]}) | Average error (MAE, people/hour) | Average % error (MAPE) |
|---|---:|---:|
{rows}

*Lower is better. MAE is the average gap between the prediction and the real
count. MAPE is the same gap as a percentage of the real count; it only counts
hours with at least 10 people, because a percentage of almost zero is
meaningless.*

![Actual vs forecast vs typical for three sensors over one test week](chart.png)

The chart shows the three busiest sensors ({sensors_text}) over one week of
the test period. The model never saw these weeks during training.{week_note(week_start)}

{weather_section(attempts, decision)}
## How it was tested fairly

- **Data:** two years of hourly counts from {split['sensors']} City of Melbourne
  sensors (the *Pedestrian Counting System, monthly counts per hour* dataset,
  CC BY). Hours with nobody walking past aren't published, so they were
  filled in as 0. Days when a sensor sent nothing at all were treated as
  *sensor down*, not as a quiet day.
- **Split by time, never shuffled.** The model learned from
  {split['train'][0]} to {split['train'][1]}. The next 8 weeks
  ({split['validation'][0]} to {split['validation'][1]}) were used to pick
  settings, and the final 8 weeks were used **once** for the scores above.
- **No peeking at the future.** The site shows forecasts up to 36 hours
  ahead, so the model may only use information that exists well before the
  hour it predicts. Every history-based input looks back at least a full week,
  for example "same hour last week". An automated test deletes the most recent
  7 days of data and checks that no input changes. Weather inputs are
  forecasts, never observed weather (see "Does weather help?").
- **Same questions for everyone.** All three methods were scored on the same
  {split['test_rows_scored']:,} sensor-hours, the ones where every method
  could make a prediction.
- **Daylight saving handled.** "Same hour last week" means the same *local*
  hour, so 9am is compared with 9am when the clocks change.

## What the model pays attention to

| # | Input | Share of the model's learning (gain) |
|---|---|---:|
{features}

## Attempts

| Feature set | Typical MAE | LightGBM MAE | Settings (chosen on validation) |
|---|---:|---:|---|
{tries}

"Extra" adds Victorian **school holidays** and a **sensor-was-down** count.
"Weather" adds the five weather-forecast inputs described above.
The loss function and the number of trees were chosen on the validation weeks
only. Tree count was capped at 1,500 to keep the model file small; the l1 runs
stopped at or near that cap, so a larger model might gain a little more.

## Error by hour of day (test set)

<details>
<summary>Show the 24-hour table</summary>

| Hour | Naive MAE | Typical MAE | LightGBM MAE | Naive MAPE | Typical MAPE | LightGBM MAPE |
|---|---:|---:|---:|---:|---:|---:|
{by_hour}

</details>

## Limits

- The model knows about holidays but not one-off events such as concerts,
  protests or big sports days, so those hours will be off.
- A sensor that has just been installed or repaired has little history, so
  its forecast leans on the general pattern for that hour and day.
{weather_limit}- The shipped model was retrained on all the data using the settings chosen
  above. It is {meta['size_bytes'] / 1e6:.1f} MB (`model.txt.gz`) and is rebuilt
  by running `python model/train.py`.
"""


def main() -> int:
    """Re-render the report from the last training run without retraining."""
    import pickle

    here = Path(__file__).parent
    saved = json.loads((here / "metrics.json").read_text())
    attempts = saved["attempts"]
    best = next(a for a in attempts if a["label"] == saved["decision"]["shipped"])
    best["results"] = {k: {**v, "by_hour": {int(h): m for h, m in v["by_hour"].items()}} for k, v in best["results"].items()}
    with open(here / ".cache" / "test_frame.pkl", "rb") as f:
        best["test_frame"] = pickle.load(f)
    write(attempts, best, json.loads((here / "model_meta.json").read_text()), here, saved["decision"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
