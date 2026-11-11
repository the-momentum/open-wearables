# Implementation rules

Conventions every provider in this repo already follows, plus the fork rules
that apply to new code. `backend/AGENTS.md` is the general backend rulebook:
layers, logging and error handling. Read it first; this page does not repeat
it except where providers make it concrete.

## Fork rules that bite provider code

- **User IDs are `str`** (fork-wins rule 1): Firebase UIDs, never `UUID`.
  Annotate `user_id: str` everywhere, pass `str(user_id)` into logs and
  payloads, and use `tests.factories.fake_firebase_uid()` or a literal string
  in tests. Upstream provider code you copy may say `user_id: UUID`; str-ify it.
- **Ask only for the scopes you use** (in the spirit of fork-wins rule 3). The
  default scope string requests exactly what the handlers read. If an optional
  endpoint needs a scope Ren does not request, gate that endpoint on the scope
  the connection was granted and skip it otherwise (pattern:
  `scope_granted()` in `google_health/helpers.py`). Asking for more is a
  product decision, not an implementation detail.
- **No migrations** for a provider. Fork-wins rule 6 governs any you think you
  need.
- Run the fork-only code paths with `str` user IDs in tests. Several upstream
  tests still fail on the fork because of UUID assumptions. Don't "fix" them as
  part of this work.

## Strategy (`strategy.py`)

Copy the exemplar strategy (see `architecture.md`) and change only the
identity, capabilities and components. Set:

- `name`: the slug (lowercase).
- `display_name`: the brand casing.
- `api_base_url`: the data API root; OAuth hosts go in `oauth.endpoints`.
- `capabilities`: honest flags. `max_historical_days` if the API caps history.
- `coverage`: `ProviderCoverage(...)` built from the `coverage.py` constants.

## Coverage (`coverage.py`) is the single source of truth

- Every key→`SeriesType` map lives here, and `data_247.py` / `workouts.py`
  import it. `TIMESERIES` is derived from those maps (`*MAP.values()`), plus
  any one-off `SeriesType.x` the handlers emit inline.
- Declare every `EventRecordDetail` field the code sets in `WORKOUT_FIELDS` /
  `SLEEP_FIELDS` (and `MENSTRUAL_CYCLE_FIELDS` / `MEAL_FIELDS` if relevant).
- `HEALTH_SCORES`: the categories you write.
- `WORKOUT_ENERGY_SERIES = SeriesType.active_energy` or `total_energy`, only if
  the provider documents which one its workout calories are. Otherwise omit
  it, and don't set `energy_series`.
- The guard test `tests/providers/test_provider_coverage.py -k coros` must
  pass.

## OAuth (`oauth.py`)

- `endpoints`: authorize and token URLs from the provider's docs.
- `credentials`: read `settings.coros_client_id`,
  `settings.coros_client_secret.get_secret_value()` (guard against `None`),
  `redirect_uri=settings.oauth_redirect_uri(ProviderName.COROS)` and
  `default_scope=settings.coros_default_scope`.
- `use_pkce` and `auth_method` (`BODY` or `BASIC_AUTH`) exactly as the
  provider documents. Getting these wrong shows up as `invalid_client` on the
  callback.
- `_get_provider_user_info` returns `{"user_id": <provider's stable user id as
  str or None>, "username": None}`. Never raise from it; log with
  `log_structured` and return `None`s on failure (see `oura/oauth.py`).
- `deregister_user` revokes the grant if the provider has a revoke endpoint.
  Disconnect, data purge and account deletion all call it.
- Providers with non-standard token responses override `_exchange_token` /
  `refresh_access_token` (see `withings/oauth.py`). Providers that need extra
  token-request fields override `_prepare_token_request` /
  `_prepare_refresh_request`.

## HTTP calls

- Use `services/providers/api_client.make_authenticated_request` (it refreshes
  the token, retries 429s with backoff, and maps errors to `HTTPException`).
  Wrap it in a `_make_api_request` method on your class, as
  `sensorbio/data_247.py` and `sensorbio/workouts.py` do.
- Store every raw API response with
  `store_raw_payload(source="api_response", provider=self.provider_name,
  payload=..., user_id=str(user_id), trace_id=<endpoint>)`. It is a no-op
  unless raw payload storage is enabled, and invaluable when it is.
- Parse payloads through Pydantic models in `schemas/providers/coros/`. On a
  `ValidationError`, log and skip the record; don't fail the sync
  (`SensorBio247Data._parse` is the pattern).
- Respect documented rate limits. Paginate fully. If an endpoint takes one
  day per call, loop over days the way SensorBio's sleep does.

## 24/7 data (`data_247.py`)

- `load_and_save_all(db, user_id, start_time, end_time, is_first_sync)` uses
  `start_dt, end_dt = self.resolve_window(start_time, end_time,
  default_days=...)` and `run = self.sync_run(db, user_id)`. Each data type is
  one `with run.step("<type>") as step:` that ends with
  `step.record(write_counts)`. Finish with `run.log_summary()` and
  `return run.result`.
- Key steps by data type in the provider's vocabulary (`sleep`, `recovery`,
  `daily_activity`, `heart_rate`). Pass `WriteCounts` straight through from
  `timeseries_service.bulk_create_samples` / `health_score_service.bulk_create`.
- Day values carry `period=CalendarPeriod.of_date(day, zone_offset)` and
  `is_daily_total=daily_total_flag(series_type, True)`. Session values carry
  `session=SessionValue(record_id=...)`. Intraday samples carry neither (see
  the table in `architecture.md`).
