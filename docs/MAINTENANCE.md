# Melbourne Pulse — Maintenance

Live site: https://melbourne-pulse-au.vercel.app
Repo: https://github.com/Ruki-Diaz/melbourne-pulse

No secrets are stored in this file. Keys live only in `.env` (local), GitHub Secrets, Vercel, and cron-job.org.

## Yearly: renew the GitHub token for cron-job.org

**Reminder:** Fri 24 Sep 2027, 9:00am — "Renew Melbourne Pulse GitHub token (expires 1 Oct). 10 min job." Then every year on 24 Sep.

### 1. Make the new token (3 min)
1. Go to https://github.com/settings/personal-access-tokens
2. Click **cron-job.org melbourne-pulse**.
3. Click **Regenerate token** (keeps the same repo + permission).
4. New expiry: **Custom** → one year ahead (1 Oct of next year).
5. Click **Regenerate token**, then copy the new `github_pat_...` with the copy icon.

The token should only have: repository `Ruki-Diaz/melbourne-pulse`, Actions **Read and write**, Metadata read-only (automatic).

### 2. Put it into cron-job.org (3 min)
Update **BOTH** cron jobs in https://console.cron-job.org:
1. **Melbourne Pulse hourly** → **Advanced** tab:
   - **Authorization** header → `Bearer ` + new token (exactly one space after Bearer).
   - **X-GitHub-Api-Version** → `2022-11-28` (or newer if updated).
2. **Melbourne Pulse daily forecast** → **Advanced** tab:
   - **Authorization** header → `Bearer ` + new token (same token).
   - **X-GitHub-Api-Version** → `2022-11-28` (or newer if updated).

### 3. Test (2 min)
1. In both jobs, click **Test run** → want **204**. 401 = token pasted wrong. 403/404 = token missing the repo or Actions permission.
2. **Save** both jobs.
3. Check https://github.com/Ruki-Diaz/melbourne-pulse/actions to verify workflow dispatches trigger cleanly.

### 4. Set next year's reminder (24 Sep).

If you forget: cron-job.org emails on 1 Oct that the job failed. The site shows its last data (amber "Last updated X h ago") until you renew.

## Yearly: review the GitHub Actions versions

Do this with the token renewal (24 Sep). All four workflows in `.github/workflows/` pin two things that GitHub retires on its own schedule:

- **Runner image:** `runs-on: ubuntu-24.04`. A fixed image, not `ubuntu-latest`, so a new Ubuntu can't change the jobs unannounced. Check https://github.com/actions/runner-images for the newest LTS image and whether 24.04 has a retirement date; move every workflow together.
- **Actions:** `actions/checkout@v7`, `actions/setup-python@v7`, `actions/setup-node@v7` (all run on Node 24; set on 2 Oct 2026). Check each action's releases page for a newer major and for deprecation warnings on recent runs in the Actions tab ("Node.js XX actions are deprecated").

After changing either, start `ci` (push), then run `hourly`, `daily-forecast` and `monthly-rain-effect` once from the Actions tab and confirm all are green.

## cron-job.org settings (to rebuild from scratch)

### Job 1: Melbourne Pulse hourly

| Field | Value |
|---|---|
| Title | Melbourne Pulse hourly |
| URL | `https://api.github.com/repos/Ruki-Diaz/melbourne-pulse/actions/workflows/hourly.yml/dispatches` |
| Schedule | Custom → minute 7 every hour (`7 * * * *`), Australia/Melbourne |
| Method | POST |
| Body | `{"ref":"main"}` |
| Headers | `Authorization: Bearer github_pat_...` · `Accept: application/vnd.github+json` · `X-GitHub-Api-Version: 2022-11-28` · `Content-Type: application/json` |
| Notifications | On: execution fails |

GitHub's own schedule (:17) is a backup and stands down if cron-job.org already ran.

### Job 2: Melbourne Pulse daily forecast

| Field | Value |
|---|---|
| Title | Melbourne Pulse daily forecast |
| URL | `https://api.github.com/repos/Ruki-Diaz/melbourne-pulse/actions/workflows/daily-forecast.yml/dispatches` |
| Schedule | Custom → 04:37 every day (`37 4 * * *`), Australia/Melbourne |
| Method | POST |
| Body | `{"ref":"main"}` |
| Headers | `Authorization: Bearer github_pat_...` · `Accept: application/vnd.github+json` · `X-GitHub-Api-Version: 2022-11-28` · `Content-Type: application/json` |
| Notifications | On: execution fails |

GitHub's own schedule (`37 17 * * *` UTC = 03:37 AEST / 04:37 AEDT) is a fallback.

