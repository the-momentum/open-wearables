# Unified Health Payload — Design Specification

## Table of Contents

1. [Comparison of raw structure per provider](#1-comparison-of-raw-structure-per-provider)
2. [Unified payload — structure](#2-unified-payload--structure)
3. [Records — types and mapping](#3-records--types-and-mapping)
4. [Workouts — structure and mapping](#4-workouts--structure-and-mapping)
5. [Sleep — structure and mapping](#5-sleep--structure-and-mapping)
6. [Data splitting per SDK](#6-data-splitting-per-sdk)
7. [Full payload example](#7-full-payload-example)

---

## 1. Comparison of raw structure per provider

### 1.1 Records — raw structure

| Field | Apple Health | Samsung Health | Health Connect |
|------|-------------|----------------|----------------|
| **ID** | `uuid` (string UUID) | `uid` (string) | `metadata.id` (string UUID) |
| **Type** | `type` string e.g. `"HKQuantityTypeIdentifierHeartRate"` | `dataType` string e.g. `"HEART_RATE"` | `type` string e.g. `"HeartRateRecord"` |
| **Start** | `startDate` ISO8601 | `startTime` epoch ms | `startTime` ISO8601 (or `time` for instant) |
| **End** | `endDate` ISO8601 | `endTime` epoch ms | `endTime` ISO8601 (or = `time`) |
| **Timezone** | none (UTC) | `zoneOffset` string `"+01:00"` | `startZoneOffset` / `endZoneOffset` string |
| **Value** | `value` number + `unit` string (1 value per record) | `values` object with named keys e.g. `{ "HEART_RATE": 72, "MIN_HEART_RATE": 68 }` | flat keys at top-level e.g. `percentage: 97.5`, `count: 3542`, `systolic: 121` |
| **Series data** | none (each reading = separate record) | `values.SERIES_DATA[]` e.g. `[{ timestamp, heartRate }]` | `samples[]` e.g. `[{ time, beatsPerMinute }]` |
| **Source app** | `source.bundleIdentifier` | `source.appId` | `metadata.dataOrigin.packageName` |
| **Device ID** | none | `device.deviceId` | none |
| **Device name** | `source.deviceName` | `device.name` | none |
| **Device manufacturer** | `source.deviceManufacturer` | `device.manufacturer` | `metadata.device.manufacturer` |
| **Device model** | `source.productType` e.g. `"Watch7,3"` | `device.model` e.g. `"SM-R960"` | `metadata.device.model` e.g. `"SM-R960"` |
| **Device type** | inferred from model (Watch→watch, iPhone→phone) | `device.deviceType` string `"WATCH"/"MOBILE"` | `metadata.device.type` int (1=watch, 2=phone, 3=scale...) |
| **Recording method** | none | none | `metadata.recordingMethod` int (1=active, 2=auto, 3=manual) |
| **OS version** | `source.operatingSystemVersion` object `{major,minor,patch}` | none | none |
| **App version** | `source.version` | none | none |
| **Client record ID** | none | `clientDataId` | `metadata.clientRecordId` |
| **Client version** | none | `clientVersion` | `metadata.clientRecordVersion` |
| **Last modified** | none | `updateTime` epoch ms | `metadata.lastModifiedTime` ISO8601 |
| **Metadata** | `recordMetadata[]` array of `{ key, value }` | none (values in `values` object) | none (individual fields at top-level e.g. `bodyPosition`, `specimenSource`) |
| **Multi-value records** | NO — blood pressure = 2 separate records (systolic + diastolic) | YES — e.g. `BLOOD_PRESSURE: { SYSTOLIC, DIASTOLIC, PULSE }`, `BODY_COMPOSITION: { WEIGHT, HEIGHT, BODY_FAT, ... }` | PARTIAL — blood pressure in one `{ systolic, diastolic }`, but weight/height/bodyFat = separate records |

### 1.2 Workouts — raw structure

| Field | Apple Health | Samsung Health | Health Connect |
|------|-------------|----------------|----------------|
| **ID** | `uuid` | `uid` | `metadata.id` |
| **Exercise type** | `type` string e.g. `"running"`, `"strength_training"` | `values.EXERCISE_TYPE` string e.g. `"RUNNING"` | `exerciseType` int e.g. `56`=running, `78`=strength |
| **Start/End** | `startDate`/`endDate` ISO8601 | `startTime`/`endTime` epoch ms | `startTime`/`endTime` ISO8601 |
| **Timezone** | none | `zoneOffset` | `startZoneOffset`/`endZoneOffset` |
| **Title** | none | `values.CUSTOM_TITLE` | `title` |
| **Notes** | none | `sessions[].comment` | `notes` |
| **Stats/Values** | `workoutStatistics[]` array of `{ type, value, unit }` | in `sessions[]` as flat keys: `calories`, `distance`, `meanHeartRate`, `maxHeartRate`... | none inline — **query separately** linked records (HeartRateRecord, DistanceRecord, etc. in time range) |
| **Sessions** | NO (1 workout = 1 continuous session) | YES — `sessions[]` (1 exercise → N sessions when paused) | NO (1 record = 1 session) |
| **Segments** | none (from HKWorkoutActivity separately) | none | `segments[]` with `{ startTime, endTime, segmentType: int, repetitions }` |
| **Laps** | none | none | `laps[]` with `{ startTime, endTime, length }` |
| **Route/GPS** | none inline — **separate HKWorkoutRoute object** must be fetched | `sessions[].route[]` with `{ timestamp, latitude, longitude, altitude, accuracy }` | `route.locations[]` with `{ time, latitude, longitude, altitude, horizontalAccuracy, verticalAccuracy }` |
| **Time-series log** | none | `sessions[].log[]` combined: `{ timestamp, heartRate, cadence, speed, power, count }` | none inline — **query separately** linked records |
| **Swimming log** | none | `sessions[].swimmingLog` | none |
| **Planned exercise** | none | none | `plannedExerciseSessionId` |
| **Has route flag** | none | none | `hasRoute` bool |
| **Source/Device** | `source` object (same as records) | `source` + `device` object (same as records) | `metadata` object (same as records) |

### 1.3 Sleep — raw structure

| Field | Apple Health | Samsung Health | Health Connect |
|------|-------------|----------------|----------------|
| **ID** | `uuid` (per stage!) | `uid` (per sleep record) | `metadata.id` (per session) |
| **Type** | `type` = `"HKCategoryTypeIdentifierSleepAnalysis"` | `dataType` = `"SLEEP"` | `type` = `"SleepSessionRecord"` |
| **Start/End** | per stage: `startDate`/`endDate` ISO8601 | per entire sleep: `startTime`/`endTime` epoch ms | per session: `startTime`/`endTime` ISO8601 |
| **Timezone** | none | `zoneOffset` | `startZoneOffset`/`endZoneOffset` |
| **Granularity** | **FLAT** — each stage = separate record in `sleep[]` | **NESTED** — 1 record → `sessions[]` → `stages[]` | **NESTED** — 1 record → `stages[]` |
| **Stage** | `value` int: 0=inBed, 1=asleepUnspecified, 2=awake, 3=core, 4=deep, 5=REM | `sessions[].stages[].stage` string: `"AWAKE"`, `"LIGHT"`, `"DEEP"`, `"REM"` | `stages[].type` int: 1=awake, 2=awakeInBed, 3=sleeping, 4=light, 5=deep, 6=REM |
| **Session grouping** | NONE — stages are loose, you must group by timestamps yourself | YES — `sessions[]` array (2 sessions = wake-up at night + going back to sleep) | NONE — 1 SleepSessionRecord = 1 session |
| **Duration** | none (calculate from start/end) | `values.DURATION` epoch ms | none (calculate from start/end) |
| **Sleep score** | none | `values.SLEEP_SCORE` int | none |
| **Title** | none | none | `title` |
| **Notes** | none | none | `notes` |
| **Source/Device** | `source` object (same as records) | `source` + `device` object (same as records) | `metadata` object (same as records) |
| **Metadata** | `recordMetadata[]` | none | none |

---

## 2. Unified payload — structure

### Rules

1. **Timestamps → ISO 8601 UTC** — Samsung SDK converts epoch ms to ISO8601
2. **1 record = 1 value + 1 unit** — Apple convention, no value arrays
3. **Flat data** — Samsung series/sessions/stages split into separate objects
4. **`parentId`** — links split data back to the original record/session
5. **null = unavailable** for a given provider

### Top-level

```json
{
  "provider": "apple_health | samsung_health | health_connect",
  "sdkVersion": "0.1.0",
  "syncTimestamp": "2026-02-18T12:00:00Z",
  "data": {
    "records": [],
    "workouts": [],
    "sleep": []
  }
}
```

### Source (per record/workout/sleep)

```json
{
  "appId": "string",
  "deviceId": "string | null",
  "deviceName": "string | null",
  "deviceManufacturer": "string | null",
  "deviceModel": "string | null",
  "deviceType": "watch | phone | scale | ring | fitness_band | chest_strap | head_mounted | smart_display | medical_device | unknown | null",
  "recordingMethod": "active | automatic | manual | unknown | null"
}
```

#### Source mapping

| Field | Apple Health | Samsung Health | Health Connect |
|------|-------------|----------------|----------------|
| `appId` | `source.bundleIdentifier` | `source.appId` | `metadata.dataOrigin.packageName` |
| `deviceId` | `null` | `device.deviceId` | `null` |
| `deviceName` | `source.deviceName` | `device.name` | `null` |
| `deviceManufacturer` | `source.deviceManufacturer` | `device.manufacturer` | `metadata.device.manufacturer` |
| `deviceModel` | `source.productType` | `device.model` | `metadata.device.model` |
| `deviceType` | infer from model | map `device.deviceType` | map `metadata.device.type` int |
| `recordingMethod` | `null` | `null` | map `metadata.recordingMethod` int |

---

## 3. Records — types and mapping

### Record structure (10 keys, always)

```json
{
  "id": "string",
  "type": "string",
  "startDate": "ISO8601",
  "endDate": "ISO8601",
  "zoneOffset": "string | null",
  "source": { },
  "value": "number",
  "unit": "string",
  "parentId": "string | null",
  "metadata": "{ } | null"
}
```

### Record types

| Record `type` | `unit` | Apple Health | Samsung Health | Health Connect |
|---|---|---|---|---|
| `step_count` | `count` | `HKQuantityTypeIdentifierStepCount` → `value` | step tracker | `StepsRecord` → `count` |
| `heart_rate` | `bpm` | `HKQuantityTypeIdentifierHeartRate` → `value` (single reading) | `HEART_RATE` → split `SERIES_DATA[]` into separate records | `HeartRateRecord` → split `samples[]` into separate records |
| `resting_heart_rate` | `bpm` | `HKQuantityTypeIdentifierRestingHeartRate` | ❌ none | `RestingHeartRateRecord` |
| `heart_rate_variability` | `ms` | `HKQuantityTypeIdentifierHeartRateVariabilitySDNN`, metadata: `{ "method": "sdnn" }` | ❌ none | `HeartRateVariabilityRmssdRecord`, metadata: `{ "method": "rmssd" }` |
| `oxygen_saturation` | `%` | `HKQuantityTypeIdentifierOxygenSaturation` — **×100!** (Apple returns 0–1) | `BLOOD_OXYGEN` → `OXYGEN_SATURATION` | `OxygenSaturationRecord` → `percentage` |
| `blood_pressure_systolic` | `mmHg` | `HKQuantityTypeIdentifierBloodPressureSystolic` (already separate) | `BLOOD_PRESSURE` → split, `SYSTOLIC` | `BloodPressureRecord` → split, `systolic` |
| `blood_pressure_diastolic` | `mmHg` | `HKQuantityTypeIdentifierBloodPressureDiastolic` (already separate) | `BLOOD_PRESSURE` → split, `DIASTOLIC` | `BloodPressureRecord` → split, `diastolic` |
| `blood_glucose` | `mmol/L` | `HKQuantityTypeIdentifierBloodGlucose` | `BLOOD_GLUCOSE` → `LEVEL` — **÷18.0182** (Samsung returns mg/dL) | `BloodGlucoseRecord` → `level` |
| `active_calories_burned` | `kcal` | `HKQuantityTypeIdentifierActiveEnergyBurned` | from activity summary | `ActiveCaloriesBurnedRecord` → `energy` |
| `basal_calories_burned` | `kcal` | `HKQuantityTypeIdentifierBasalEnergyBurned` | from body composition | `BasalCaloriesBurnedRecord` |
| `body_temperature` | `°C` | `HKQuantityTypeIdentifierBodyTemperature` | `BODY_TEMPERATURE` → `TEMPERATURE` | `BodyTemperatureRecord` → `temperature` |
| `weight` | `kg` | `HKQuantityTypeIdentifierBodyMass` | `BODY_COMPOSITION` → split, `WEIGHT` | `WeightRecord` → `weight` |
| `height` | `m` | `HKQuantityTypeIdentifierHeight` | `BODY_COMPOSITION` → split, `HEIGHT` — **÷100** (Samsung returns cm) | `HeightRecord` → `height` |
| `body_fat` | `%` | `HKQuantityTypeIdentifierBodyFatPercentage` | `BODY_COMPOSITION` → split, `BODY_FAT` | `BodyFatRecord` → `percentage` |
| `body_fat_mass` | `kg` | ❌ none | `BODY_COMPOSITION` → split, `BODY_FAT_MASS` | ❌ none |
| `lean_body_mass` | `kg` | `HKQuantityTypeIdentifierLeanBodyMass` | `BODY_COMPOSITION` → split, `FAT_FREE_MASS` | `LeanBodyMassRecord` → `mass` |
| `skeletal_muscle_mass` | `kg` | ❌ none | `BODY_COMPOSITION` → split, `SKELETAL_MUSCLE_MASS` | ❌ none |
| `bmi` | `kg/m²` | `HKQuantityTypeIdentifierBodyMassIndex` | `BODY_COMPOSITION` → split, `BMI` | ❌ none |
| `basal_metabolic_rate` | `kcal/day` | `HKQuantityTypeIdentifierBasalEnergyBurned` | `BODY_COMPOSITION` → split, `BASAL_METABOLIC_RATE` | `BasalMetabolicRateRecord` → `basalMetabolicRate` |
| `floors_climbed` | `count` | `HKQuantityTypeIdentifierFlightsClimbed` | `FLOORS_CLIMBED` → `FLOORS` | `FloorsClimbedRecord` → `floors` |
| `distance` | `m` | `HKQuantityTypeIdentifierDistanceWalkingRunning` | from exercise/tracker | `DistanceRecord` → `distance` |
| `hydration` | `mL` | `HKQuantityTypeIdentifierDietaryWater` | `WATER_INTAKE` → `VOLUME` (already mL) | `HydrationRecord` → `volume` — **×1000** (HC returns liters) |
| `vo2_max` | `mL/kg/min` | `HKQuantityTypeIdentifierVO2Max` | from workout session | `Vo2MaxRecord` |

### Metadata per record type

| Record type | Possible keys in `metadata` |
|---|---|
| `heart_rate` | `motionContext`: `"sedentary"` / `"active"` |
| `heart_rate_variability` | `method`: `"sdnn"` / `"rmssd"` |
| `blood_pressure_systolic` / `_diastolic` | `bodyPosition`: `"sitting"` / `"standing"` / `"lying_down"`, `measurementLocation`: `"left_upper_arm"` / `"left_wrist"` / `"right_wrist"` |
| `blood_glucose` | `specimenSource`: `"interstitial_fluid"` / `"capillary_blood"` / `"whole_blood"` / ..., `relationToMeal`: `"fasting"` / `"before_meal"` / `"after_meal"` / ..., `measurementType`: string |
| `body_temperature` | `measurementLocation`: `"wrist"` / `"mouth"` / `"ear"` / `"forehead"` / ... |

---

## 4. Workouts — structure and mapping

### Workout structure (15 keys, always)

```json
{
  "id": "string",
  "parentId": "string | null",
  "type": "string",
  "startDate": "ISO8601",
  "endDate": "ISO8601",
  "zoneOffset": "string | null",
  "source": { },
  "title": "string | null",
  "notes": "string | null",
  "values": [{ "type": "string", "value": "number", "unit": "string" }],
  "segments": "[ ] | null",
  "laps": "[ ] | null",
  "route": "[ ] | null",
  "samples": "[ ] | null",
  "metadata": "{ } | null"
}
```

### Workout type mapping

| Unified | Apple (`type`) | Samsung (`EXERCISE_TYPE`) | Health Connect (`exerciseType`) |
|---------|----------------|---------------------------|-------------------------------|
| `running` | `"running"` | `"RUNNING"` | `56` |
| `strength_training` | `"strength_training"` | `"STRENGTH_TRAINING"` | `78` |
| `cycling` | `"cycling"` | `"BIKING"` | `8` |
| `swimming` | `"swimming"` | `"SWIMMING"` | `75` |
| `hiking` | `"hiking"` | `"HIKING"` | `29` |
| `walking` | `"walking"` | `"WALKING"` | `79` |
| `yoga` | `"yoga"` | `"YOGA"` | `84` |

### Workout values — available `type`

| `values[].type` | `unit` | Apple | Samsung | Health Connect |
|---|---|:---:|:---:|:---:|
| `duration` | `s` | ✅ | ✅ | ✅ calculate from start/end |
| `activeCalories` | `kcal` | ✅ | ✅ | ✅ linked record |
| `basalCalories` | `kcal` | ✅ | ❌ | ❌ |
| `distance` | `m` | ✅ | ✅ | ✅ linked record |
| `stepCount` | `count` | ✅ | ❌ | ✅ linked record |
| `avgHeartRate` | `bpm` | ✅ | ✅ | ✅ linked record |
| `minHeartRate` | `bpm` | ✅ | ✅ | ✅ linked record |
| `maxHeartRate` | `bpm` | ✅ | ✅ | ✅ linked record |
| `avgSpeed` | `m/s` | ✅ | ✅ | ✅ linked record |
| `maxSpeed` | `m/s` | ❌ | ✅ | ❌ |
| `avgCadence` | `spm` | ❌ | ✅ | ❌ |
| `maxCadence` | `spm` | ❌ | ✅ | ❌ |
| `avgPower` | `W` | ✅ (running power) | ❌ | ✅ linked record |
| `avgStrideLength` | `m` | ✅ | ❌ | ❌ |
| `avgVerticalOscillation` | `cm` | ✅ | ❌ | ❌ |
| `avgGroundContactTime` | `ms` | ✅ | ❌ | ❌ |
| `elevationGain` | `m` | ✅ | ✅ | ✅ linked record |
| `elevationLoss` | `m` | ✅ | ✅ | ❌ |
| `maxAltitude` | `m` | ❌ | ✅ | ❌ |
| `minAltitude` | `m` | ❌ | ✅ | ❌ |
| `vo2Max` | `mL/kg/min` | ❌ | ✅ | ❌ |
| `avgCalorieBurnRate` | `kcal/min` | ❌ | ✅ | ❌ |
| `maxCalorieBurnRate` | `kcal/min` | ❌ | ✅ | ❌ |
| `weatherTemperature` | `°C` | ✅ | ❌ | ❌ |
| `weatherHumidity` | `%` | ✅ | ❌ | ❌ |
| `isIndoor` | `bool` | ✅ (0/1) | ❌ | ❌ |

### Segment type mapping

| Unified | Samsung (session log) | Health Connect (`segmentType`) |
|---------|----------------------|-------------------------------|
| `warmup` / `stretching` | inferred | `66` |
| `running` | from exerciseType | `55` |
| `cooldown` | inferred | `19` |
| `bench_press` | — | `7` |
| `squat` | — | `64` |
| `deadlift` | — | `22` |

### Sub-structures

**segments[]:**
```json
{ "startDate": "ISO8601", "endDate": "ISO8601", "type": "string", "repetitions": "int | null" }
```

**laps[]:**
```json
{ "startDate": "ISO8601", "endDate": "ISO8601", "distanceM": "number" }
```

**route[]:**
```json
{ "timestamp": "ISO8601", "latitude": "number", "longitude": "number", "altitudeM": "number", "horizontalAccuracyM": "number", "verticalAccuracyM": "number" }
```

**samples[]:**
```json
{ "timestamp": "ISO8601", "type": "heartRate | cadence | speed | power", "value": "number", "unit": "bpm | spm | m/s | W" }
```

### Workout flattening — Samsung sessions

Samsung `sessions[]` → each session becomes a separate workout with `parentId` = original exercise UID.

```
Samsung raw:
  exercise (uid: "wrk-001")
    └─ sessions[0] (start: 06:30, end: 07:15)
    └─ sessions[1] (start: 08:00, end: 08:45)

Unified:
  workout { id: "wrk-001-s0", parentId: "wrk-001", start: 06:30, end: 07:15 }
  workout { id: "wrk-001-s1", parentId: "wrk-001", start: 08:00, end: 08:45 }
```

Apple and Health Connect: `parentId = null` (1 workout = 1 session).

---

## 5. Sleep — structure and mapping

### Sleep structure (9 keys, always)

Each entry = **one stage** (not a session). Samsung and HC split sessions into chunks.

```json
{
  "id": "string",
  "parentId": "string | null",
  "stage": "awake | light | deep | rem | in_bed | sleeping | unknown",
  "startDate": "ISO8601",
  "endDate": "ISO8601",
  "zoneOffset": "string | null",
  "source": { },
  "values": "[ ] | null",
  "metadata": "{ } | null"
}
```

### Stage mapping

| Unified | Apple (`value`) | Samsung (`stage`) | Health Connect (`type`) |
|---------|:---:|:---:|:---:|
| `in_bed` | `0` | — | `2` (AWAKE_IN_BED) |
| `sleeping` | `1` (asleepUnspecified) | — | `3` (SLEEPING) |
| `awake` | `2` | `"AWAKE"` | `1` (AWAKE) |
| `light` | `3` (asleepCore) | `"LIGHT"` | `4` (LIGHT) |
| `deep` | `4` | `"DEEP"` | `5` (DEEP) |
| `rem` | `5` | `"REM"` | `6` (REM) |
| `unknown` | — | — | `0` (UNKNOWN) |

### Sleep flattening per provider

**Apple Health** — no work needed, already comes in chunks:
```
raw: sleep[0] = { uuid: "AAA", value: 3, start: "22:45", end: "00:45" }
     sleep[1] = { uuid: "BBB", value: 5, start: "00:45", end: "01:30" }

unified: sleep[0] = { id: "AAA", parentId: null, stage: "light", start: "22:45", end: "00:45" }
         sleep[1] = { id: "BBB", parentId: null, stage: "rem",   start: "00:45", end: "01:30" }
```

**Samsung Health** — split sessions → stages:
```
raw: sleep.sessions[0].stages = [
       { stage: "LIGHT", start: "22:58", end: "23:25" },
       { stage: "DEEP",  start: "23:25", end: "00:10" }
     ]

unified: sleep[0] = { id: "slp-001-s0-0", parentId: "slp-001", stage: "light", ... }
         sleep[1] = { id: "slp-001-s0-1", parentId: "slp-001", stage: "deep", ... }
```

Samsung `sleepScore` → `values: [{ "type": "sleepScore", "value": 82, "unit": "score" }]` on each chunk.

**Health Connect** — split stages:
```
raw: stages = [
       { type: 4, startTime: "22:58", endTime: "23:25" },
       { type: 5, startTime: "23:25", endTime: "00:10" }
     ]

unified: sleep[0] = { id: "...-0", parentId: "99999999-...", stage: "light", ... }
         sleep[1] = { id: "...-1", parentId: "99999999-...", stage: "deep", ... }
```

---

## 6. Data splitting per SDK

### What the SDK must split

| Raw data | Apple Health | Samsung Health | Health Connect |
|----------|:---:|:---:|:---:|
| HR series → separate records | Already split | `SERIES_DATA[]` → N × record, parentId = UID | `samples[]` → N × record, parentId = metadata.id |
| Blood pressure → systolic + diastolic | Already split | 1 record → 2 records, parentId = UID | 1 record → 2 records, parentId = metadata.id |
| Body composition → separate records | N/A | 1 record → 7 records, parentId = UID | Already split |
| Workout sessions → separate workouts | Already flat | `sessions[]` → N × workout, parentId = exercise UID | Already flat |
| Sleep stages → separate chunks | Already flat | `sessions[].stages[]` → N × sleep, parentId = sleep UID | `stages[]` → N × sleep, parentId = metadata.id |

### Unit conversions per SDK

| Conversion | Applies to SDK |
|-----------|-------------|
| SpO2: `value × 100` (0–1 → 0–100%) | Apple Health |
| Blood glucose: `value ÷ 18.0182` (mg/dL → mmol/L) | Samsung Health |
| Height: `value ÷ 100` (cm → m) | Samsung Health |
| Hydration: `value × 1000` (L → mL) | Health Connect |
| Timestamps: epoch ms → ISO8601 UTC | Samsung Health |
| Int enums → string enums (exerciseType, segmentType, deviceType, stageType, etc.) | Health Connect |

---

## 7. Full payload example

> **`type` = native name from the SDK provider.** The backend maps by `provider` + `type`.
> For records split from composite (Samsung body_composition, blood_pressure) → `metadata.component` indicates which value.

### 7.1 Example — Apple Health

```json
{
  "provider": "apple_health",
  "sdkVersion": "0.1.0",
  "syncTimestamp": "2026-02-18T12:00:00Z",
  "data": {
    "records": [
      {
        "id": "11111111-2222-3333-4444-555555555555",
        "type": "HKQuantityTypeIdentifierStepCount",
        "startDate": "2026-02-18T08:00:00Z",
        "endDate": "2026-02-18T09:00:00Z",
        "zoneOffset": null,
        "source": { "appId": "com.apple.health", "deviceId": null, "deviceName": "iPhone", "deviceManufacturer": "Apple Inc.", "deviceModel": "iPhone16,2", "deviceType": "phone", "recordingMethod": null },
        "value": 1847,
        "unit": "count",
        "parentId": null,
        "metadata": null
      },
      {
        "id": "22222222-3333-4444-5555-666666666666",
        "type": "HKQuantityTypeIdentifierHeartRate",
        "startDate": "2026-02-18T10:05:00Z",
        "endDate": "2026-02-18T10:05:00Z",
        "zoneOffset": null,
        "source": { "appId": "com.apple.health.81A3FE2B", "deviceId": null, "deviceName": "Apple Watch", "deviceManufacturer": "Apple Inc.", "deviceModel": "Watch7,3", "deviceType": "watch", "recordingMethod": null },
        "value": 72.0,
        "unit": "count/min",
        "parentId": null,
        "metadata": { "HKMetadataKeyHeartRateMotionContext": "1" }
      },
      {
        "id": "33333333-4444-5555-6666-777777777777",
        "type": "HKQuantityTypeIdentifierActiveEnergyBurned",
        "startDate": "2026-02-18T09:00:00Z",
        "endDate": "2026-02-18T10:00:00Z",
        "zoneOffset": null,
        "source": { "appId": "com.apple.health.81A3FE2B", "deviceId": null, "deviceName": "Apple Watch", "deviceManufacturer": "Apple Inc.", "deviceModel": "Watch7,3", "deviceType": "watch", "recordingMethod": null },
        "value": 42.5,
        "unit": "kcal",
        "parentId": null,
        "metadata": null
      },
      {
        "id": "44444444-5555-6666-7777-888888888888",
        "type": "HKQuantityTypeIdentifierOxygenSaturation",
        "startDate": "2026-02-18T03:22:00Z",
        "endDate": "2026-02-18T03:22:00Z",
        "zoneOffset": null,
        "source": { "appId": "com.apple.health.81A3FE2B", "deviceId": null, "deviceName": "Apple Watch", "deviceManufacturer": "Apple Inc.", "deviceModel": "Watch7,3", "deviceType": "watch", "recordingMethod": null },
        "value": 97.0,
        "unit": "%",
        "parentId": null,
        "metadata": null
      },
      {
        "id": "55555555-6666-7777-8888-999999999999",
        "type": "HKQuantityTypeIdentifierBloodPressureSystolic",
        "startDate": "2026-02-18T08:30:00Z",
        "endDate": "2026-02-18T08:30:00Z",
        "zoneOffset": null,
        "source": { "appId": "com.withings.wiScaleNG", "deviceId": null, "deviceName": null, "deviceManufacturer": "Withings", "deviceModel": "BPM Connect", "deviceType": "medical_device", "recordingMethod": null },
        "value": 118.0,
        "unit": "mmHg",
        "parentId": null,
        "metadata": null
      },
      {
        "id": "66666666-7777-8888-9999-AAAAAAAAAAAA",
        "type": "HKQuantityTypeIdentifierBloodPressureDiastolic",
        "startDate": "2026-02-18T08:30:00Z",
        "endDate": "2026-02-18T08:30:00Z",
        "zoneOffset": null,
        "source": { "appId": "com.withings.wiScaleNG", "deviceId": null, "deviceName": null, "deviceManufacturer": "Withings", "deviceModel": "BPM Connect", "deviceType": "medical_device", "recordingMethod": null },
        "value": 76.0,
        "unit": "mmHg",
        "parentId": null,
        "metadata": null
      },
      {
        "id": "77777777-8888-9999-AAAA-BBBBBBBBBBBB",
        "type": "HKQuantityTypeIdentifierRestingHeartRate",
        "startDate": "2026-02-18T00:00:00Z",
        "endDate": "2026-02-18T00:00:00Z",
        "zoneOffset": null,
        "source": { "appId": "com.apple.health.81A3FE2B", "deviceId": null, "deviceName": "Apple Watch", "deviceManufacturer": "Apple Inc.", "deviceModel": "Watch7,3", "deviceType": "watch", "recordingMethod": null },
        "value": 54.0,
        "unit": "count/min",
        "parentId": null,
        "metadata": null
      },
      {
        "id": "88888888-9999-AAAA-BBBB-CCCCCCCCCCCC",
        "type": "HKQuantityTypeIdentifierHeartRateVariabilitySDNN",
        "startDate": "2026-02-18T03:15:00Z",
        "endDate": "2026-02-18T03:15:00Z",
        "zoneOffset": null,
        "source": { "appId": "com.apple.health.81A3FE2B", "deviceId": null, "deviceName": "Apple Watch", "deviceManufacturer": "Apple Inc.", "deviceModel": "Watch7,3", "deviceType": "watch", "recordingMethod": null },
        "value": 42.5,
        "unit": "ms",
        "parentId": null,
        "metadata": null
      }
    ],
    "workouts": [
      {
        "id": "A1B2C3D4-E5F6-7890-ABCD-EF1234567890",
        "parentId": null,
        "type": "HKWorkoutActivityTypeRunning",
        "startDate": "2026-02-18T07:00:00Z",
        "endDate": "2026-02-18T07:42:00Z",
        "zoneOffset": null,
        "source": { "appId": "com.apple.health.81A3FE2B", "deviceId": null, "deviceName": "Apple Watch", "deviceManufacturer": "Apple Inc.", "deviceModel": "Watch7,3", "deviceType": "watch", "recordingMethod": "active" },
        "title": null,
        "notes": null,
        "values": [
          { "type": "duration", "value": 2520.0, "unit": "s" },
          { "type": "activeEnergyBurned", "value": 385.7, "unit": "kcal" },
          { "type": "basalEnergyBurned", "value": 62.3, "unit": "kcal" },
          { "type": "distance", "value": 5840.0, "unit": "m" },
          { "type": "stepCount", "value": 5120, "unit": "count" },
          { "type": "minHeartRate", "value": 102.0, "unit": "bpm" },
          { "type": "averageHeartRate", "value": 158.0, "unit": "bpm" },
          { "type": "maxHeartRate", "value": 182.0, "unit": "bpm" },
          { "type": "averageRunningPower", "value": 260.0, "unit": "W" },
          { "type": "averageRunningSpeed", "value": 3.86, "unit": "m/s" },
          { "type": "averageRunningStrideLength", "value": 1.15, "unit": "m" },
          { "type": "averageVerticalOscillation", "value": 9.2, "unit": "cm" },
          { "type": "averageGroundContactTime", "value": 238.0, "unit": "ms" },
          { "type": "elevationAscended", "value": 45.0, "unit": "m" },
          { "type": "elevationDescended", "value": 42.0, "unit": "m" },
          { "type": "indoorWorkout", "value": 0, "unit": "bool" },
          { "type": "weatherTemperature", "value": 4.5, "unit": "degC" },
          { "type": "weatherHumidity", "value": 78.0, "unit": "%" }
        ],
        "segments": null,
        "laps": null,
        "route": null,
        "samples": null,
        "metadata": null
      }
    ],
    "sleep": [
      {
        "id": "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE",
        "parentId": null,
        "stage": "light",
        "startDate": "2026-02-17T23:12:00Z",
        "endDate": "2026-02-18T00:45:00Z",
        "zoneOffset": null,
        "source": { "appId": "com.apple.health.81A3FE2B", "deviceId": null, "deviceName": "Apple Watch", "deviceManufacturer": "Apple Inc.", "deviceModel": "Watch7,3", "deviceType": "watch", "recordingMethod": "automatic" },
        "values": null,
        "metadata": null
      },
      {
        "id": "BBBBBBBB-CCCC-DDDD-EEEE-FFFFFFFFFFFF",
        "parentId": null,
        "stage": "rem",
        "startDate": "2026-02-18T00:45:00Z",
        "endDate": "2026-02-18T01:30:00Z",
        "zoneOffset": null,
        "source": { "appId": "com.apple.health.81A3FE2B", "deviceId": null, "deviceName": "Apple Watch", "deviceManufacturer": "Apple Inc.", "deviceModel": "Watch7,3", "deviceType": "watch", "recordingMethod": "automatic" },
        "values": null,
        "metadata": null
      },
      {
        "id": "CCCCCCCC-DDDD-EEEE-FFFF-111111111111",
        "parentId": null,
        "stage": "deep",
        "startDate": "2026-02-18T01:30:00Z",
        "endDate": "2026-02-18T02:15:00Z",
        "zoneOffset": null,
        "source": { "appId": "com.apple.health.81A3FE2B", "deviceId": null, "deviceName": "Apple Watch", "deviceManufacturer": "Apple Inc.", "deviceModel": "Watch7,3", "deviceType": "watch", "recordingMethod": "automatic" },
        "values": null,
        "metadata": null
      }
    ]
  }
}
```

### 7.2 Example — Samsung Health

```json
{
  "provider": "samsung_health",
  "sdkVersion": "0.1.0",
  "syncTimestamp": "2026-02-18T12:00:00Z",
  "data": {
    "records": [
      {
        "id": "abc-111-def-s0",
        "type": "HEART_RATE",
        "startDate": "2026-02-18T10:01:00Z",
        "endDate": "2026-02-18T10:01:00Z",
        "zoneOffset": "+01:00",
        "source": { "appId": "com.sec.android.app.shealth", "deviceId": "R9ZW30ABC12", "deviceName": "Galaxy Watch7", "deviceManufacturer": "Samsung", "deviceModel": "SM-R960", "deviceType": "watch", "recordingMethod": "automatic" },
        "value": 72.0,
        "unit": "bpm",
        "parentId": "abc-111-def",
        "metadata": null
      },
      {
        "id": "abc-111-def-s1",
        "type": "HEART_RATE",
        "startDate": "2026-02-18T10:01:10Z",
        "endDate": "2026-02-18T10:01:10Z",
        "zoneOffset": "+01:00",
        "source": { "appId": "com.sec.android.app.shealth", "deviceId": "R9ZW30ABC12", "deviceName": "Galaxy Watch7", "deviceManufacturer": "Samsung", "deviceModel": "SM-R960", "deviceType": "watch", "recordingMethod": "automatic" },
        "value": 68.0,
        "unit": "bpm",
        "parentId": "abc-111-def",
        "metadata": null
      },
      {
        "id": "abc-222-def",
        "type": "BLOOD_OXYGEN",
        "startDate": "2026-02-18T10:15:00Z",
        "endDate": "2026-02-18T10:15:00Z",
        "zoneOffset": "+01:00",
        "source": { "appId": "com.sec.android.app.shealth", "deviceId": "R9ZW30ABC12", "deviceName": "Galaxy Watch7", "deviceManufacturer": "Samsung", "deviceModel": "SM-R960", "deviceType": "watch", "recordingMethod": "automatic" },
        "value": 97.0,
        "unit": "%",
        "parentId": null,
        "metadata": null
      },
      {
        "id": "abc-333-def",
        "type": "BLOOD_GLUCOSE",
        "startDate": "2026-02-18T10:30:00Z",
        "endDate": "2026-02-18T10:30:00Z",
        "zoneOffset": "+01:00",
        "source": { "appId": "com.example.glucosetracker", "deviceId": "RFCW123XYZ", "deviceName": "Galaxy S25 Ultra", "deviceManufacturer": "Samsung", "deviceModel": "SM-S928B", "deviceType": "phone", "recordingMethod": null },
        "value": 5.27,
        "unit": "mmol/L",
        "parentId": null,
        "metadata": { "mealStatus": "AFTER_MEAL", "measurementType": "WHOLE_BLOOD", "sampleSourceType": "FINGER_TIP" }
      },
      {
        "id": "abc-444-def-sys",
        "type": "BLOOD_PRESSURE",
        "startDate": "2026-02-18T11:00:00Z",
        "endDate": "2026-02-18T11:00:00Z",
        "zoneOffset": "+01:00",
        "source": { "appId": "com.sec.android.app.shealth", "deviceId": "R9ZW30ABC12", "deviceName": "Galaxy Watch7", "deviceManufacturer": "Samsung", "deviceModel": "SM-R960", "deviceType": "watch", "recordingMethod": "automatic" },
        "value": 122.0,
        "unit": "mmHg",
        "parentId": "abc-444-def",
        "metadata": { "component": "SYSTOLIC" }
      },
      {
        "id": "abc-444-def-dia",
        "type": "BLOOD_PRESSURE",
        "startDate": "2026-02-18T11:00:00Z",
        "endDate": "2026-02-18T11:00:00Z",
        "zoneOffset": "+01:00",
        "source": { "appId": "com.sec.android.app.shealth", "deviceId": "R9ZW30ABC12", "deviceName": "Galaxy Watch7", "deviceManufacturer": "Samsung", "deviceModel": "SM-R960", "deviceType": "watch", "recordingMethod": "automatic" },
        "value": 78.0,
        "unit": "mmHg",
        "parentId": "abc-444-def",
        "metadata": { "component": "DIASTOLIC" }
      },
      {
        "id": "abc-555-def",
        "type": "BODY_TEMPERATURE",
        "startDate": "2026-02-18T11:10:00Z",
        "endDate": "2026-02-18T11:10:00Z",
        "zoneOffset": "+01:00",
        "source": { "appId": "com.sec.android.app.shealth", "deviceId": "R9ZW30ABC12", "deviceName": "Galaxy Watch7", "deviceManufacturer": "Samsung", "deviceModel": "SM-R960", "deviceType": "watch", "recordingMethod": "automatic" },
        "value": 36.6,
        "unit": "°C",
        "parentId": null,
        "metadata": null
      },
      {
        "id": "abc-666-def",
        "type": "FLOORS_CLIMBED",
        "startDate": "2026-02-18T09:00:00Z",
        "endDate": "2026-02-18T10:00:00Z",
        "zoneOffset": "+01:00",
        "source": { "appId": "com.sec.android.app.shealth", "deviceId": "R9ZW30ABC12", "deviceName": "Galaxy Watch7", "deviceManufacturer": "Samsung", "deviceModel": "SM-R960", "deviceType": "watch", "recordingMethod": "automatic" },
        "value": 7,
        "unit": "count",
        "parentId": null,
        "metadata": null
      },
      {
        "id": "abc-777-def-weight",
        "type": "BODY_COMPOSITION",
        "startDate": "2026-02-18T06:50:00Z",
        "endDate": "2026-02-18T06:50:00Z",
        "zoneOffset": "+01:00",
        "source": { "appId": "com.sec.android.app.shealth", "deviceId": "RFCW123XYZ", "deviceName": "Galaxy S25 Ultra", "deviceManufacturer": "Samsung", "deviceModel": "SM-S928B", "deviceType": "phone", "recordingMethod": null },
        "value": 78.5,
        "unit": "kg",
        "parentId": "abc-777-def",
        "metadata": { "component": "WEIGHT" }
      },
      {
        "id": "abc-777-def-height",
        "type": "BODY_COMPOSITION",
        "startDate": "2026-02-18T06:50:00Z",
        "endDate": "2026-02-18T06:50:00Z",
        "zoneOffset": "+01:00",
        "source": { "appId": "com.sec.android.app.shealth", "deviceId": "RFCW123XYZ", "deviceName": "Galaxy S25 Ultra", "deviceManufacturer": "Samsung", "deviceModel": "SM-S928B", "deviceType": "phone", "recordingMethod": null },
        "value": 1.80,
        "unit": "m",
        "parentId": "abc-777-def",
        "metadata": { "component": "HEIGHT" }
      },
      {
        "id": "abc-777-def-bf",
        "type": "BODY_COMPOSITION",
        "startDate": "2026-02-18T06:50:00Z",
        "endDate": "2026-02-18T06:50:00Z",
        "zoneOffset": "+01:00",
        "source": { "appId": "com.sec.android.app.shealth", "deviceId": "RFCW123XYZ", "deviceName": "Galaxy S25 Ultra", "deviceManufacturer": "Samsung", "deviceModel": "SM-S928B", "deviceType": "phone", "recordingMethod": null },
        "value": 18.5,
        "unit": "%",
        "parentId": "abc-777-def",
        "metadata": { "component": "BODY_FAT" }
      },
      {
        "id": "abc-777-def-smm",
        "type": "BODY_COMPOSITION",
        "startDate": "2026-02-18T06:50:00Z",
        "endDate": "2026-02-18T06:50:00Z",
        "zoneOffset": "+01:00",
        "source": { "appId": "com.sec.android.app.shealth", "deviceId": "RFCW123XYZ", "deviceName": "Galaxy S25 Ultra", "deviceManufacturer": "Samsung", "deviceModel": "SM-S928B", "deviceType": "phone", "recordingMethod": null },
        "value": 35.2,
        "unit": "kg",
        "parentId": "abc-777-def",
        "metadata": { "component": "SKELETAL_MUSCLE_MASS" }
      },
      {
        "id": "abc-888-def",
        "type": "WATER_INTAKE",
        "startDate": "2026-02-18T08:00:00Z",
        "endDate": "2026-02-18T08:00:00Z",
        "zoneOffset": "+01:00",
        "source": { "appId": "com.sec.android.app.shealth", "deviceId": "RFCW123XYZ", "deviceName": "Galaxy S25 Ultra", "deviceManufacturer": "Samsung", "deviceModel": "SM-S928B", "deviceType": "phone", "recordingMethod": null },
        "value": 250.0,
        "unit": "mL",
        "parentId": null,
        "metadata": null
      }
    ],
    "workouts": [
      {
        "id": "wrk-001-xyz-s0",
        "parentId": "wrk-001-xyz",
        "type": "EXERCISE",
        "startDate": "2026-02-18T06:46:40Z",
        "endDate": "2026-02-18T07:46:40Z",
        "zoneOffset": "+01:00",
        "source": { "appId": "com.sec.android.app.shealth", "deviceId": "R9ZW30ABC12", "deviceName": "Galaxy Watch7", "deviceManufacturer": "Samsung", "deviceModel": "SM-R960", "deviceType": "watch", "recordingMethod": "active" },
        "title": null,
        "notes": "Morning run in the park",
        "values": [
          { "type": "duration", "value": 3480000, "unit": "ms" },
          { "type": "calories", "value": 345.5, "unit": "kcal" },
          { "type": "distance", "value": 5234.0, "unit": "m" },
          { "type": "meanHeartRate", "value": 142.3, "unit": "bpm" },
          { "type": "maxHeartRate", "value": 178.0, "unit": "bpm" },
          { "type": "minHeartRate", "value": 95.0, "unit": "bpm" },
          { "type": "meanSpeed", "value": 1.50, "unit": "m/s" },
          { "type": "maxSpeed", "value": 3.20, "unit": "m/s" },
          { "type": "meanCadence", "value": 165.0, "unit": "spm" },
          { "type": "maxCadence", "value": 182.0, "unit": "spm" },
          { "type": "altitudeGain", "value": 45.0, "unit": "m" },
          { "type": "altitudeLoss", "value": 42.0, "unit": "m" },
          { "type": "maxAltitude", "value": 185.0, "unit": "m" },
          { "type": "minAltitude", "value": 140.0, "unit": "m" },
          { "type": "vo2Max", "value": 42.5, "unit": "mL/kg/min" }
        ],
        "segments": null,
        "laps": null,
        "route": [
          { "timestamp": "2026-02-18T06:47:40Z", "latitude": 52.229676, "longitude": 21.012229, "altitudeM": 142.0, "horizontalAccuracyM": 3.5, "verticalAccuracyM": null },
          { "timestamp": "2026-02-18T06:48:40Z", "latitude": 52.230100, "longitude": 21.013500, "altitudeM": 145.0, "horizontalAccuracyM": 2.8, "verticalAccuracyM": null }
        ],
        "samples": [
          { "timestamp": "2026-02-18T06:47:40Z", "type": "heartRate", "value": 110.0, "unit": "bpm" },
          { "timestamp": "2026-02-18T06:47:40Z", "type": "cadence", "value": 155.0, "unit": "spm" },
          { "timestamp": "2026-02-18T06:47:40Z", "type": "speed", "value": 1.8, "unit": "m/s" },
          { "timestamp": "2026-02-18T06:48:40Z", "type": "heartRate", "value": 125.0, "unit": "bpm" },
          { "timestamp": "2026-02-18T06:48:40Z", "type": "cadence", "value": 162.0, "unit": "spm" },
          { "timestamp": "2026-02-18T06:48:40Z", "type": "speed", "value": 2.1, "unit": "m/s" }
        ],
        "metadata": { "exerciseType": "RUNNING" }
      }
    ],
    "sleep": [
      {
        "id": "slp-001-abc-s0-0",
        "parentId": "slp-001-abc",
        "stage": "awake",
        "startDate": "2026-02-17T23:00:00Z",
        "endDate": "2026-02-17T23:10:00Z",
        "zoneOffset": "+01:00",
        "source": { "appId": "com.sec.android.app.shealth", "deviceId": "R9ZW30ABC12", "deviceName": "Galaxy Watch7", "deviceManufacturer": "Samsung", "deviceModel": "SM-R960", "deviceType": "watch", "recordingMethod": "automatic" },
        "values": [{ "type": "sleepScore", "value": 82, "unit": "score" }],
        "metadata": null
      },
      {
        "id": "slp-001-abc-s0-1",
        "parentId": "slp-001-abc",
        "stage": "light",
        "startDate": "2026-02-17T23:10:00Z",
        "endDate": "2026-02-18T00:00:00Z",
        "zoneOffset": "+01:00",
        "source": { "appId": "com.sec.android.app.shealth", "deviceId": "R9ZW30ABC12", "deviceName": "Galaxy Watch7", "deviceManufacturer": "Samsung", "deviceModel": "SM-R960", "deviceType": "watch", "recordingMethod": "automatic" },
        "values": [{ "type": "sleepScore", "value": 82, "unit": "score" }],
        "metadata": null
      },
      {
        "id": "slp-001-abc-s0-2",
        "parentId": "slp-001-abc",
        "stage": "deep",
        "startDate": "2026-02-18T00:00:00Z",
        "endDate": "2026-02-18T01:00:00Z",
        "zoneOffset": "+01:00",
        "source": { "appId": "com.sec.android.app.shealth", "deviceId": "R9ZW30ABC12", "deviceName": "Galaxy Watch7", "deviceManufacturer": "Samsung", "deviceModel": "SM-R960", "deviceType": "watch", "recordingMethod": "automatic" },
        "values": [{ "type": "sleepScore", "value": 82, "unit": "score" }],
        "metadata": null
      }
    ]
  }
}
```

### 7.3 Example — Health Connect

```json
{
  "provider": "health_connect",
  "sdkVersion": "0.1.0",
  "syncTimestamp": "2026-02-18T12:00:00Z",
  "data": {
    "records": [
      {
        "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "type": "StepsRecord",
        "startDate": "2026-02-18T06:00:00Z",
        "endDate": "2026-02-18T06:30:00Z",
        "zoneOffset": "+01:00",
        "source": { "appId": "com.google.android.apps.fitness", "deviceId": null, "deviceName": null, "deviceManufacturer": "Google", "deviceModel": "Pixel 8", "deviceType": "phone", "recordingMethod": "automatic" },
        "value": 3542,
        "unit": "count",
        "parentId": null,
        "metadata": null
      },
      {
        "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901-s0",
        "type": "HeartRateRecord",
        "startDate": "2026-02-18T08:00:00Z",
        "endDate": "2026-02-18T08:00:00Z",
        "zoneOffset": "+01:00",
        "source": { "appId": "com.samsung.android.wear.shealth", "deviceId": null, "deviceName": null, "deviceManufacturer": "Samsung", "deviceModel": "SM-R960", "deviceType": "watch", "recordingMethod": "automatic" },
        "value": 62,
        "unit": "bpm",
        "parentId": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
        "metadata": null
      },
      {
        "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901-s1",
        "type": "HeartRateRecord",
        "startDate": "2026-02-18T08:01:00Z",
        "endDate": "2026-02-18T08:01:00Z",
        "zoneOffset": "+01:00",
        "source": { "appId": "com.samsung.android.wear.shealth", "deviceId": null, "deviceName": null, "deviceManufacturer": "Samsung", "deviceModel": "SM-R960", "deviceType": "watch", "recordingMethod": "automatic" },
        "value": 64,
        "unit": "bpm",
        "parentId": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
        "metadata": null
      },
      {
        "id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
        "type": "OxygenSaturationRecord",
        "startDate": "2026-02-18T07:30:00Z",
        "endDate": "2026-02-18T07:30:00Z",
        "zoneOffset": "+01:00",
        "source": { "appId": "com.samsung.android.wear.shealth", "deviceId": null, "deviceName": null, "deviceManufacturer": "Samsung", "deviceModel": "SM-R960", "deviceType": "watch", "recordingMethod": "automatic" },
        "value": 97.5,
        "unit": "%",
        "parentId": null,
        "metadata": null
      },
      {
        "id": "d4e5f6a7-b8c9-0123-defa-234567890123-sys",
        "type": "BloodPressureRecord",
        "startDate": "2026-02-18T07:00:00Z",
        "endDate": "2026-02-18T07:00:00Z",
        "zoneOffset": "+01:00",
        "source": { "appId": "com.withings.wiscale2", "deviceId": null, "deviceName": null, "deviceManufacturer": "Withings", "deviceModel": "BPM Connect", "deviceType": "medical_device", "recordingMethod": "active" },
        "value": 121.0,
        "unit": "mmHg",
        "parentId": "d4e5f6a7-b8c9-0123-defa-234567890123",
        "metadata": { "component": "systolic", "bodyPosition": "standing", "measurementLocation": "left_upper_arm" }
      },
      {
        "id": "d4e5f6a7-b8c9-0123-defa-234567890123-dia",
        "type": "BloodPressureRecord",
        "startDate": "2026-02-18T07:00:00Z",
        "endDate": "2026-02-18T07:00:00Z",
        "zoneOffset": "+01:00",
        "source": { "appId": "com.withings.wiscale2", "deviceId": null, "deviceName": null, "deviceManufacturer": "Withings", "deviceModel": "BPM Connect", "deviceType": "medical_device", "recordingMethod": "active" },
        "value": 78.0,
        "unit": "mmHg",
        "parentId": "d4e5f6a7-b8c9-0123-defa-234567890123",
        "metadata": { "component": "diastolic", "bodyPosition": "standing", "measurementLocation": "left_upper_arm" }
      },
      {
        "id": "e5f6a7b8-c9d0-1234-efab-345678901234",
        "type": "BloodGlucoseRecord",
        "startDate": "2026-02-18T12:15:00Z",
        "endDate": "2026-02-18T12:15:00Z",
        "zoneOffset": "+01:00",
        "source": { "appId": "com.dexcom.g7", "deviceId": null, "deviceName": null, "deviceManufacturer": "Dexcom", "deviceModel": "G7", "deviceType": "medical_device", "recordingMethod": "automatic" },
        "value": 5.6,
        "unit": "mmol/L",
        "parentId": null,
        "metadata": { "specimenSource": "capillary_blood", "relationToMeal": "fasting" }
      },
      {
        "id": "b8c9d0e1-f2a3-4567-bcde-678901234567",
        "type": "WeightRecord",
        "startDate": "2026-02-18T06:50:00Z",
        "endDate": "2026-02-18T06:50:00Z",
        "zoneOffset": "+01:00",
        "source": { "appId": "com.withings.wiscale2", "deviceId": null, "deviceName": null, "deviceManufacturer": "Withings", "deviceModel": "Body+", "deviceType": "scale", "recordingMethod": "automatic" },
        "value": 78.5,
        "unit": "kg",
        "parentId": null,
        "metadata": null
      },
      {
        "id": "d0e1f2a3-b4c5-6789-defa-890123456789",
        "type": "HeartRateVariabilityRmssdRecord",
        "startDate": "2026-02-18T08:05:00Z",
        "endDate": "2026-02-18T08:05:00Z",
        "zoneOffset": "+01:00",
        "source": { "appId": "com.samsung.android.wear.shealth", "deviceId": null, "deviceName": null, "deviceManufacturer": "Samsung", "deviceModel": "SM-R960", "deviceType": "watch", "recordingMethod": "automatic" },
        "value": 42.7,
        "unit": "ms",
        "parentId": null,
        "metadata": null
      },
      {
        "id": "e1f2a3b4-c5d6-7890-efab-901234567890",
        "type": "FloorsClimbedRecord",
        "startDate": "2026-02-18T09:00:00Z",
        "endDate": "2026-02-18T09:30:00Z",
        "zoneOffset": "+01:00",
        "source": { "appId": "com.google.android.apps.fitness", "deviceId": null, "deviceName": null, "deviceManufacturer": "Google", "deviceModel": "Pixel 8", "deviceType": "phone", "recordingMethod": "automatic" },
        "value": 4,
        "unit": "count",
        "parentId": null,
        "metadata": null
      },
      {
        "id": "b4c5d6e7-f8a9-0123-bcde-234567890bcd",
        "type": "HydrationRecord",
        "startDate": "2026-02-18T08:00:00Z",
        "endDate": "2026-02-18T08:00:00Z",
        "zoneOffset": "+01:00",
        "source": { "appId": "com.google.android.apps.fitness", "deviceId": null, "deviceName": null, "deviceManufacturer": "Google", "deviceModel": "Pixel 8", "deviceType": "phone", "recordingMethod": "manual" },
        "value": 330.0,
        "unit": "mL",
        "parentId": null,
        "metadata": null
      }
    ],
    "workouts": [
      {
        "id": "11111111-2222-3333-4444-555555555555",
        "parentId": null,
        "type": "ExerciseSessionRecord",
        "startDate": "2026-02-18T06:30:00Z",
        "endDate": "2026-02-18T07:15:00Z",
        "zoneOffset": "+01:00",
        "source": { "appId": "com.strava", "deviceId": null, "deviceName": null, "deviceManufacturer": "Samsung", "deviceModel": "SM-R960", "deviceType": "watch", "recordingMethod": "active" },
        "title": "Morning Run",
        "notes": "Easy 5K around the park",
        "values": [
          { "type": "duration", "value": 2700.0, "unit": "s" },
          { "type": "activeCalories", "value": 345.0, "unit": "kcal" },
          { "type": "distance", "value": 5000.0, "unit": "m" },
          { "type": "avgHeartRate", "value": 148.0, "unit": "bpm" },
          { "type": "maxHeartRate", "value": 175.0, "unit": "bpm" },
          { "type": "avgSpeed", "value": 1.85, "unit": "m/s" }
        ],
        "segments": [
          { "startDate": "2026-02-18T06:30:00Z", "endDate": "2026-02-18T06:35:00Z", "type": "stretching", "repetitions": null },
          { "startDate": "2026-02-18T06:35:00Z", "endDate": "2026-02-18T07:10:00Z", "type": "running", "repetitions": null },
          { "startDate": "2026-02-18T07:10:00Z", "endDate": "2026-02-18T07:15:00Z", "type": "cooldown", "repetitions": null }
        ],
        "laps": [
          { "startDate": "2026-02-18T06:35:00Z", "endDate": "2026-02-18T06:42:30Z", "distanceM": 1000.0 },
          { "startDate": "2026-02-18T06:42:30Z", "endDate": "2026-02-18T06:49:45Z", "distanceM": 1000.0 },
          { "startDate": "2026-02-18T06:49:45Z", "endDate": "2026-02-18T06:57:00Z", "distanceM": 1000.0 },
          { "startDate": "2026-02-18T06:57:00Z", "endDate": "2026-02-18T07:04:15Z", "distanceM": 1000.0 },
          { "startDate": "2026-02-18T07:04:15Z", "endDate": "2026-02-18T07:10:00Z", "distanceM": 1000.0 }
        ],
        "route": [
          { "timestamp": "2026-02-18T06:35:00Z", "latitude": 52.2297, "longitude": 21.0122, "altitudeM": 110.5, "horizontalAccuracyM": 3.2, "verticalAccuracyM": 5.1 },
          { "timestamp": "2026-02-18T06:50:00Z", "latitude": 52.2312, "longitude": 21.0148, "altitudeM": 109.3, "horizontalAccuracyM": 3.5, "verticalAccuracyM": 5.8 }
        ],
        "samples": null,
        "metadata": { "exerciseType": 56, "hasRoute": true }
      }
    ],
    "sleep": [
      {
        "id": "99999999-8888-7777-6666-555555555555-s0",
        "parentId": "99999999-8888-7777-6666-555555555555",
        "stage": "awake",
        "startDate": "2026-02-17T22:45:00Z",
        "endDate": "2026-02-17T22:58:00Z",
        "zoneOffset": "+01:00",
        "source": { "appId": "com.samsung.android.wear.shealth", "deviceId": null, "deviceName": null, "deviceManufacturer": "Samsung", "deviceModel": "SM-R960", "deviceType": "watch", "recordingMethod": "automatic" },
        "values": null,
        "metadata": null
      },
      {
        "id": "99999999-8888-7777-6666-555555555555-s1",
        "parentId": "99999999-8888-7777-6666-555555555555",
        "stage": "light",
        "startDate": "2026-02-17T22:58:00Z",
        "endDate": "2026-02-17T23:25:00Z",
        "zoneOffset": "+01:00",
        "source": { "appId": "com.samsung.android.wear.shealth", "deviceId": null, "deviceName": null, "deviceManufacturer": "Samsung", "deviceModel": "SM-R960", "deviceType": "watch", "recordingMethod": "automatic" },
        "values": null,
        "metadata": null
      },
      {
        "id": "99999999-8888-7777-6666-555555555555-s2",
        "parentId": "99999999-8888-7777-6666-555555555555",
        "stage": "deep",
        "startDate": "2026-02-17T23:25:00Z",
        "endDate": "2026-02-18T00:10:00Z",
        "zoneOffset": "+01:00",
        "source": { "appId": "com.samsung.android.wear.shealth", "deviceId": null, "deviceName": null, "deviceManufacturer": "Samsung", "deviceModel": "SM-R960", "deviceType": "watch", "recordingMethod": "automatic" },
        "values": null,
        "metadata": null
      },
      {
        "id": "99999999-8888-7777-6666-555555555555-s3",
        "parentId": "99999999-8888-7777-6666-555555555555",
        "stage": "rem",
        "startDate": "2026-02-18T00:10:00Z",
        "endDate": "2026-02-18T00:45:00Z",
        "zoneOffset": "+01:00",
        "source": { "appId": "com.samsung.android.wear.shealth", "deviceId": null, "deviceName": null, "deviceManufacturer": "Samsung", "deviceModel": "SM-R960", "deviceType": "watch", "recordingMethod": "automatic" },
        "values": null,
        "metadata": null
      }
    ]
  }
}
```
