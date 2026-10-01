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
1. https://console.cron-job.org → **Melbourne Pulse hourly** → **Advanced** tab.
2. **Authorization** header → `Bearer ` + new token (exactly one space after Bearer).
3. **X-GitHub-Api-Version** → check https://docs.github.com/en/rest/about-the-rest-api/api-versions and use the newest if newer than `2022-11-28` (that version stops working March 2028).

### 3. Test (2 min)
1. **Test run** → want **204**. 401 = token pasted wrong. 403/404 = token missing the repo or Actions permission.
2. **Save**.
3. https://github.com/Ruki-Diaz/melbourne-pulse/actions → a new **hourly** run turns green.

### 4. Set next year's reminder (24 Sep).

If you forget: cron-job.org emails on 1 Oct that the job failed. The site shows its last data (amber "Last updated X h ago") until you renew.

## cron-job.org settings (to rebuild from scratch)

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
1. Live site badge "Live · updated X min ago" (under 2 h) → all good.
2. Amber "Last updated X h ago" → check https://github.com/Ruki-Diaz/melbourne-pulse/actions. Red run → copy the error to Claude Code. No recent runs → check cron-job.org (token expired? job disabled?).
3. Neon usage (free: 100 CU-hours/month, 0.5 GB): https://console.neon.tech → project → Usage.

## If a key leaks
- **Neon:** Roles → `neondb_owner` → Reset password → update `.env` + GitHub `DATABASE_URL`.
- **Gemini:** AI Studio → API Keys → delete → create new → update `.env` + GitHub `GEMINI_API_KEY`.
- **GitHub token:** https://github.com/settings/personal-access-tokens → Delete → make a new one → update cron-job.org.
