# Data sources

All data comes from the **City of Melbourne Open Data** portal (Opendatasoft
Explore API v2.1), licensed **CC BY**. No API key is required.

```
Base: https://data.melbourne.vic.gov.au/api/explore/v2.1/catalog/datasets/<id>
  /records        paged queries (max 100 rows per call, ODSQL select/where/group_by)
  /exports/json   full dataset as one JSON array (no row limit; accepts where/select)
  /exports/csv    same, semicolon-delimited, UTF-8 with BOM
```

Everything below was checked against live responses on **2026-10-01, about 02:50 AEST
(2026-09-30 16:50 UTC)**. Field names are exactly as the API returns them.

| Dataset id | Rows | Used for |
|---|---:|---|
| `on-street-parking-bay-sensors` | 6,324 | live parking layer |
| `pedestrian-counting-system-past-hour-counts-per-minute` | ~56,600 | live pedestrian counts |
| `pedestrian-counting-system-sensor-locations` | 134 | sensor names and coordinates |
| `pedestrian-counting-system-monthly-counts-per-hour` | 1,623,914 | model training and "typical" baseline |

All four ids resolved on the first try, so no catalog search was needed.

---

## 1. `on-street-parking-bay-sensors`

One row per in-ground bay sensor. The **whole dataset is the current state**.

| Field | Type | Example | Notes |
|---|---|---|---|
| `kerbsideid` | int | `57940` | Unique per row (verified). Use as the bay id. |
| `status_description` | text | `"Unoccupied"` | Only two values: `Present` (car in the bay) and `Unoccupied` (free). |
| `status_timestamp` | datetime (UTC) | `2025-04-14T03:01:40+00:00` | When the status last changed. |
| `lastupdated` | datetime (UTC) | `2026-09-30T16:48:49+00:00` | When the sensor last reported. |
| `zone_number` | int, nullable | `7218` | Parking restriction zone. `null` on 520 rows. |
| `location` | geo_point_2d | `{"lon": 144.9546, "lat": -37.8203}` | Note the key order: `lon`, then `lat`. |

Observed state: 4,253 `Unoccupied` and 2,071 `Present`.

**Stale sensors.** 5,345 rows had `lastupdated` today. The rest are days to
months old; the oldest is `2024-12-04`. A bay whose sensor has gone quiet will
still show its last known status. The map and the "% free" stat should only count
bays with `lastupdated` in the last 24 h. The others can be drawn grey as "no
recent data".

## 2. `pedestrian-counting-system-past-hour-counts-per-minute`

Despite the name, this is a **rolling window of about 26 hours**, not one hour.
Observed range: `2026-09-29T13:55Z` to `2026-09-30T16:25Z`, from 99 distinct
sensors. It lags real time by about 25 minutes.

| Field | Type | Example | Notes |
|---|---|---|---|
| `location_id` | int | `3` | Joins to `sensor-locations.location_id`. |
| `sensing_datetime` | datetime (UTC) | `2026-09-29T14:02:00+00:00` | Start of the minute. Use this field for time maths. |
| `sensing_date` | date (local) | `2026-09-30` | Melbourne local date. |
| `sensing_time` | text (local) | `"00:02"` | Melbourne local `HH:MM`. |
| `direction_1` | int | `0` | Count in direction 1 (named in sensor-locations). |
| `direction_2` | int | `3` | Count in direction 2. |
| `total_of_directions` | int | `3` | `direction_1 + direction_2` |

Quirks:
- **Zero minutes are omitted.** Only one row in the whole window has
  `total_of_directions = 0`, so a missing minute means a count of 0.
- **Granularity varies by sensor.** Location 3 reports 60 rows an hour.
  Location 5 reports 12, one per 5 minutes. Always `sum()` per hour. Never
  count rows.
- **Size.** A full `/exports/json` is **about 10.6 MB**. Stored hourly for 3 days,
  that is about 760 MB, which is more than Supabase's 500 MB free tier. The fetch
  should filter on the server:
  `where=sensing_datetime >= now(hours=-2)` returns about 80 KB per hour of data.

