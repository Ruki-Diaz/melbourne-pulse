"""What a failed feed does to the hourly run: a yellow warning or a red failure.

One feed failing (the city's API or Open-Meteo erroring, timing out or sending
nothing usable) is routine and heals on the next run, so it is a GitHub warning
annotation and the run stays green. The run goes red only when
  - every feed of a script failed in the same run, or
  - the same feed has now failed STALE_AFTER_RUNS runs in a row (counted in the
    feed_status table), so a warning can never hide a long outage.
A database error is never caught: it ends the script with a traceback, also red.
"""

from __future__ import annotations

from datetime import datetime

from .timeutil import local

STALE_AFTER_RUNS = 3


def annotate(level: str, title: str, message: str) -> None:
    """Print a GitHub Actions annotation (`level` is warning or error). Plain text anywhere else."""
    escaped = message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    print(f"::{level} title={title}::{escaped}", flush=True)


def exit_code(
    failures: dict[str, str],
    streaks: dict[str, tuple[int, datetime | None]],
    *,
    all_failed: bool,
) -> int:
    """Annotate every failed feed and return the script's exit code.

    failures    feed -> why it failed this run
    streaks     feed -> (runs failed in a row including this one, last success), from
                db.record_feed_runs; empty on a dry run, where nothing is counted
    all_failed  every feed the script fetches failed this run
    """
    code = 0
    for feed, reason in failures.items():
        runs, last_ok = streaks.get(feed, (1, None))
        if runs >= STALE_AFTER_RUNS:
            since = f"last success {local(last_ok):%a %d %b %H:%M %Z}" if last_ok else "no success recorded"
            annotate("error", f"Feed stale: {feed}", f"{feed} has failed {runs} runs in a row ({since}). Latest: {reason}")
            code = 1
        else:
            annotate("warning", f"Feed failed: {feed}", f"{feed} failed this run ({runs} in a row): {reason}")
    if all_failed:
        annotate("error", "All feeds failed", f"no feed could be fetched this run: {', '.join(failures)}")
        code = 1
    return code
