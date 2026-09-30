-- Melbourne Pulse schema (Neon Postgres). Idempotent: safe to re-run.
-- Run in Neon: SQL Editor -> paste -> Run. Then set web_reader's password (bottom).
--
-- Only hourly aggregates are stored (no raw snapshots), so the database stays
-- a few tens of MB. See README "Free-tier budget".

-- One row per source. The website's live view reads this.
--   parking    [{kerbsideid, lat, lon, free, stale}]
--   pedestrian {hour, sensors: [{location_id, count, typical}]}  (latest complete hour)
--   sensors    [{location_id, name, lat, lon, indoor}]
--   summary    {text, source, hour, stats}
create table if not exists latest (
  source     text primary key
             check (source in ('parking', 'pedestrian', 'sensors', 'summary')),
  updated_at timestamptz not null default now(),
  payload    jsonb       not null
);

-- Pedestrians per sensor per hour. `hour` is the UTC instant a Melbourne local
-- hour starts. is_partial marks the hour still filling up; it is excluded from
-- 'typical' and from model training. Kept 90 days (pipeline/pulse/db.py).
create table if not exists pedestrian_hourly (
  location_id integer     not null,
  hour        timestamptz not null,
  count       integer     not null check (count >= 0),
  is_partial  boolean     not null default false,
  primary key (location_id, hour)
);
create index if not exists pedestrian_hourly_hour on pedestrian_hourly (hour);

-- CBD-wide parking per hour. Stale bays (no report in 24 h) are counted apart
-- and left out of pct_free's denominator.
create table if not exists parking_hourly (
  hour          timestamptz primary key,
  bays_free     integer not null check (bays_free >= 0),
  bays_occupied integer not null check (bays_occupied >= 0),
  bays_stale    integer not null check (bays_stale >= 0),
  pct_free      real    check (pct_free between 0 and 1)
);

-- Next-24-hour forecasts, rewritten daily by model/predict.py.
create table if not exists forecasts (
  sensor_id       integer     not null,
  hour            timestamptz not null,
  predicted_count real        not null,
  baseline_count  real,
  generated_at    timestamptz not null default now(),
  primary key (sensor_id, hour)
);

-- Read-only role for the website. No password here: the repo is public.
-- Set it once in the SQL Editor (not in this file):
--   alter role web_reader password '<paste output of: openssl rand -base64 32>';
-- Then:
--   DATABASE_URL_READONLY=postgresql://web_reader:<password>@<endpoint>-pooler.<region>.aws.neon.tech/<dbname>?sslmode=require
do $$
begin
  if not exists (select from pg_roles where rolname = 'web_reader') then
    create role web_reader login;
  end if;
end
$$;

alter role web_reader set default_transaction_read_only = on;
alter role web_reader set statement_timeout = '5s';
revoke all on all tables in schema public from web_reader;
grant usage on schema public to web_reader;
grant select on latest, pedestrian_hourly, parking_hourly, forecasts to web_reader;