## Monthly workflow: `monthly-rain-effect`

- **Trigger:** Automatic GitHub Actions schedule on the 1st of each month at 17:13 UTC (`13 17 1 * *` = 03:13 AEST / 04:13 AEDT on the 2nd), or manual run via `workflow_dispatch`.
- **Purpose:** Executes `pipeline/rain_effect.py` to re-estimate how rain changes foot traffic over the previous 12 months using matched wet vs dry hour comparisons.
- **Table:** Replaces every row in `rain_effect` in one transaction, so a run that fails part-way leaves the previous month's rows in place.
- **Never overlaps the hourly job:** it shares the `hourly` concurrency group. If it is ever cancelled while waiting, start it again from the Actions tab.

## Database Tables & Cadence

| Table | Written by | Cadence | Purpose |
|---|---|---|---|
| `latest` | `pipeline/fetch.py`, `summary.py` | Hourly | Live parking, pedestrian counts, sensor metadata, and Gemini AI summary. |
| `pedestrian_hourly` | `pipeline/fetch.py` | Hourly | Sensor-level hourly history (kept 90 days). |
| `parking_hourly` | `pipeline/fetch.py` | Hourly | CBD-wide parking utilization history. |
| `forecasts` | `model/predict.py` (`daily-forecast.yml`) | Daily (04:37 local) | 24-hour ahead pedestrian count predictions per sensor. |
| `weather_forecast` | `pipeline/weather_forecast.py` (`hourly.yml`) | Hourly | CBD precipitation, rain probability, temp, wind, and WMO code from Open-Meteo. |
| `feed_quality` | `pipeline/feed_quality.py` (`hourly.yml`); `pipeline/audit.py --resolve` (`daily-forecast.yml`) | Hourly; resolved daily | One row per finished hour: the share of sensors under half their typical, whether the hour is flagged, and what the city's figures later said (`resolution`). |
| `rain_effect` | `pipeline/rain_effect.py` (`monthly-rain-effect.yml`) | Monthly | 12-month matched wet-vs-dry impact statistics across overall, intensity, daytype, temperature, and sensor breakdowns. |

## Where everything is set

| What | Where |
|---|---|
| `DATABASE_URL` | GitHub → Settings → Secrets → Actions (Neon owner, pooled) |
| `GEMINI_API_KEY` | GitHub → Settings → Secrets → Actions |
| `REVALIDATE_SECRET` | GitHub Secrets **and** Vercel env vars (must match) |
| `SITE_URL` | GitHub → Settings → **Variables** → Actions = `https://melbourne-pulse-au.vercel.app` |
| `DATABASE_URL_READONLY` | Vercel env vars (Neon web_reader, pooled) |
| `NEXT_PUBLIC_SITE_URL` | Vercel env vars = `https://melbourne-pulse-au.vercel.app` (redeploy after changing) |

## Quick health check

1. **Live site badge** "Live · updated X min ago" (under 2 h) → all good.
2. **Amber "Last updated X h ago"** → check https://github.com/Ruki-Diaz/melbourne-pulse/actions. Red run → copy the error. No recent runs → check cron-job.org (token expired? job disabled?).
3. **If `/plan` looks stale:**
   - Check `daily-forecast.yml` runs in GitHub Actions (should have run today at 04:37 Melbourne time).
   - Check `hourly.yml` runs in GitHub Actions (should run hourly to pull Open-Meteo weather into `weather_forecast` and revalidate Vercel cache).
   - Check Neon tables directly:
     - `forecasts`: check `max(generated_at)` (should be within the last 24h).
     - `weather_forecast`: check `max(fetched_at)` (should be within the last 1-2h).
     - `rain_effect`: check `max(computed_at)` (should be within the last 35 days).
   - `/api/plan` shows what the site last read: `dataFreshness` has each table's newest write and `snapshotAt`, the time of the read. If the tables are newer than `snapshotAt` by more than an hour, the hourly job's "Revalidate website" step isn't getting through (check `SITE_URL` and `REVALIDATE_SECRET`).
4. **If a number on the homepage looks wrong:** run `cd pipeline && DATABASE_URL='…' ../.venv/bin/python audit.py`. It recomputes the pedestrian count total, the % against typical, the % of parking bays free and the busiest sensor straight from the City of Melbourne API and prints them beside the database and the live page. All four should say "yes". If they match but the counts still look implausibly low, the city's live feed itself may be short: compare with the city's hourly dataset a day later (it is published about a day behind).
5. **Neon usage** (free: 100 CU-hours/month, 0.5 GB): https://console.neon.tech → project → Usage.

## The "far below normal" notice

