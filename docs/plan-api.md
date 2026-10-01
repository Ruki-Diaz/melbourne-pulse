# Plan API Specification

The Plan API serves foot-traffic and weather forecast data for the Plan page (`/plan`).
Responses are computed in-memory from a single cached Neon database snapshot (tag `plan`, cached for 1 hour).
The cache is invalidated on each hourly ingestion run via `/api/revalidate`.

---

## Endpoints

### 1. `GET /api/plan`

Returns hourly pedestrian count forecasts, historical typical baselines, delta percentages, hourly weather forecasts (precipitation, temperature, wind speed, WMO weather codes), rain effect evidence for the selected sensor (or CBD fallback), and 2-hour window activity recommendations.

#### Query Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `sensor` | `string \| number` | `"cbd"` | `"cbd"` for aggregated CBD-wide forecast, or a numeric sensor ID (e.g. `3`). |
| `window` | `string` | `"12h"` | Time window: `"12h"` (next 12 hours), `"today"` (remaining hours today), `"tomorrow"` (24 hours tomorrow), or `"36h"` (36-hour horizon). |

#### Response Shape

```typescript
type PlanResponse = {
  generatedAt: string; // ISO 8601 UTC
  dataFreshness: {
    forecastGeneratedAt: string | null;
    weatherFetchedAt: string | null;
    rainEffectComputedAt: string | null;
  };
  sensor:
    | "cbd"
    | {
        id: number;
        name: string;
        lat: number;
        lon: number;
      };
  window: {
    key: "12h" | "today" | "tomorrow" | "36h";
    start: string; // ISO 8601 UTC
    end: string; // ISO 8601 UTC
    complete: boolean; // false if forecast doesn't cover the full window yet
  };
  hours: Array<{
    hourLocal: string; // Melbourne local time with ISO offset (e.g. "2026-10-02T02:00:00+10:00")
    forecastCount: number; // Predicted pedestrians
    typicalCount: number | null; // Historical median for this day-of-week & hour
    deltaPct: number | null; // % difference from typical (-3.5 = 3.5% below typical)
    precipMm: number | null; // Rain in mm for the hour
    precipProb: number | null; // Probability of rain 0-100%
    tempC: number | null; // Temperature in °C
    windKmh: number | null; // Wind speed in km/h
    weatherCode: number | null; // WMO weather code
  }>;
  rainEffect: {
    value: number; // Historical change in counts during wet hours in % (-18.5 = -18.5%)
    ciLow: number | null; // 95% bootstrap CI lower bound
    ciHigh: number | null; // 95% bootstrap CI upper bound
    nWetHours: number; // Number of observed wet hours in 12-month sample
    reliable: boolean; // true if >= 100 wet hours and 95% CI excludes 0
    usedFallback: boolean; // true if sensor lacked data and CBD-wide value is used
    scope: "sensor" | "cbd";
  } | null;
  recommendations: {
    mostTraffic: RecommendationSet;
    busyButDry: RecommendationSet;
    quietest: RecommendationSet;
  };
};

type RecommendationSet = {
  best: Recommendation | null;
  secondBest: Recommendation | null;
  avoid: Recommendation | null;
};

type Recommendation = {
  start: string; // Melbourne local ISO start (e.g. "2026-10-02T16:00:00+10:00")
  end: string; // Melbourne local ISO end (exclusive, covers 2 hours)
  deltaPct: number | null;
  maxPrecipProb: number | null;
  reason: string;
};
```

#### Example Real Response (`GET /api/plan?sensor=cbd&window=36h`)

*Response Size: ~8.72 KB (8,930 bytes)*

