# Personal Record Write API — Design

**Date:** 2026-07-08
**Repo:** open-wearables (fork)
**Branch:** release/0.6.2-syn
**Status:** Approved design — pending implementation plan
**Type:** Fork DELTA (net-new vs upstream OW)

## Problem

The `public.personal_record` table holds slow-changing per-user attributes
(`birth_date`, `sex`, `gender`) but there is **no HTTP endpoint that writes to
it**. Today the only writer is the seed-data generator (`seed_data/service.py`
via `CrudRepository(PersonalRecord)`). Real users therefore have no
`personal_record` row, so `birth_date` is always absent.

`birth_date` is consumed by OW's own heart-rate math:

- `event_record_service._user_birth_date` → `estimate_max_hr` — runs **at
  workout ingest** and produces the `hr_zone_*_min` fields on workouts.
- `summaries_service._get_user_max_hr` — daily-summary intensity minutes.

Both use `estimate_max_hr` (`app/utils/heart_rate.py`), which falls back to
`DEFAULT_MAX_HR = 190` when `birth_date` is `None`. With no way to set
`birth_date`, every user's zones are computed against the 190 fallback instead
of the correct `220 − age`.

The .NET adapter currently compensates with `WorkoutHrZoneHealService`, which
re-derives zones from its own `user_profiles.date_of_birth`. Giving OW the
`birth_date` lets **OW compute correct zones at the source**, so freshly
ingested workouts arrive correct and the adapter heal becomes redundant for new
data.

## Goals

1. Let the .NET adapter (server-to-server) populate `personal_record` for a
   user — primarily `birth_date`, so OW computes max HR as `220 − age`.
2. Store `gender` (self-reported) alongside it.
3. Support backfilling existing users who have no `personal_record` row, via a
   safely repeatable, idempotent call.

## Non-goals / scope boundaries

- **No retroactive recompute.** OW computes zones **once, at ingest time**.
  Setting `birth_date` only affects workouts ingested *afterward*. Historical
  workouts keep their maxHr-190 zones; the adapter's existing
  `WorkoutHrZoneHealService` continues to cover those.
- **`sex` is excluded.** The `sex: bool` column is read by nothing in OW (not
  even the seed generator sets it) and its boolean semantics are ambiguous.
  Excluding it keeps the write body equal to the existing `PersonalRecordBase`.
  Adding `sex` later is an additive follow-up.
- **Caller is the adapter only.** Mobile-SDK / dashboard write paths are out of
  scope for this change.

## Design

### Endpoint

Singleton sub-resource under the user, with idempotent upsert:

| Method | Path                                    | Auth        | Success        |
|--------|-----------------------------------------|-------------|----------------|
| `PUT`  | `/users/{user_id}/personal-record`      | `ApiKeyDep` | 201 create / 200 update |
| `GET`  | `/users/{user_id}/personal-record`      | `ApiKeyDep` | 200 / 404 if none |

- `user_id` comes from the path; the adapter already knows the OW user id from
  its `wearable_connections` mapping.
- `ApiKeyDep` matches the existing `POST /users`, which the adapter already
  authenticates against.
- Registered in `app/api/routes/v1/__init__.py` under the
  `External: Users` tag.

Chosen over (B) separate `POST`(409)/`PATCH` verbs — which force the adapter to
know whether a row exists before writing (extra round-trip / race, poor backfill
ergonomics) — and (C) a top-level `/personal-records/{id}` resource — which
forces the caller to track a row id it does not care about, a poor fit for the
1:1-per-user cardinality (`personal_record.user_id` is `Unique`).

### Request / response schemas

Write body reuses the existing `PersonalRecordBase`
(`app/schemas/model_crud/activities/personal_record.py`):

```python
class PersonalRecordUpsert(PersonalRecordBase):  # birth_date + gender
    ...
```

- `birth_date: date | None` — validator: must not be in the future and not
  absurdly old (age ≤ 120). Nullable so a caller may send only what it has.
- `gender: Literal["female","male","nonbinary","other"] | None` — already
  validated by `PersonalRecordBase`.
- The caller never supplies `id` (server-generated on create) or `user_id`
  (from the path).

Response: existing `PersonalRecordResponse` (`id`, `user_id`, `birth_date`,
`gender`).

### Wiring (mirrors `users.py` → service → repository)

- **Repository** — `PersonalRecordRepository` (or the generic
  `CrudRepository`) with a `get_by_user_id(db, user_id)` lookup.
- **Service** — `personal_record_service.upsert(db, user_id, payload)`:
  1. Verify the user exists → else 404 (avoids an opaque FK error).
  2. `get_by_user_id`; if absent → create with a server-generated `id`;
     else → update the mutable fields (`birth_date`, `gender`).
  3. Return the row and whether it was created (drives 201 vs 200).
- **Route** — new `app/api/routes/v1/personal_records.py` holding the `PUT` and
  `GET` handlers.

### Error handling

| Condition                         | Status |
|-----------------------------------|--------|
| Missing / invalid API key         | 401    |
| Unknown `user_id`                 | 404    |
| GET with no `personal_record` row | 404    |
| `birth_date` in the future / invalid | 400 (OW remaps `RequestValidationError` → 400) |

## Testing (pytest)

1. Upsert creates when absent → 201, row present with correct fields.
2. Upsert updates when present → 200, same `user_id`, **no duplicate row**
   (exercises the `Unique(user_id)` path).
3. GET returns the row; GET with no row → 404.
4. Unknown `user_id` → 404 (both PUT and GET).
5. Future `birth_date` → 400 (OW remaps `RequestValidationError` → 400).
6. Missing API key → 401.
7. Behavioral: after setting `birth_date`, a newly ingested workout's
   `hr_zone_*_min` reflect `220 − age` rather than the 190 fallback
   (integration-level; confirms the end-to-end purpose).

## Fork DELTA record

Record in `FORK-DELTA.md`: net-new `PUT/GET /users/{user_id}/personal-record`
write API for `personal_record`, adapter-driven, `birth_date` set at source to
drive OW's `220 − age` HR-zone math. Note the "future-workouts-only" recompute
boundary and that `sex` is intentionally omitted.
