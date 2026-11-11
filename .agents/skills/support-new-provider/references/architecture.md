# How a provider is built in Open Wearables

Verified on 2026-11-11 against the fork's `main` (73046c73). That commit last
synced upstream at 8adb8d0b (2026-10-30) and was then 60 commits behind
upstream 1.0 (7ca121dd). The provider APIs named here exist on both. If a
path or signature below no longer matches the code, trust the code and update
this page. Upstream's own guide is
`docs/dev-guides/how-to-add-new-provider.mdx`. It has full code samples, but
some of its examples are older than the code (its factory example, for one).

## The runtime path a provider plugs into

| Flow | Entry point | What it calls on your provider |
|---|---|---|
| Connect | `GET /api/v1/oauth/{slug}/authorize?user_id=` and then `GET /api/v1/oauth/{slug}/callback` (`api/routes/v1/oauth.py`) | `oauth.get_authorization_url` and `oauth.handle_callback`. The callback exchanges the token, calls `_get_provider_user_info`, then `_save_connection`. It then stamps `last_synced_at` and, while `HISTORICAL_SYNC_ON_CONNECT` is true, queues a historical sync. |
| Periodic pull | Celery beat `sync-all-users-periodic` every `SYNC_INTERVAL_SECONDS` (default 3600) runs `sync_all_users`, which runs `sync_vendor_data` per user (`integrations/celery/tasks/sync_vendor_data_task.py`) | `workouts.load_data(db, user_id, **build_sync_params(start, end))`, then `data_247.load_and_save_all(db, user_id, start_time, end_time, is_first_sync)`, which returns a `Sync247Result`. |
| Historical sync | `POST /api/v1/providers/{slug}/users/{user_id}/sync/historical` | `strategy.start_historical_sync(user_id, days)`. The default runs the same pull with `is_historical=True`; `capabilities.max_historical_days` caps it. |
| Manual sync | `POST /api/v1/providers/{slug}/users/{user_id}/sync` | Same as periodic pull, for one user. |
| Push | `POST`/`GET`/`HEAD /api/v1/providers/{slug}/webhooks` (`api/routes/v1/webhooks.py`, the unified router) | `webhooks.handle`, `webhooks.handle_challenge`, `webhooks.handle_probe`. No new route file is needed. |
| Subscriptions | `/api/v1/providers/{slug}/webhooks/subscriptions*`; `PUT /api/v1/oauth/providers/{slug}` (switching live-sync mode) | `webhook_service.*`; `strategy.apply_live_sync_mode` queues `reconcile_provider_webhooks` when `webhook_registration_api` is set. |
| Provider list | `GET /api/v1/oauth/providers` (`provider_settings_service.get_all_providers`) | Iterates every `ProviderName` except `unknown`/`internal` and calls `ProviderFactory.get_provider` on each. **Add the enum member and the factory case together**: a member without a factory case breaks this endpoint and the periodic sync's eligibility check. |
| Coverage | `GET /api/v1/meta/coverage` | `strategy.coverage`. It also feeds the dashboard's Data Coverage tab and `docs/providers/coverage.mdx`. |

`provider` columns (`user_connection`, `data_source`, `provider_settings`,
`provider_priority`, `health_score`, `sync_run`) are `String`, not a Postgres
enum. **Adding a provider needs no Alembic migration.**

## Components (`services/providers/base_strategy.py`)

| Attribute | Base class (`services/providers/templates/`) | Set it when |
|---|---|---|
| `oauth` | `BaseOAuthTemplate`: abstract `endpoints`, `credentials`; knobs `use_pkce`, `auth_method`; hooks `_get_provider_user_info`, `deregister_user`, `_save_connection`, `_prepare_token_request` / `_prepare_refresh_request` | It is a cloud provider. `None` means SDK-only. |
| `workouts` | `BaseWorkoutsTemplate`: abstract `get_workouts`, `_normalize_workout`; implement `load_data` (returns the **count** written), `_extract_dates`, `get_workouts_from_api` | The API exposes workouts or activities. |
| `data_247` | `Base247DataTemplate`: abstract sleep / recovery / activity-samples / daily-activity getters and normalizers; override `load_and_save_all` using `self.sync_run(...)` and `self.resolve_window(...)` | It exposes sleep, recovery, HR, steps or any other continuous data. |
| `webhooks` | `BaseWebhookHandler`: `verify_signature`, `parse_payload`, `dispatch`, `supported_event_types`; optional `handle_challenge`, `handle_probe`, `process_payload` | It pushes (`webhook_ping` or `webhook_stream`). |
| `webhook_service` | `BaseWebhookService`: `register_subscriptions`, `deregister_subscriptions`, `list_subscriptions`, ... (unsupported operations raise `NotImplementedError`) | `webhook_registration_api=True`. |

