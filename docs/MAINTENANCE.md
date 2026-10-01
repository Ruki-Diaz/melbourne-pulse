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

## If a key leaks
- **Neon:** Roles → `neondb_owner` → Reset password → update `.env` + GitHub `DATABASE_URL`.
- **Gemini:** AI Studio → API Keys → delete → create new → update `.env` + GitHub `GEMINI_API_KEY`.
- **GitHub token:** https://github.com/settings/personal-access-tokens → Delete → make a new one → update BOTH cron-job.org jobs.