- All datetimes are timezone-aware UTC (`app.utils.dates.as_utc`). Keep the
  provider's offset in `zone_offset` when it gives one.
- The abstract getters and normalizers you don't use (recovery for a provider
  with no recovery data, say) return empty results; don't raise.

## Workouts (`workouts.py`)

- `get_workouts(db, user_id, start_date, end_date)` returns the raw list.
- `_normalize_workout` builds `EventRecordCreate(id=uuid4(),
  category=EventCategory.WORKOUT, type=get_unified_workout_type(...).value,
  source_name="COROS", device_model=..., duration_seconds=...,
  start_datetime=..., end_datetime=..., external_id=<provider workout id as
  str>, source=self.provider_name, user_id=<str>)` plus
  `EventRecordDetailCreate(record_id=<same id>, **metrics)`. See
  `SensorBioWorkouts._normalize_workout`.
- `load_data(db, user_id, **kwargs) -> int` returns the number of workouts
  written. The sync task reads that number.
- The workout-type map lives in `constants/workout_types/coros.py`; unknown
  types map to `WorkoutType.OTHER` and are logged once.

## Webhooks (only if the provider pushes)

- The handler verifies the signature with the base helpers
  (`_verify_hmac_sha256`, `_verify_token`). Never hand-roll a comparison.
- `dispatch` must return fast: queue the work on Celery instead of fetching
  inline when the provider has a short timeout.
- Ping-style webhooks refetch through the same `data_247` / `workouts` code
  the pull uses, so there is one normalization path.
- Ren runs pull mode (see `ren-rollout.md`). Webhooks are optional for Ren;
  build them only when the provider has no usable polling API or the user asks
  for them.

## Logging, errors, privacy

- `log_structured(self.logger, level, "<stable message>",
  provider=self.provider_name, action=..., user_id=str(user_id), ...)`: put
  variable parts in attributes, not the message.
- Handled exceptions in batch or sync loops go through
  `log_and_capture_error(e, logger, "<stable message>", extra={ids and
  categories only})`.
- **Never log or send health values, raw payloads, names or emails to logs or
  Sentry.** IDs, counts and data-type names only.

## New `SeriesType` (avoid if you can)

First map onto an existing type: there are about 150, so check
`schemas/enums/series_types.py` thoroughly. If nothing fits:

1. Add the enum member named `coros_<metric>` (provider-prefixed, like
   `withings_pulse_wave_velocity`) with a trailing `# fork-provider: coros`.
2. Add `(9NN, SeriesType.coros_<metric>, "<unit>")` to `SERIES_TYPE_DEFINITIONS`
   using the **fork range 900–999**, and add `(range(900, 1000),
   "Provider-Specific (fork)")` to `_CATEGORY_RANGES` the first time. Upstream
   allocates IDs below 600, so a fork ID never collides with an upstream one.
   IDs are persisted forever: never reuse or renumber one.
3. Add its `AggregationMethod` in `aggregation_method.py` (SUM for counts and
   totals, AVG for rates, MAX/MIN where meaningful).
4. Startup's `scripts/init/seed_series_types.py` seeds the definition row; no
   migration.
5. Tell the user in the PR: Ren's DAS maps OW series to its own measurements,
   and a brand-new series type is invisible to Ren until it is mapped there.

## Tests (`backend/tests/providers/coros/`)

Fixtures go in a `conftest.py` here (not the shared `tests/providers/conftest.py`).
Build sample payloads from the provider's API docs, shaped exactly like real
responses, with **no real user data**. Write at least:

| File | Covers |
|---|---|
| `test_coros_strategy.py` | `name`, `display_name`, `api_base_url`, capabilities, components wired, coverage non-empty, `ProviderFactory().get_provider("coros")` returns `CorosStrategy`, `ProviderName.COROS` in `DEFAULT_PROVIDER_PRIORITY`, `ProviderName.from_source_string("COROS Pace 3") is ProviderName.COROS` |
| `test_coros_oauth.py` | Endpoints, credentials from settings, PKCE and auth method, user-info parsing including the failure path, revoke |
| `test_coros_workouts.py` | Normalization of each fixture: type mapping, UTC times, metrics, `external_id`; `load_data` count |
| `test_coros_247.py` | Each step: normalization, `period` / `session` on day and session values, `Sync247Result` step keys, an empty response, a malformed record that gets skipped |
| `test_coros_workout_types.py` | Known types map; an unknown type falls back to `OTHER` |
| `test_coros_webhooks.py` (if push) | Valid and invalid signature, challenge handshake, dispatch of each event type |

Mock HTTP at the `httpx` boundary or at `make_authenticated_request`, as the
existing provider tests do.

## Verification commands (from `backend/`)

```bash
uv run ruff check . --fix && uv run ruff format . && uv run ty check .
uv run pytest tests/providers/coros \
  tests/providers/test_provider_coverage.py tests/providers/test_provider_factory.py \
  tests/repositories/test_provider_priority_repository.py tests/schemas/test_provider_name.py \
  tests/services/test_provider_settings_service.py -q
uv run python scripts/generate_coverage_docs.py && uv run python scripts/export_openapi.py
```

Tests need Docker running (testcontainers starts Postgres and Redis) or
`TEST_DATABASE_URL`. Then run the whole suite and compare it with the same run
on `main`. **The fork's PRs get no CI test run** (only CodeQL is queued), so
your local run is the gate. Report any failure that is not already failing on
`main`.

If credentials exist, also run the live checks in `ren-rollout.md` § Local
end-to-end.