**What it means.** The homepage headline, the stat card and the top of `/map` say *"Foot traffic is far below normal across most sensors. This may be severe weather, a major event, or a sensor feed issue."* They show raw counts with no "X% quieter" comparison, and each sensor reads "Comparison paused". The hourly job (`pipeline/feed_quality.py`) has flagged the current hour in the `feed_quality` table because **at least 60% of sensors read under half their typical count at the same time**, on a day that isn't a public holiday, after allowing for heavy rain. In the moment nobody can tell a storm or a big event from a fault in the city's feed, so the notice doesn't pick one. The rules and their thresholds are in `pipeline/pulse/quality.py`.

While an hour is flagged and not yet resolved:
- the summary sentence is the fixed notice (Gemini is not asked);
- the hour is left out of the site's "typical", so it can't drag next week's baseline down;
- the forecast model doesn't use it as history (it falls back to the next valid week), and it is dropped from training and from the rain effect. `predict.py`, `train.py` and `rain_effect.py` log how many hours were left out.

The notice clears by itself: once fewer than 25% of sensors are low, the next hourly run stops flagging.

**How it gets settled.** The city publishes its own hourly totals about a day later. Each morning, before the forecast, the `daily-forecast` workflow runs `pipeline/audit.py --resolve`, which compares every flagged hour with those totals and writes the outcome to `feed_quality.resolution`:

| Resolution | When | What happens |
|---|---|---|
| `confirmed_real` | our total is within 5% of the city's | The hour is unflagged (`anomaly = false`) and is normal data again everywhere. A real storm is exactly the heavy-rain evidence the rain effect needs. |
| `confirmed_fault` | our total is more than 5% below the city's | The live feed was incomplete. On the **site** the hour stays flagged (`anomaly = true`): our live table holds the short counts, so it is kept out of "typical". The **model and the rain effect** use the hour again, because they read the city's final figures, which are correct. |
| *(empty)* | not published yet, ours is above the city's, or the hour was seeded | Nothing changes: the hour stays flagged and excluded everywhere. Unpublished hours are tried again the next day. |

Who leaves out what:

| | Unresolved flag | `confirmed_fault` | `confirmed_real` |
|---|---|---|---|
| Site: notice, "typical", comparisons (our live table) | left out | left out | used |
| Forecast model: training and lag/typical history (city's figures) | left out | used | used |
| Rain effect (city's figures) | left out | used | used |

A resolution is final: neither the hourly check nor a `--backfill` re-assesses a resolved hour.

**Seeded hours are never resolved automatically.** Everything in `pedestrian_hourly` before Wed 30 Sep 2026, 3pm (`LIVE_FEED_SINCE` in `pipeline/audit.py`) was copied from the city's hourly dataset by `seed_history.py`, so comparing it with that dataset would always "agree". A flag on such an hour (the two Grand Final Saturday hours, 26 Sep 12pm and 1pm, are the only ones) stays flagged and excluded until you remove it by hand with the SQL in step 3 below. If the database is ever rebuilt and re-seeded, move `LIVE_FEED_SINCE` to the first hour the hourly job wrote.

**How to check by hand.**
1. See what is flagged: `cd pipeline && DATABASE_URL='…' ../.venv/bin/python feed_quality.py --backfill 3 --dry-run --verbose` prints every hour of the last 3 days with the share of low sensors. Nothing is written with `--dry-run`.
2. Compare with the city's own figures: `DATABASE_URL='…' ../.venv/bin/python audit.py`. Run like this it writes nothing; its first section says what the daily run will decide for each flagged hour ("really that quiet, to be unflagged", "the live feed was incomplete, to stay flagged", or "not in the city's hourly dataset yet"). Add `--resolve` to record those outcomes now instead of waiting for the morning run.
3. To overrule a flag or a resolution by hand, delete the rows and let the model use those hours again: `delete from feed_quality where hour >= '2026-10-01 05:00+00' and hour < '2026-10-01 16:00+00';` (times are UTC). To re-assess after changing a threshold, run `feed_quality.py --backfill 14`: it replaces the last 14 days of flags.
4. If the feed stays broken for days, the City of Melbourne Open Data team is the contact: https://data.melbourne.vic.gov.au (the dataset page has a "Contact" link).

## If a key leaks
- **Neon:** Roles → `neondb_owner` → Reset password → update `.env` + GitHub `DATABASE_URL`.
- **Gemini:** AI Studio → API Keys → delete → create new → update `.env` + GitHub `GEMINI_API_KEY`.
- **GitHub token:** https://github.com/settings/personal-access-tokens → Delete → make a new one → update BOTH cron-job.org jobs.