Required strategy properties: `name` (the slug), `api_base_url`,
`capabilities`. Optional: `display_name` (defaults to `name.capitalize()`;
override it for brand casing such as "COROS" or "Sensor Bio"), `coverage`
(always set it), `api_version`, and `start_historical_sync` (override only for
a non-pull backfill such as Garmin's). The icon is served from
`/static/provider-icons/{slug}.svg`.

## `ProviderCapabilities`

`rest_pull`, `client_sdk`, `file_import`, `webhook_callback`, `webhook_stream`,
`webhook_ping`, `webhook_registration_api`, `webhook_subscription_per_user`,
`webhook_inbound_secret`, `max_historical_days`. `__post_init__` enforces:

- `webhook_stream` and `webhook_ping` are mutually exclusive.
- `webhook_ping` requires `rest_pull`.
- `webhook_inbound_secret` and `webhook_subscription_per_user` each require
  `webhook_registration_api`.

The default live-sync mode is derived from the flags: `rest_pull` gives
`PULL`. Ren runs every provider in pull mode (see `ren-rollout.md`), so
`rest_pull=True` is what matters for Ren. Add webhooks only if the provider
offers no usable polling.

## Existing providers by archetype: pick the closest one as your exemplar

| Archetype | Capabilities | Exemplar | Notes |
|---|---|---|---|
| REST pull, 24/7 data and workouts | `rest_pull` | **`sensorbio`** (newest, small, clean) | Pydantic payload schemas in `schemas/providers/sensorbio/`, a per-day endpoint loop, HTTP/2 via `http2=True` |
| REST pull, 24/7 data only (ring) | `rest_pull` | `ultrahuman` | No workouts component |
| REST pull plus webhook ping, subscriptions set by hand in the provider portal | `rest_pull, webhook_ping` | `whoop` | Webhook triggers a REST refetch |
| REST pull plus webhook ping plus a registration API (app-level) | `+ webhook_registration_api` | `oura`, `strava`, `google_health` | `polar` adds `webhook_inbound_secret` |
| Per-user subscriptions | `+ webhook_subscription_per_user` | `withings` | Per-connection Celery task under `integrations/celery/tasks/withings/`; RPC-over-POST API via `api_client` `form_data` |
| Full-payload stream | `rest_pull, webhook_stream` | `suunto` | `garmin` is stream plus `webhook_callback` backfill, without `rest_pull` |
| Workouts-centric | `rest_pull, webhook_ping` | `strava` | `fitbit` is legacy and feature-frozen; do not copy it |
| On-device SDK | `client_sdk` | `apple`, `samsung`, `health_connect` | **Out of scope for this SOP**: it needs mobile SDK work in `open_wearables_ios_sdk` |

OAuth variants:
- PKCE: `garmin`, `fitbit`.
- `AuthenticationMethod.BASIC_AUTH`: `fitbit`.
- `AuthenticationMethod.BODY`: most of the rest.
- Non-standard token handling: `withings`, which overrides `_exchange_token` and `refresh_access_token` because its token endpoint is an RPC action (`action=requesttoken`) with a wrapped response.

## Where each kind of value goes

| Provider value | Write as | Key details |
|---|---|---|
| Workout | `EventRecordCreate(category="workout", type=<WorkoutType>, external_id=<provider id>, ...)` plus `EventRecordDetailCreate` through `event_record_service.create` / `create_detail` | Non-meal records are unique per `(data_source_id, start_datetime, end_datetime)`, so a re-sync of the same window updates instead of duplicating. Keep start and end stable and in UTC. |
| Sleep session | `EventRecord(category="sleep")` plus sleep detail fields (`sleep_*`, `is_nap`, `sleep_stages`) | Fields you set must be in `SLEEP_FIELDS` |
| Continuous samples (HR, steps per epoch) | `TimeSeriesSampleCreate` via `timeseries_service.bulk_create_samples` (returns `WriteCounts`) | Unique per `(data_source_id, series_type, recorded_at)` |
| A day's total or average | The same sample with `period=CalendarPeriod.of_date(day, zone_offset)` (or `.local_day(...)`) and `is_daily_total=daily_total_flag(series_type, True)` | Mirrored into `series_aggregate`. Without `period` the value is not written to the day aggregate; it is stored as an ordinary sample. |
| One value for a sleep or workout (resting HR, HRV of a night) | Sample with `session=SessionValue(record_id=<event record id>)` | Mirrored into `event_record_aggregate` |
| Provider scores (sleep, readiness, recovery) | `HealthScoreCreate` via `health_score_service.bulk_create` | Add the scale to `constants/health_scores.py` `HEALTH_SCORE_RANGES` |
| Workout energy series | `energy_series=WORKOUT_ENERGY_SERIES` from your `coverage.py` | Declare it only when the provider's energy semantics (active vs total) are known; the guard test enforces this |

Metric vocabulary is `SeriesType` (`schemas/enums/series_types.py`, with
stable persisted IDs). Workout vocabulary is `WorkoutType`
(`schemas/enums/workout_types.py`). Sleep stages are `SleepStage`. Map onto
what exists. Adding to any of these is a shared-file change with the rules in
`implementation-rules.md`.

## Guard tests that already encode the contract

They pick up a new provider automatically. Make them pass; don't edit them.

- `tests/providers/test_provider_coverage.py` scans every provider directory
  that has a `coverage.py`. It fails if your code emits a `SeriesType` or sets
  a detail field that `coverage.py` does not declare, or if the strategy drops
  a constant.
- `tests/repositories/test_provider_priority_repository.py::test_default_order_covers_every_connectable_provider`:
  every `ProviderName` has a unique `DEFAULT_PROVIDER_PRIORITY`.
- `tests/providers/test_provider_factory.py`: `SDK_PROVIDERS` matches the
  `client_sdk` strategies.
- `tests/schemas/test_provider_name.py`: substring inference in
  `ProviderName.from_source_string`.
