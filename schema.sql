-- Run once in Supabase: SQL Editor -> New query -> paste -> Run.

-- Short-term raw history (trimmed by fetch.py after RETENTION_DAYS).
create table if not exists snapshots (
  id           bigserial primary key,
  source       text        not null,          -- 'parking' | 'pedestrian'
  fetched_at   timestamptz not null default now(),
  record_count integer     not null,
  payload      jsonb       not null
);
create index if not exists snapshots_source_time
  on snapshots (source, fetched_at desc);

-- One row per source: what the live map reads.
create table if not exists latest (
  source       text primary key,
  fetched_at   timestamptz not null,
  record_count integer     not null,
  payload      jsonb       not null
);

-- Security: the website (anon key) may READ `latest` only.
-- fetch.py connects as the database owner, so it bypasses these rules.
alter table snapshots enable row level security;
alter table latest    enable row level security;

drop policy if exists "public read latest" on latest;
create policy "public read latest" on latest for select using (true);