```json
{
  "generatedAt": "2026-10-01T15:22:39.953Z",
  "dataFreshness": {
    "forecastGeneratedAt": "2026-10-01T14:44:50.589Z",
    "weatherFetchedAt": "2026-10-01T14:57:13.156Z",
    "rainEffectComputedAt": "2026-10-01T14:57:13.459Z"
  },
  "sensor": "cbd",
  "window": {
    "key": "36h",
    "start": "2026-10-01T16:00:00.000Z",
    "end": "2026-10-03T04:00:00.000Z",
    "complete": false
  },
  "hours": [
    {
      "hourLocal": "2026-10-02T02:00:00+10:00",
      "forecastCount": 1698,
      "typicalCount": 1759,
      "deltaPct": -3.5,
      "precipMm": 0.5,
      "precipProb": 87,
      "tempC": 12.2,
      "windKmh": 8.2,
      "weatherCode": 53
    },
    {
      "hourLocal": "2026-10-02T03:00:00+10:00",
      "forecastCount": 1289,
      "typicalCount": 1341,
      "deltaPct": -3.9,
      "precipMm": 0.2,
      "precipProb": 81,
      "tempC": 12.1,
      "windKmh": 6.9,
      "weatherCode": 51
    },
    {
      "hourLocal": "2026-10-02T16:00:00+10:00",
      "forecastCount": 78051,
      "typicalCount": 83457,
      "deltaPct": -6.5,
      "precipMm": 0.8,
      "precipProb": 54,
      "tempC": 15.2,
      "windKmh": 11.2,
      "weatherCode": 61
    },
    {
      "hourLocal": "2026-10-02T17:00:00+10:00",
      "forecastCount": 79147,
      "typicalCount": 83526,
      "deltaPct": -5.2,
      "precipMm": 0.2,
      "precipProb": 49,
      "tempC": 14.8,
      "windKmh": 12.5,
      "weatherCode": 51
    }
  ],
  "rainEffect": {
    "value": -18.5,
    "ciLow": -21.8,
    "ciHigh": -14.4,
    "nWetHours": 876,
    "reliable": true,
    "usedFallback": false,
    "scope": "cbd"
  },
  "recommendations": {
    "mostTraffic": {
      "best": {
        "start": "2026-10-02T16:00:00+10:00",
        "end": "2026-10-02T18:00:00+10:00",
        "deltaPct": -5.9,
        "maxPrecipProb": 54,
        "reason": "Highest forecast foot traffic: about 78,599 pedestrian counts an hour, 6% below typical. Rain likely (up to 54% chance)."
      },
      "secondBest": {
        "start": "2026-10-02T12:00:00+10:00",
        "end": "2026-10-02T14:00:00+10:00",
        "deltaPct": -1.2,
        "maxPrecipProb": 76,
        "reason": "Next-highest forecast foot traffic: about 74,700 pedestrian counts an hour, about typical for these hours. Rain likely (up to 76% chance)."
      },
      "avoid": {
        "start": "2026-10-03T07:00:00+10:00",
        "end": "2026-10-03T09:00:00+10:00",
        "deltaPct": -13.4,
        "maxPrecipProb": 88,
        "reason": "Lowest forecast foot traffic: about 11,226 pedestrian counts an hour, 13% below typical. Rain likely (up to 88% chance)."
      }
    },
    "busyButDry": {
      "best": {
        "start": "2026-10-02T18:00:00+10:00",
        "end": "2026-10-02T20:00:00+10:00",
        "deltaPct": -6.1,
        "maxPrecipProb": 41,
        "reason": "Busiest dry hours: about 62,995 pedestrian counts an hour, 6% below typical. Rain unlikely (up to 41% chance)."
      },
      "secondBest": {
        "start": "2026-10-02T20:00:00+10:00",
        "end": "2026-10-02T22:00:00+10:00",
        "deltaPct": -2.8,
        "maxPrecipProb": 43,
        "reason": "Next-busiest dry hours: about 47,027 pedestrian counts an hour, about typical for these hours. Rain unlikely (up to 43% chance)."
      },
      "avoid": {
        "start": "2026-10-03T07:00:00+10:00",
        "end": "2026-10-03T09:00:00+10:00",
        "deltaPct": -13.4,
        "maxPrecipProb": 88,
        "reason": "Most likely to be wet: about 11,226 pedestrian counts an hour, 13% below typical. Rain likely (up to 88% chance)."
      }
    },
    "quietest": {
      "best": {
        "start": "2026-10-03T07:00:00+10:00",
        "end": "2026-10-03T09:00:00+10:00",
        "deltaPct": -13.4,
        "maxPrecipProb": 88,
        "reason": "Lowest forecast foot traffic: about 11,226 pedestrian counts an hour, 13% below typical. Rain likely (up to 88% chance)."
      },
      "secondBest": {
        "start": "2026-10-02T07:00:00+10:00",
        "end": "2026-10-02T09:00:00+10:00",
        "deltaPct": -19.9,
        "maxPrecipProb": 76,
        "reason": "Next-lowest forecast foot traffic: about 24,089 pedestrian counts an hour, 20% below typical. Rain likely (up to 76% chance)."
      },
      "avoid": {
        "start": "2026-10-02T16:00:00+10:00",
        "end": "2026-10-02T18:00:00+10:00",
        "deltaPct": -5.9,
        "maxPrecipProb": 54,
        "reason": "Highest forecast foot traffic: about 78,599 pedestrian counts an hour, 6% below typical. Rain likely (up to 54% chance)."
      }
    }
  }
}
```

---

### 2. `GET /api/plan/evidence`

Returns the statistical evidence behind the rain effect claims: forest plot rows (overall effect, intensity breakdowns, weekday vs weekend, temperature strata), hourly CBD-wide count profiles comparing matched wet vs dry hours, and sensor-by-sensor effect measurements.

#### Response Shape

