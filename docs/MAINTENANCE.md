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
| `feed_quality` | `pipeline/feed_quality.py` (`hourly.yml`) | Hourly | One row per finished hour: the share of sensors under half their typical, and whether the hour is flagged as a feed anomaly. |
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

## The "sensor feed looks unusual" warning

**What it means.** The homepage headline, the stat card and the top of `/map` say *"The city's sensor feed looks unusual right now. Counts may be incomplete."* and show raw counts with no "X% quieter" comparison. The hourly job (`pipeline/feed_quality.py`) has flagged the current hour in the `feed_quality` table because **at least 60% of sensors read under half their typical count at the same time**, on a day that isn't a public holiday, after allowing for heavy rain. Real events don't move most sensors that far at once; a fault in the city's feed does. The rules and their thresholds are in `pipeline/pulse/quality.py`.

While an hour is flagged:
- the summary sentence is the fixed warning (Gemini is not asked);
- the hour is left out of "typical", so it can't drag next week's baseline down;
- the forecast model doesn't use it as history (it falls back to the next valid week), and it is dropped from future training. `predict.py` and `train.py` log how many hours were left out.

The warning clears by itself: once fewer than 25% of sensors are low, the next hourly run stops flagging.

**How to check whether the city fixed the feed.**
1. See what is flagged: `cd pipeline && DATABASE_URL='…' ../.venv/bin/python feed_quality.py --backfill 3 --dry-run --verbose` prints every hour of the last 3 days with the share of low sensors. Nothing is written with `--dry-run`.
2. Compare with the city's own figures: `DATABASE_URL='…' ../.venv/bin/python audit.py`. Its last section sets our hourly totals beside the city's hourly dataset, which is published about a day behind.
   - **"MISMATCH … ours far below city"** for the flagged hours: the live feed was incomplete and the city's final figures are fine. Nothing to do; the hours stay flagged and excluded.
   - **"flagged hours match the city's own hourly figures"**: the low counts are in the city's final data too. Either the sensors really under-counted or the city really was that quiet (for example a severe storm). The flag is then a judgement call; see step 3.
   - **"not in the city's hourly dataset yet"**: too early. Run it again tomorrow.
3. To clear flags you believe are wrong, delete them and let the model use those hours again: `delete from feed_quality where hour >= '2026-10-01 05:00+00' and hour < '2026-10-01 16:00+00';` (times are UTC). To re-assess after changing a threshold, run `feed_quality.py --backfill 14`: it replaces the last 14 days of flags.
4. If the feed stays broken for days, the City of Melbourne Open Data team is the contact: https://data.melbourne.vic.gov.au (the dataset page has a "Contact" link).

## If a key leaks
- **Neon:** Roles → `neondb_owner` → Reset password → update `.env` + GitHub `DATABASE_URL`.
- **Gemini:** AI Studio → API Keys → delete → create new → update `.env` + GitHub `GEMINI_API_KEY`.
- **GitHub token:** https://github.com/settings/personal-access-tokens → Delete → make a new one → update BOTH cron-job.org jobs.
