# Melbourne Pulse

Live map of how busy Melbourne's CBD is: pedestrian counts, free parking bays, and ML forecasts.
Built on City of Melbourne Open Data. Runs entirely on free tiers.

## Setup (about 15 minutes)

1. **Database:** Create a free project at supabase.com. Open SQL Editor, paste `schema.sql`, and click Run.
2. **Connection string:** In Supabase, go to Connect → Session pooler and copy the URI (it includes your DB password).
3. **Repo:** Push this folder to a **public** GitHub repo (Actions minutes are free and unlimited on public repos).
4. **Secret:** In the repo, go to Settings → Secrets and variables → Actions → New secret. Name it `DATABASE_URL` and paste the URI.
5. **Test:** Go to Actions → fetch-data → Run workflow. It should go green and show `saved N records` for both sources.
6. From then on it runs every hour by itself.

## Run locally

```bash
pip install -r requirements.txt
python fetch.py --dry-run          # no database: prints record counts and field names
DATABASE_URL="postgresql://..." python fetch.py
```

## How it works

- `fetch.py` downloads both datasets and stores the raw JSON in `snapshots` (3 days of history) and `latest` (one row per source).
- Old snapshots are deleted every run, so the free 500 MB database never fills up.
- The website only ever reads `latest`. Row-level security blocks public access to everything else.
- If a feed fails or returns 0 rows, the run turns red in GitHub Actions so you notice.
