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
- **Table:** Completely replaces the rows in `rain_effect`.

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
   - Check Vercel cache revalidation: `/api/revalidate` with `secret` clears tag `plan`.
4. **Neon usage** (free: 100 CU-hours/month, 0.5 GB): https://console.neon.tech → project → Usage.

## If a key leaks
- **Neon:** Roles → `neondb_owner` → Reset password → update `.env` + GitHub `DATABASE_URL`.
- **Gemini:** AI Studio → API Keys → delete → create new → update `.env` + GitHub `GEMINI_API_KEY`.
- **GitHub token:** https://github.com/settings/personal-access-tokens → Delete → make a new one → update BOTH cron-job.org jobs.