## 3. `pedestrian-counting-system-sensor-locations`

Static metadata. There are 134 rows (100 outdoor, 34 indoor), all with `status = "A"`.

| Field | Type | Example |
|---|---|---|
| `location_id` | int | `3` |
| `sensor_description` | text | `"Melbourne Central"` (human-readable name; use this in the UI) |
| `sensor_name` | text | `"Swa295_T"` (internal code) |
| `installation_date` | date | `2009-03-25` |
| `note` | text, nullable | `"Device has been replaced with new sensor on 22/03/2019"` |
| `location_type` | text | `"Outdoor"` / `"Indoor"` |
| `status` | text | `"A"` |
| `direction_1` / `direction_2` | text | `"North"` / `"South"` (here these are labels, not counts) |
| `latitude` / `longitude` | double | `-37.81101524` / `144.96429485` |
| `location` | geo_point_2d | `{"lon": ..., "lat": ...}` |

All 99 live `location_id`s exist here. The other 35 sensors are not reporting
at the moment.

## 4. `pedestrian-counting-system-monthly-counts-per-hour`

Hourly totals per sensor. This is already a **rolling 2-year window**,
`2024-10-01` to `2026-09-30`, from 103 sensors. That covers exactly what the model
needs, so there is no 2009 history to avoid. The newest day is partial, with a lag
of about 1 day.

| Field | Type | Example | Notes |
|---|---|---|---|
| `id` | int | `1421420250122` | Built as `location_id` + `hourday` + `yyyymmdd`. Don't parse it; use the columns. |
| `location_id` | int | `142` | Same id space as the live feed. |
| `sensing_date` | date (local) | `2025-01-22` | Melbourne local date. JSON shows it as `2025-01-22T00:00:00+00:00`; ignore the fake UTC suffix. |
| `hourday` | int 0–23 | `14` | **Local** hour (verified below). |
| `direction_1` / `direction_2` | int | `542` / `446` | |
| `pedestriancount` | int | `988` | Hourly total. The API label is "Total_of_Directions", but the field name is `pedestriancount`. |
| `sensor_name` | text | `"Hammer1584_T"` | |
| `location` | geo_point_2d | | |

(`location_id`, `sensing_date`, `hourday`) is unique (verified).

**Timezone check.** For location 3, `hourday = 0` on `2026-09-30` equals **219**.
That matches the per-minute sum over `2026-09-29 14:00–15:00 UTC`, which is also
**219**. So `hourday` is AEST local time. Daylight saving starts on
**2026-10-04**, so forecasts must build timestamps in `Australia/Melbourne`, not
with a fixed +10 offset.

**Download.** `/exports/csv?select=location_id,sensing_date,hourday,pedestriancount`
returns about 1.4 MB per month (4 s). Two years is about 35 MB, which is fine for a
daily GitHub Action. Pulling month by month with a `where` filter keeps each
request small and lets a failed month be retried on its own.

---

## Decisions for later phases

1. **Pedestrian live:** export with a `where` filter for the last 2 hours, then sum
   `total_of_directions` per `location_id` over the latest complete hour.
2. **Parking live:** full export (about 1.5 MB). Status is `Present` = occupied and
   `Unoccupied` = free. Ignore bays with `lastupdated` older than 24 h.
3. **Sensors:** store `sensor-locations` in `latest` (source `sensors`). It is tiny
   and rarely changes.
4. **"Typical" level:** the mean `pedestriancount` per
   (`location_id`, day of week, `hourday`) from the monthly dataset.
5. **Existing root `fetch.py`** downloads the full 10.6 MB pedestrian feed every
   hour, which would fill the free database in about 2 days. Phase 1 fixes this
   with point 1.
6. **Attribution:** "City of Melbourne Open Data, CC BY". The monthly dataset's
   metadata leaves `license` empty, but it belongs to the same CC BY
   pedestrian-counting collection.
