# Scheduling the hourly job

GitHub's built-in `schedule:` trigger is best-effort: on busy hours it starts
runs late or skips them. On launch day it ran **2 of 10** hourly slots, each
about 50 minutes late. So the hourly workflow is started by a free external
cron service, [cron-job.org](https://cron-job.org), and GitHub's schedule is
kept only as a backup.

How the pieces fit:

- **cron-job.org** sends one HTTPS request at :07 every hour to GitHub's API,
  which starts the `hourly` workflow (a `workflow_dispatch` event).
- **GitHub's schedule** (`:17`) still fires. Its first job asks GitHub whether
  a dispatched run succeeded in the last 55 minutes; if so, it stops there,
  without touching the database.
- **Only one run at a time.** The workflow's `concurrency: hourly` group makes a
  second run wait until the first finishes; it is never cancelled mid-write.
  Every write is an upsert, so a repeated run changes nothing.
- **Missed hours heal themselves.** Each run re-reads the last 24 hours, so if
  a trigger is skipped, the next run fills the gap.

## 1. Create a fine-grained GitHub token (this repo only, Actions only)

1. On GitHub, click your profile picture (top right) → **Settings**.
2. Left sidebar, at the bottom: **Developer settings** → **Personal access
   tokens** → **Fine-grained tokens** → **Generate new token**.
3. Fill in:
   - **Token name:** `cron-job.org melbourne-pulse`
   - **Expiration:** the longest offered (e.g. 1 year). Put a reminder in
     your calendar a week before it expires.
   - **Resource owner:** `Ruki-Diaz`
   - **Repository access:** **Only select repositories** → `melbourne-pulse`
4. **Permissions** → **Repository permissions** → **Actions** → set to
   **Read and write**. Leave everything else as **No access**.
   GitHub automatically adds **Metadata: Read-only**. Every token has it and
   it can't be removed; it only lets the token see the repo exists.
5. Click **Generate token** and **copy it now**. It starts with
   `github_pat_` and GitHub won't show it again.

**Where to keep it:** only in two places: the cron-job.org job (step 3 below)
and your password manager. Never in this repo, `.env`, or a GitHub secret
(the workflow doesn't need it).

## 2. Test the token from your terminal

```bash
curl -i -X POST \
  -H "Authorization: Bearer github_pat_YOUR_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  https://api.github.com/repos/Ruki-Diaz/melbourne-pulse/actions/workflows/hourly.yml/dispatches \
  -d '{"ref":"main"}'
```

You want `HTTP/2 204` (no body). Then open the repo's **Actions** tab: a new
`hourly` run should appear within a few seconds. A `401` means the token was
copied wrong; `403` or `404` means the permission or repository selection is
wrong.

## 3. Create the cron job

1. Sign up at [console.cron-job.org/signup](https://console.cron-job.org/signup)
   (free, no card) and confirm your email.
2. Click **Create cronjob**.
3. **Common** tab:
   - **Title:** `Melbourne Pulse hourly`
   - **URL:**
     `https://api.github.com/repos/Ruki-Diaz/melbourne-pulse/actions/workflows/hourly.yml/dispatches`
   - **Enable job:** on
   - **Execution schedule:** choose **Custom**, then set *Minutes* to `7`
     and *Hours*, *Days of month*, *Days of week* and *Months* to **every**.
     That's "at minute 7 of every hour".
   - **Notify me when:** tick *execution of the cronjob fails*, so you get an
     email if GitHub starts rejecting the token (e.g. after it expires).
4. **Advanced** tab:
   - **Request method:** `POST`
   - **Request body:** `{"ref":"main"}`
   - **Headers:** add these three (*key* / *value*):
     | Key | Value |
     |---|---|
     | `Authorization` | `Bearer github_pat_YOUR_TOKEN` |
     | `Accept` | `application/vnd.github+json` |
     | `X-GitHub-Api-Version` | `2022-11-28` |
5. Click **Create** (or **Save**). Use **Test run** if it's offered. A
   successful run shows status **204** and a new run in GitHub's **Actions** tab.

## Checking it's working

- cron-job.org → **History** for the job: one 204 every hour.
- GitHub → **Actions → hourly**: runs labelled *workflow_dispatch* at about
  :07. Runs labelled *schedule* at about :17 should finish in a few seconds with
  the `ingest` job **skipped**. That's the backup standing down.
- The site's badge reads **Live** while data is under 2 hours old.

## When the token expires

cron-job.org will email you that executions are failing (401). Create a new
token (step 1), test it (step 2), and replace the `Authorization` header value
in the cron job. Until then, GitHub's backup schedule keeps running, just less
reliably.
