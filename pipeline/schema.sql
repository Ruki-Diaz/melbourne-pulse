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

-- Hourly weather forecast for the CBD (Open-Meteo), for the Plan page. `hour` is
-- the UTC instant the hour starts; rain columns describe that hour (see
-- pipeline/pulse/openmeteo.py). Future hours are replaced by every hourly run;
-- past hours are kept 2 days. A missing value is null, never 0.
create table if not exists weather_forecast (
  hour                      timestamptz primary key,
  precipitation             real,      -- mm in the hour
  precipitation_probability real,      -- 0-100
  temperature               real,      -- deg C
  wind_speed                real,      -- km/h
  weather_code              smallint,  -- WMO code
  fetched_at                timestamptz not null default now()
);

-- How much rain changes pedestrian counts, measured over the last 12 months by
-- pipeline/rain_effect.py (monthly; the whole table is replaced each run).
-- Used to explain the forecast, never to adjust it.
--   scope        key
--   overall      all
--   intensity    light | heavy
--   daytype      weekday | weekend      (weekend includes public holidays)
--   temperature  cold | mild | warm     (< 12 C, 12-20 C, > 20 C)
--   sensor       <location_id>
--   profile      cbd                    detail = [{hour, wet, dry, n_wet_hours}]
-- effect, ci_low, ci_high are fractions (-0.18 = 18% fewer). reliable = at
-- least 100 wet hours and a 95% interval that excludes zero.
create table if not exists rain_effect (
  scope        text        not null
               check (scope in ('overall', 'intensity', 'daytype', 'temperature', 'sensor', 'profile')),
  key          text        not null,
  effect       real,
  ci_low       real,
  ci_high      real,
  n_wet_hours  integer     not null check (n_wet_hours >= 0),
  reliable     boolean     not null default false,
  detail       jsonb,
  window_start date        not null,
  window_end   date        not null,
  computed_at  timestamptz not null,
  primary key (scope, key)
);

-- One row per finished hour: does the city's live feed look faulty? (pipeline/feed_quality.py,
-- rules in pipeline/pulse/quality.py.) anomaly = most sensors read under half their typical
-- at once, not explained by heavy rain or a public holiday. The cause isn't known then
-- (severe weather, a major event, or a feed fault). The website shows a notice instead of
-- a comparison for such an hour, and the forecast model leaves it out.
create table if not exists feed_quality (
  hour           timestamptz primary key,
  sensors_judged integer     not null check (sensors_judged >= 0),  -- sensors with a usable typical
  sensors_low    integer     not null check (sensors_low >= 0),     -- of those, under the threshold
  share_low      real,                                               -- sensors_low / sensors_judged
  anomaly        boolean     not null,
  reason         text        not null,  -- ok | low_counts | holding | public_holiday | too_few_sensors
  heavy_rain     boolean     not null default false,                 -- thresholds were relaxed for heavy rain
  checked_at     timestamptz not null default now()
);
-- What the city's published hourly totals later said about a flagged hour
-- (pipeline/audit.py --resolve, daily). null = not compared yet.
--   confirmed_real   ours matched the city's: really that quiet. anomaly is set back to false.
--   confirmed_fault  ours were well below the city's: the live feed was incomplete. Stays flagged.
alter table feed_quality add column if not exists resolution text
  check (resolution in ('confirmed_real', 'confirmed_fault'));
create index if not exists feed_quality_anomaly on feed_quality (hour) where anomaly;

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
grant select on latest, pedestrian_hourly, parking_hourly, forecasts, weather_forecast, rain_effect, feed_quality
  to web_reader;