```typescript
type EvidenceResponse = {
  generatedAt: string; // ISO 8601 UTC
  window: {
    start: string; // YYYY-MM-DD
    end: string; // YYYY-MM-DD
  } | null;
  computedAt: string | null; // ISO 8601 UTC
  forest: Array<{
    group: "overall" | "intensity" | "daytype" | "temperature";
    key: string;
    label: string;
    value: number; // Effect in % (-18.5 = 18.5% drop)
    ciLow: number | null; // 95% CI lower bound
    ciHigh: number | null; // 95% CI upper bound
    nWetHours: number;
    reliable: boolean;
  }>;
  profile: Array<{
    hour: number; // Local hour 0..23
    wet: number; // Average pedestrian count in wet hours
    dry: number; // Matched average pedestrian count in dry hours
    nWetHours: number;
  }>;
  sensors: Array<{
    id: number;
    name: string;
    lat: number | null;
    lon: number | null;
    value: number; // Sensor-specific effect in %
    ciLow: number | null;
    ciHigh: number | null;
    nWetHours: number;
    reliable: boolean;
  }>;
};
```

#### Example Real Response (`GET /api/plan/evidence`)

*Response Size: ~18.42 KB (18,857 bytes)*

```json
{
  "generatedAt": "2026-10-01T15:22:50.000Z",
  "window": {
    "start": "2025-09-30",
    "end": "2026-09-29"
  },
  "computedAt": "2026-10-01T14:57:13.459Z",
  "forest": [
    {
      "group": "overall",
      "key": "all",
      "label": "All wet hours",
      "value": -18.5,
      "ciLow": -21.8,
      "ciHigh": -14.4,
      "nWetHours": 876,
      "reliable": true
    },
    {
      "group": "intensity",
      "key": "light",
      "label": "Light rain (0.2 to 2 mm an hour)",
      "value": -17,
      "ciLow": -20.4,
      "ciHigh": -13.3,
      "nWetHours": 774,
      "reliable": true
    },
    {
      "group": "intensity",
      "key": "heavy",
      "label": "Heavy rain (2 mm an hour or more)",
      "value": -29.1,
      "ciLow": -35.1,
      "ciHigh": -21.2,
      "nWetHours": 102,
      "reliable": true
    },
    {
      "group": "daytype",
      "key": "weekday",
      "label": "Weekdays",
      "value": -18.3,
      "ciLow": -21.8,
      "ciHigh": -14.2,
      "nWetHours": 605,
      "reliable": true
    },
    {
      "group": "daytype",
      "key": "weekend",
      "label": "Weekends and public holidays",
      "value": -19.4,
      "ciLow": -24.4,
      "ciHigh": -13.5,
      "nWetHours": 271,
      "reliable": true
    },
    {
      "group": "temperature",
      "key": "cold",
      "label": "Cold (below 12 °C)",
      "value": -18.5,
      "ciLow": -22.7,
      "ciHigh": -13.9,
      "nWetHours": 435,
      "reliable": true
    },
    {
      "group": "temperature",
      "key": "mild",
      "label": "Mild (12 to 20 °C)",
      "value": -17.5,
      "ciLow": -21.7,
      "ciHigh": -12.4,
      "nWetHours": 395,
      "reliable": true
    },
    {
      "group": "temperature",
      "key": "warm",
      "label": "Warm (above 20 °C)",
      "value": -33.6,
      "ciLow": -42.8,
      "ciHigh": -20.9,
      "nWetHours": 46,
      "reliable": false
    }
  ],
  "profile": [
    { "hour": 0, "wet": 7131, "dry": 9603, "nWetHours": 29 },
    { "hour": 1, "wet": 5282, "dry": 6062, "nWetHours": 31 },
    { "hour": 12, "wet": 56024, "dry": 69324, "nWetHours": 42 }
  ],
  "sensors": [
    {
      "id": 11,
      "name": "Docklands Waterfront City Building Side",
      "lat": -37.81566651,
      "lon": 144.93974366,
      "value": -49.8,
      "ciLow": -54.6,
      "ciHigh": -43.2,
      "nWetHours": 876,
      "reliable": true
    },
    {
      "id": 29,
      "name": "St Kilda Rd-Alexandra Gardens",
      "lat": -37.8199817,
      "lon": 144.96872865,
      "value": -47.8,
      "ciLow": -55.8,
      "ciHigh": -38.2,
      "nWetHours": 872,
      "reliable": true
    }
  ]
}
```

---

### 3. `GET /api/plan/sensors`

Returns an array of sensors that currently have active forecasts, sorted alphabetically by name. Used for populating the sensor selector dropdown.

#### Response Shape

```json
{
  "sensors": [
    {
      "id": 1,
      "name": "Bourke Street Mall (North)",
      "lat": -37.81349441,
      "lon": 144.96515324
    },
    {
      "id": 2,
      "name": "Bourke Street Mall (South)",
      "lat": -37.8138067,
      "lon": 144.96516718
    }
  ]
}
```

---

## Error Responses

All error responses adhere to a standard JSON error envelope:

```json
{
  "error": "window must be one of: 12h, today, tomorrow, 36h"
}
```

| HTTP Status | Condition |
|---|---|
| `400 Bad Request` | Invalid `window` parameter or invalid `sensor` identifier format. |
| `404 Not Found` | Sensor is numeric but has no available forecast data. |
| `500 Internal Server Error` | Database connection error or missing `DATABASE_URL_READONLY`. |
