# Plan API

Three read-only endpoints behind the Plan page (`/plan`). All of them answer
from one cached snapshot of the database (`web/lib/plan.ts`), and every number
is computed by pure functions in `web/lib/plan-core.ts`.

**Every example on this page is a real response**, captured on 2026-10-01 from a
local build reading the production database. Where an array has been
shortened, the cut is marked with a `// ...` line; the values that are shown
are untouched. When the shapes change, capture new responses rather than
editing numbers by hand.

- [GET /api/plan](#get-apiplan)
- [GET /api/plan/evidence](#get-apiplanevidence)
- [GET /api/plan/sensors](#get-apiplansensors)
- [Errors](#errors)
- [Caching and freshness](#caching-and-freshness)

Wording used in every text field: "pedestrian counts" and "foot traffic". A
sensor counts passers-by, and one person can pass several sensors, so the
figures are never called "people".

## GET /api/plan

`/api/plan?sensor=<id|cbd>&window=<12h|today|tomorrow|36h>`

| Parameter | Default | Values |
|---|---|---|
| `sensor` | `cbd` | `cbd` for all sensors together, or a sensor id from `/api/plan/sensors` |
| `window` | `12h` | `12h` and `36h`: from the next full hour. `today`: from the next full hour to midnight (empty after 11pm). `tomorrow`: midnight to midnight, Melbourne time (23 or 25 hours on a daylight-saving change). |

### Shape

```ts
type PlanResponse = {
  generatedAt: string;            // when this response was computed (UTC)
  dataFreshness: {
    forecastGeneratedAt: string | null;   // newest write to the forecasts table
    weatherFetchedAt: string | null;      // newest write to weather_forecast
    rainEffectComputedAt: string | null;  // newest write to rain_effect
    snapshotAt: string;                   // when the website last read the database
  };
  sensor: "cbd" | { id: number; name: string; lat: number; lon: number };
  sensorsUsed: number;            // sensors behind every count in `hours` (1 for a single sensor)
  window: { key: "12h" | "today" | "tomorrow" | "36h"; start: string; end: string; complete: boolean };
  hours: Array<{
    hourLocal: string;            // start of the hour, Melbourne time with offset
    forecastCount: number;        // forecast pedestrian counts in that hour
    typicalCount: number | null;  // 8-week median for the same weekday and hour
    deltaPct: number | null;      // forecast against typical, in percent
    precipMm: number | null;      // rain forecast for the hour
    precipProb: number | null;    // chance of rain, 0-100
    tempC: number | null;
    windKmh: number | null;
    weatherCode: number | null;   // WMO code
  }>;
  rainEffect: {
    value: number;                // change in a wet hour, in percent (-18.5 = 18.5% fewer)
    ciLow: number | null;         // 95% interval
    ciHigh: number | null;
    nWetHours: number;
    reliable: boolean;            // enough wet hours and an interval that excludes zero
    usedFallback: boolean;        // true: the sensor's own estimate wasn't reliable, this is the CBD-wide one
    scope: "sensor" | "cbd";      // which estimate `value` is
  } | null;
  recommendations: {
    mostTraffic: RecommendationSet;
    busyButDry: RecommendationSet;
    quietest: RecommendationSet;
    hoursConsidered: { from: string; to: string; daytimeOnly: boolean } | null;
  };
};

type RecommendationSet = { best: Recommendation | null; secondBest: Recommendation | null; avoid: Recommendation | null };

type Recommendation = {
  start: string;                  // Melbourne time with offset
  end: string;                    // exclusive
  deltaPct: number | null;        // the block's forecast against its typical
  maxPrecipProb: number | null;   // highest chance of rain in the block
  reason: string;                 // one or two plain sentences
};
```

### Rules worth knowing

- **`sensorsUsed` and the CBD totals.** For `sensor=cbd`, `forecastCount` and
  `typicalCount` are sums over the *same* sensors in *every* hour returned: the
  sensors that have both a forecast and a typical in all of those hours.
  `sensorsUsed` is how many that is. A sensor that is missing either value in
  any hour is left out of all of them, so the two columns are always
  comparable with each other and from hour to hour. An hour covered by fewer
  than half the sensors (a leftover from an old forecast run) is dropped
  instead of shrinking the set.
- **`window.complete`** is `false` when the forecast doesn't reach the end of
  the window yet. The daily run writes 36 hours, so late in the day the tail of
  `36h` and most of `tomorrow` are not there until the next run.
- **`dataFreshness`** gives each table's newest write (a `max()` over the whole
  table) and `snapshotAt`, the moment the database was read. All the numbers in
  one response come from that single read, so two responses with the same
  `snapshotAt` always agree on every hour they share.
- **The forecast already includes the weather forecast.** `rainEffect` only
  explains it. It is never applied to `forecastCount`.
- **Recommendations** are blocks of 2 consecutive hours, picked with no
  randomness. Blocks inside 7am to 10pm are used when the window has any
  (`daytimeOnly: true`); otherwise every block is used. `hoursConsidered` is
  the real range those blocks span: the start of the first to the end of the
  last. `secondBest` never overlaps `best`, and `avoid` overlaps neither.
  - `mostTraffic`: highest average forecast. `avoid` is the lowest.
  - `busyButDry`: an hour is a rain risk if `precipProb >= 50` or
    `precipMm >= 0.2`. Blocks with fewer rain-risk hours always rank above
    blocks with more; ties go to the busier block. `avoid` is the wettest.
  - `quietest`: lowest average forecast. `avoid` is the highest.
- **Rain wording in `reason`** follows `maxPrecipProb` and always shows it:
  under 30% "Low rain risk (12%)", 30 to 49% "Some rain risk (41%)", 50% and
  over "Rain likely (76%)". With no rain forecast it reads "No rain forecast
  for these hours."

### Example: `GET /api/plan?sensor=cbd&window=12h`

The complete response, 5,051 bytes. The same call with `window=36h`
was 8,845 bytes (34 hours); the limit is 15 KB.

```json
{
  "generatedAt": "2026-10-01T16:52:13.632Z",
  "dataFreshness": {
    "forecastGeneratedAt": "2026-10-01T14:44:50.589Z",
    "weatherFetchedAt": "2026-10-01T16:07:52.721Z",
    "rainEffectComputedAt": "2026-10-01T16:30:01.213Z",
    "snapshotAt": "2026-10-01T16:36:23.535Z"
  },
  "sensor": "cbd",
  "sensorsUsed": 99,
  "window": {
    "key": "12h",
    "start": "2026-10-01T17:00:00.000Z",
    "end": "2026-10-02T05:00:00.000Z",
    "complete": true
  },
  "hours": [
    {
      "hourLocal": "2026-10-02T03:00:00+10:00",
      "forecastCount": 1581,
      "typicalCount": 1340,
      "deltaPct": 18,
      "precipMm": 0.7,
      "precipProb": 84,
      "tempC": 12.3,
      "windKmh": 11.1,
      "weatherCode": 53
    },
    {
      "hourLocal": "2026-10-02T04:00:00+10:00",
      "forecastCount": 1403,
      "typicalCount": 1228,
      "deltaPct": 14.3,
      "precipMm": 0.3,
      "precipProb": 82,
      "tempC": 12.1,
      "windKmh": 15.9,
      "weatherCode": 53
    },
    {
      "hourLocal": "2026-10-02T05:00:00+10:00",
      "forecastCount": 2488,
      "typicalCount": 2555,
      "deltaPct": -2.6,
      "precipMm": 0.4,
      "precipProb": 80,
      "tempC": 12.1,
      "windKmh": 13.6,
      "weatherCode": 51
    },
    {
      "hourLocal": "2026-10-02T06:00:00+10:00",
      "forecastCount": 7443,
      "typicalCount": 8289,
      "deltaPct": -10.2,
      "precipMm": 0.7,
      "precipProb": 78,
      "tempC": 12,
      "windKmh": 13.8,
      "weatherCode": 51
    },
    {
      "hourLocal": "2026-10-02T07:00:00+10:00",
      "forecastCount": 16048,
      "typicalCount": 19038,
      "deltaPct": -15.7,
      "precipMm": 0.7,
      "precipProb": 76,
      "tempC": 11.9,
      "windKmh": 13.1,
      "weatherCode": 53
    },
    {
      "hourLocal": "2026-10-02T08:00:00+10:00",
      "forecastCount": 32130,
      "typicalCount": 41096,
      "deltaPct": -21.8,
      "precipMm": 0.1,
      "precipProb": 74,
      "tempC": 12.1,
      "windKmh": 14.6,
      "weatherCode": 53
    },
    {
      "hourLocal": "2026-10-02T09:00:00+10:00",
      "forecastCount": 35841,
      "typicalCount": 39018,
      "deltaPct": -8.1,
      "precipMm": 0,
      "precipProb": 73,
      "tempC": 13.1,
      "windKmh": 15.8,
      "weatherCode": 51
    },
    {
      "hourLocal": "2026-10-02T10:00:00+10:00",
      "forecastCount": 44164,
      "typicalCount": 43387,
      "deltaPct": 1.8,
      "precipMm": 0.1,
      "precipProb": 74,
      "tempC": 13.8,
      "windKmh": 15.5,
      "weatherCode": 3
    },
    {
      "hourLocal": "2026-10-02T11:00:00+10:00",
      "forecastCount": 58580,
      "typicalCount": 53143,
      "deltaPct": 10.2,
      "precipMm": 0.7,
      "precipProb": 76,
      "tempC": 14.4,
      "windKmh": 14.9,
      "weatherCode": 51
    },
    {
      "hourLocal": "2026-10-02T12:00:00+10:00",
      "forecastCount": 73939,
      "typicalCount": 74800,
      "deltaPct": -1.2,
      "precipMm": 0.6,
      "precipProb": 76,
      "tempC": 14.5,
      "windKmh": 15.4,
      "weatherCode": 53
    },
    {
      "hourLocal": "2026-10-02T13:00:00+10:00",
      "forecastCount": 75460,
      "typicalCount": 76400,
      "deltaPct": -1.2,
      "precipMm": 0.5,
      "precipProb": 73,
      "tempC": 14.9,
      "windKmh": 15.9,
      "weatherCode": 53
    },
    {
      "hourLocal": "2026-10-02T14:00:00+10:00",
      "forecastCount": 72077,
      "typicalCount": 70715,
      "deltaPct": 1.9,
      "precipMm": 0.5,
      "precipProb": 67,
      "tempC": 15.3,
      "windKmh": 16.1,
      "weatherCode": 53
    }
  ],
  "rainEffect": {
    "value": -18.5,
    "ciLow": -21.8,
    "ciHigh": -14.9,
    "nWetHours": 868,
    "reliable": true,
    "usedFallback": false,
    "scope": "cbd"
  },
  "recommendations": {
    "mostTraffic": {
      "best": {
        "start": "2026-10-02T12:00:00+10:00",
        "end": "2026-10-02T14:00:00+10:00",
        "deltaPct": -1.2,
        "maxPrecipProb": 76,
        "reason": "Highest forecast foot traffic: about 74,700 pedestrian counts an hour, about typical for these hours. Rain likely (76%)."
      },
      "secondBest": {
        "start": "2026-10-02T10:00:00+10:00",
        "end": "2026-10-02T12:00:00+10:00",
        "deltaPct": 6.4,
        "maxPrecipProb": 76,
        "reason": "Next-highest forecast foot traffic: about 51,372 pedestrian counts an hour, 6% above typical. Rain likely (76%)."
      },
      "avoid": {
        "start": "2026-10-02T07:00:00+10:00",
        "end": "2026-10-02T09:00:00+10:00",
        "deltaPct": -19.9,
        "maxPrecipProb": 76,
        "reason": "Lowest forecast foot traffic: about 24,089 pedestrian counts an hour, 20% below typical. Rain likely (76%)."
      }
    },
    "busyButDry": {
      "best": {
        "start": "2026-10-02T12:00:00+10:00",
        "end": "2026-10-02T14:00:00+10:00",
        "deltaPct": -1.2,
        "maxPrecipProb": 76,
        "reason": "Rain is likely in every option; the busiest of the least rainy hours: about 74,700 pedestrian counts an hour, about typical for these hours. Rain likely (76%)."
      },
      "secondBest": {
        "start": "2026-10-02T10:00:00+10:00",
        "end": "2026-10-02T12:00:00+10:00",
        "deltaPct": 6.4,
        "maxPrecipProb": 76,
        "reason": "Rain is likely in every option; the busiest of the least rainy hours: about 51,372 pedestrian counts an hour, 6% above typical. Rain likely (76%)."
      },
      "avoid": {
        "start": "2026-10-02T07:00:00+10:00",
        "end": "2026-10-02T09:00:00+10:00",
        "deltaPct": -19.9,
        "maxPrecipProb": 76,
        "reason": "Most likely to be wet: about 24,089 pedestrian counts an hour, 20% below typical. Rain likely (76%)."
      }
    },
    "quietest": {
      "best": {
        "start": "2026-10-02T07:00:00+10:00",
        "end": "2026-10-02T09:00:00+10:00",
        "deltaPct": -19.9,
        "maxPrecipProb": 76,
        "reason": "Lowest forecast foot traffic: about 24,089 pedestrian counts an hour, 20% below typical. Rain likely (76%)."
      },
      "secondBest": {
        "start": "2026-10-02T09:00:00+10:00",
        "end": "2026-10-02T11:00:00+10:00",
        "deltaPct": -2.9,
        "maxPrecipProb": 74,
        "reason": "Next-lowest forecast foot traffic: about 40,003 pedestrian counts an hour, about typical for these hours. Rain likely (74%)."
      },
      "avoid": {
        "start": "2026-10-02T12:00:00+10:00",
        "end": "2026-10-02T14:00:00+10:00",
        "deltaPct": -1.2,
        "maxPrecipProb": 76,
        "reason": "Highest forecast foot traffic: about 74,700 pedestrian counts an hour, about typical for these hours. Rain likely (76%)."
      }
    },
    "hoursConsidered": {
      "from": "2026-10-02T07:00:00+10:00",
      "to": "2026-10-02T15:00:00+10:00",
      "daytimeOnly": true
    }
  }
}
```

For one sensor (`/api/plan?sensor=4&window=12h`), these are the parts whose
shape differs:

```json
{
  "sensor": {
    "id": 4,
    "name": "Town Hall (West)",
    "lat": -37.81487988,
    "lon": 144.9660878
  },
  "sensorsUsed": 1,
  "rainEffect": {
    "value": -12.4,
    "ciLow": -16.6,
    "ciHigh": -7.3,
    "nWetHours": 867,
    "reliable": true,
    "usedFallback": false,
    "scope": "sensor"
  }
}
```

## GET /api/plan/evidence

What the rain effect is based on. No parameters.

```ts
type EvidenceResponse = {
  generatedAt: string;
  window: { start: string; end: string } | null;   // the 12 months measured, local dates, inclusive
  computedAt: string | null;
  method: {                       // as stored with the data by pipeline/rain_effect.py
    wetMm: number;                // an hour is wet from this much rain
    heavyMm: number;              // and heavy from this much
    minDryHours: number;          // dry hours a comparison needs
    bootstrapReps: number;
    minWetHours: number;          // wet hours an estimate needs to be reliable
    coldBelowC: number;
    warmAboveC: number;
  } | null;
  forest: Array<{                 // overall first, then each breakdown
    group: "overall" | "intensity" | "daytype" | "temperature";
    key: string;
    label: string;
    value: number;                // percent
    ciLow: number | null;
    ciHigh: number | null;
    nWetHours: number;
    reliable: boolean;
  }>;
  profile: Array<{ hour: number; wet: number; dry: number; nWetHours: number }>;  // CBD total by hour of day
  sensors: Array<{                // most negative first
    id: number; name: string; lat: number | null; lon: number | null;
    value: number; ciLow: number | null; ciHigh: number | null; nWetHours: number; reliable: boolean;
  }>;
};
```

`profile` compares the average CBD total in wet hours (`wet`) with what dry
hours matched to the same sensors, day type and month would have given (`dry`).

### Example

The full response was 18,971 bytes, with 24 profile rows and
102 sensors (99 of them reliable).

```jsonc
{
  "generatedAt": "2026-10-01T16:52:13.648Z",
  "window": {
    "start": "2025-10-01",
    "end": "2026-09-30"
  },
  "computedAt": "2026-10-01T16:30:01.213Z",
  "method": {
    "wetMm": 0.2,
    "heavyMm": 2,
    "minDryHours": 3,
    "bootstrapReps": 400,
    "minWetHours": 100,
    "coldBelowC": 12,
    "warmAboveC": 20
  },
  "forest": [
    {
      "group": "overall",
      "key": "all",
      "label": "All wet hours",
      "value": -18.5,
      "ciLow": -21.8,
      "ciHigh": -14.9,
      "nWetHours": 868,
      "reliable": true
    },
    {
      "group": "intensity",
      "key": "light",
      "label": "Light rain (0.2 to 2 mm an hour)",
      "value": -17.1,
      "ciLow": -20.3,
      "ciHigh": -13.5,
      "nWetHours": 768,
      "reliable": true
    },
    {
      "group": "intensity",
      "key": "heavy",
      "label": "Heavy rain (2 mm an hour or more)",
      "value": -29.4,
      "ciLow": -36.6,
      "ciHigh": -20.8,
      "nWetHours": 100,
      "reliable": true
    },
    {
      "group": "daytype",
      "key": "weekday",
      "label": "Weekdays",
      "value": -15.8,
      "ciLow": -19.4,
      "ciHigh": -11.6,
      "nWetHours": 536,
      "reliable": true
    },
    {
      "group": "daytype",
      "key": "weekend",
      "label": "Weekends and public holidays",
      "value": -23.6,
      "ciLow": -29.5,
      "ciHigh": -17.4,
      "nWetHours": 332,
      "reliable": true
    },
    {
      "group": "temperature",
      "key": "cold",
      "label": "Cold (below 12 °C)",
      "value": -26.6,
      "ciLow": -33.1,
      "ciHigh": -18.6,
      "nWetHours": 203,
      "reliable": true
    },
    {
      "group": "temperature",
      "key": "mild",
      "label": "Mild (12 to 20 °C)",
      "value": -17.6,
      "ciLow": -21,
      "ciHigh": -13.5,
      "nWetHours": 578,
      "reliable": true
    },
    {
      "group": "temperature",
      "key": "warm",
      "label": "Warm (above 20 °C)",
      "value": -14,
      "ciLow": -22.7,
      "ciHigh": -4.3,
      "nWetHours": 87,
      "reliable": false
    }
  ],
  "profile": [
    {
      "hour": 0,
      "wet": 7131,
      "dry": 9603,
      "nWetHours": 29
    },
    {
      "hour": 1,
      "wet": 5282,
      "dry": 6062,
      "nWetHours": 31
    },
    {
      "hour": 2,
      "wet": 3371,
      "dry": 3895,
      "nWetHours": 27
    },
    // ... 21 more, left out of this example
  ],
  "sensors": [
    {
      "id": 11,
      "name": "Docklands Waterfront City Building Side",
      "lat": -37.81566651,
      "lon": 144.93974366,
      "value": -49.8,
      "ciLow": -56.1,
      "ciHigh": -43.5,
      "nWetHours": 868,
      "reliable": true
    },
    {
      "id": 29,
      "name": "St Kilda Rd-Alexandra Gardens",
      "lat": -37.8199817,
      "lon": 144.96872865,
      "value": -47.8,
      "ciLow": -55.5,
      "ciHigh": -37.3,
      "nWetHours": 864,
      "reliable": true
    },
    // ... 100 more, left out of this example
  ]
}
```

## GET /api/plan/sensors

The sensors that have a forecast right now, sorted by name, for the picker.
The full response had 99 sensors (8,616 bytes).

```jsonc
{
  "sensors": [
    {
      "id": 118,
      "name": "114 Flinders Street Car Park Crossing",
      "lat": -37.81632783,
      "lon": 144.97090512
    },
    {
      "id": 117,
      "name": "114 Flinders Street Car Park Footpath",
      "lat": -37.81629332,
      "lon": 144.97090877
    },
    {
      "id": 184,
      "name": "124 Elizabeth Street",
      "lat": -37.81512416,
      "lon": 144.96371988
    },
    // ... 96 more, left out of this example
  ]
}
```

## Errors

Errors are JSON with one field and are never cached:

```json
{ "error": "window must be one of: 12h, today, tomorrow, 36h" }
```

| Status | When |
|---|---|
| 400 | `window` isn't one of the four values, or `sensor` isn't `cbd` or a number |
| 404 | the sensor id has no forecast |
| 503 | the database isn't configured or couldn't be read |

## Caching and freshness

- The database is read once into a snapshot that is cached for an hour (tag
  `plan`). The hourly job calls `/api/revalidate`, which drops the snapshot,
  and then requests `/api/plan` so the new one is built while the database is
  still awake. Changing the sensor or window never queries the database.
- If a snapshot is somehow more than 90 minutes old when a request arrives,
  the database is read directly for that request.
- Responses carry `Cache-Control: public, s-maxage=300, stale-while-revalidate=3600`.
- The logic is tested in `pipeline/tests/test_plan_recommendations.py`, which
  runs the real TypeScript with Node 22.18 or newer.
