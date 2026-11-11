# Touchpoint map: every file a new provider touches

Examples use slug `coros`, display name `COROS`. Substitute yours. Paths are
from the repo root.

The guiding rule for a fork-only provider: **put as much as possible in files
the provider owns, keep shared-file edits few and small, and mark them.**
Owned files cannot conflict in an upstream merge (until upstream ships the
same provider). Shared-file edits can, and a careless merge drops them.
`scripts/fork_providers.py register` records both kinds, and `verify` checks
them after every merge.

## Marker convention for shared files

Every line you add to a shared file carries the slug and a marker, so whoever
resolves a merge conflict sees at a glance that the line must survive:

- Python, single line: a trailing comment, `COROS = "coros"  # fork-provider: coros`.
- Python, block: an opening comment that names the marker and a closing one:
  ```python
  # COROS OAUTH SETTINGS (fork-provider: coros)
  ...
  # end fork-provider: coros
  ```
- `.env.example`: the same opening and closing pair as `#` comments.
- YAML, bash and MDX lines where a comment can't go, such as inside a multi-line
  bash command in `buildspec.yml` or a Markdown table row: no marker. Use names
  that contain the slug (`COROS_CLIENT_ID`, `coros_credentials`). The registry
  footprint counts those mentions.

## A. Owned files (new; no merge risk)

| Path | Required | Notes |
|---|---|---|
| `backend/app/services/providers/coros/__init__.py` | yes | Empty, or re-export the strategy |
| `backend/app/services/providers/coros/strategy.py` | yes | `CorosStrategy(BaseProviderStrategy)`: `name`, `display_name`, `api_base_url`, `capabilities`, `coverage`, components wired in `__init__` |
| `backend/app/services/providers/coros/coverage.py` | yes | `TIMESERIES`, `WORKOUT_FIELDS`, `SLEEP_FIELDS`, `HEALTH_SCORES` (plus `WORKOUT_ENERGY_SERIES` if known). Key→SeriesType maps live here and the handlers import them. |
| `backend/app/services/providers/coros/oauth.py` | cloud API | `CorosOAuth(BaseOAuthTemplate)` |
| `backend/app/services/providers/coros/workouts.py` | if workouts | `CorosWorkouts(BaseWorkoutsTemplate)` |
| `backend/app/services/providers/coros/data_247.py` | if sleep or 24/7 data | `Coros247Data(Base247DataTemplate)` |
| `backend/app/services/providers/coros/webhook_handler.py`, `webhook_service.py` | if push | See the webhook archetypes in `architecture.md` |
| `backend/app/services/providers/coros/<helpers>.py` or `handlers/` | optional | Provider-specific clients, timezone helpers, error types |
| `backend/app/schemas/providers/coros/__init__.py` plus models | recommended | Pydantic models for the provider's API payloads (see `schemas/providers/sensorbio/`) |
| `backend/app/constants/workout_types/coros.py` | if workouts | Provider type to `WorkoutType`, with `get_unified_workout_type()`. **Import it directly** (`from app.constants.workout_types.coros import ...`) as sensorbio and oura do. Do not add it to that package's `__init__.py`. |
| `backend/app/constants/series_types/coros.py` | optional | Provider enums to SeriesType / SleepStage maps (see `series_types/sensorbio.py`) |
| `backend/app/static/provider-icons/coros.svg` | yes | Square SVG logo; served as `icon_url` to the dashboard and API clients |
| `backend/app/integrations/celery/tasks/coros/` | only for per-user subscriptions | Pattern: `tasks/withings/notify_sync_task.py` |
| `backend/tests/providers/coros/` | yes | `__init__.py`, `conftest.py` (fixtures), and `test_coros_*.py`; see `implementation-rules.md` |
| `docs/providers/coros-api-integration.mdx` | yes | Setup guide (developer program, credentials, redirect URI, scopes, data, limits). Model it on `docs/providers/sensorbio-api-integration.mdx`. |

## B. Shared files: always edited (marked)

| File | Edit | Why |
|---|---|---|
| `backend/app/schemas/enums/provider.py` | (1) Add the member in a fork block **after `INTERNAL`**: `# --- Fork-only providers (frontbacklabs): see .agents/skills/support-new-provider ---` then `COROS = "coros"  # fork-provider: coros`. (2) Add to `DEFAULT_PROVIDER_PRIORITY` at the end: `ProviderName.COROS: 101,  # fork-provider: coros`. Fork providers take **101, 102, ...** so they never collide with upstream's next number (the test requires unique values). | Upstream appends new providers just above `UNKNOWN` and new priorities as 15, 16, ... Our block sits elsewhere, so their additions rarely overlap ours. |
| `backend/app/services/providers/factory.py` | Import with a trailing marker (ruff keeps trailing comments when it sorts imports). Put the case **first** inside `match provider_name:` as `case ProviderName.COROS.value:  # fork-provider: coros` followed by `return CorosStrategy()`. | Upstream appends cases just before `case _:` |
| `backend/app/config.py` | A marked block just before `# EMAIL SETTINGS`: `coros_client_id: str \| None = None`, `coros_client_secret: SecretStr \| None = None`, `coros_default_scope: str = "<minimal scopes>"`, plus `coros_webhook_*` if needed. **No `coros_redirect_uri`**: the redirect URI is derived from `API_BASE_URL` by `settings.oauth_redirect_uri(ProviderName.COROS)`, and the per-provider field is deprecated. | Name the fields `<slug>_client_id` / `<slug>_client_secret` / `<slug>_default_scope`, the convention upstream uses, so the env var names survive an upstream adoption. |
| `backend/config/.env.example` | A marked `#--- COROS (fork-provider: coros) ---#` block with placeholder values only | Local setup |
| `docs/providers/supported.mdx` | One row in "Cloud-based providers": `\| **COROS** \| [Setup Guide →](/providers/coros-api-integration) \| Fork-only (frontbacklabs). <access requirement> \|` | Discoverability |

## C. Shared files: only when the provider needs it (marked)

| File | When | Edit |
|---|---|---|
| `backend/app/constants/devices_map/device_types.py` | The provider ships one form factor (ring, band, scale) | `SINGLE_DEVICE_PROVIDER_TYPE[ProviderName.COROS] = DeviceType.WATCH` and the like. Leave it out if it ships several. |
| `backend/app/constants/health_scores.py` | It emits health scores | Add its scale under each `HealthScoreCategory` in `HEALTH_SCORE_RANGES` |
| `backend/app/config.py` (validator) | Webhooks need a shared secret | Add a `derive_coros_webhook_secret` model validator defaulting it to `secret_key`, like `derive_suunto_webhook_secret`. Ren then needs no extra AWS secret. |
| `backend/app/middlewares.py` | The provider sends a secret as a URL **query** parameter on webhook or verification calls | Add the key to `_REDACTED_QUERY_KEYS` so access logs mask it |
| `backend/app/services/providers/api_client.py` | Only if the provider can't use it as-is and an override inside your provider dir is impossible | Additive, optional keyword argument with a default (precedents: `http2=` for SensorBio, `form_data=` for Withings). **Prefer overriding `_make_api_request` in your own class** (as `sensorbio/data_247.py` does). |
| `backend/app/schemas/enums/series_types.py` (+ `aggregation_method.py`) | A metric has no existing `SeriesType` | Follow "New SeriesType" in `implementation-rules.md`: fork ID range 900–999, never reuse an ID |
| `backend/app/schemas/enums/workout_types.py` | Avoid | Map to the nearest existing `WorkoutType` or `OTHER`. A new value is a shared-API change. |
| `backend/app/constants/celery_tasks.py`, `backend/app/integrations/celery/tasks/__init__.py`, `backend/app/integrations/celery/core.py` | Per-user subscription tasks or periodic subscription renewal | Follow Withings (`WITHINGS_SYNC_USER_SUBSCRIPTIONS`) or Oura (`renew-oura-webhooks-monthly`) |
| `backend/app/integrations/celery/tasks/webhook_push_task.py` | `webhook_ping` provider whose deliveries should show in the sync log | Add the slug to `_SYNC_LOG_PROVIDERS` |

## D. Generated files: regenerate, never hand-edit or hand-merge

| File | Command (from `backend/`) | Also run by |
|---|---|---|
| `docs/providers/coverage.mdx` | `uv run python scripts/generate_coverage_docs.py` | pre-commit, when a `coverage.py` changes |
| `docs/openapi.json` | `uv run python scripts/export_openapi.py` | pre-commit, when any `backend/app/**.py` changes |

When these conflict in an upstream merge, take either side, then regenerate.

## E. Do not touch

| File | Why not |
|---|---|
| `README.md` provider list, `docs/index.mdx`, `docs/faqs.mdx`, `docs/dev-guides/telemetry.mdx` | They are upstream's marketing and examples; their links point at upstream's public docs site, which has no page for a fork-only provider |
| `.coderabbit.yaml` | Upstream's review bot labels |
| `mcp/**` | Docstrings list example providers only; nothing enumerates providers |
| `frontend/**` | The dashboard reads providers, icons and coverage from the API. Nothing to add. (`frontend/src/lib/seed/catalogue.ts` is the seed-data generator and stays upstream-only.) |
| `backend/app/services/seed_data/**` | Same: seed data for upstream's demo providers |
| `backend/app/constants/series_types/history_rules.py` | Frozen history of how older code stored rows; new providers write aggregates directly |
| `backend/app/services/aggregate_backfill_service.py` (`_workout_energy_series`) | Backfill of rows from before the aggregate tables |
| `backend/app/constants/workout_types/__init__.py` | Import your module directly instead |
| `backend/app/constants/sdk_providers.py` | SDK providers only |
| `backend/tests/providers/conftest.py`, `backend/tests/providers/test_provider_factory.py`, `backend/tests/schemas/test_provider_name.py` | Put your fixtures, factory test and name-inference test in `backend/tests/providers/coros/` instead |
| Alembic `backend/migrations/` | Provider columns are strings; a new provider needs no migration. If you think you need one, re-read fork-wins rule 6 and ask first. |
| `cloudbuild.yaml` | Retired GCP pipeline; the fork deploys from `buildspec.yml` |
| `docs/docs.json` | Provider pages are linked from `supported.mdx`, not the nav |
| `docs/dev-guides/how-to-add-new-provider.mdx`, `contributing/adding-providers.md` | Upstream's generic guides |

## F. Ren deployment (fork-only files)

| File | Edit |
|---|---|
| `buildspec.yml` | Secrets Manager reference, `--arg`, and the `COROS_CLIENT_ID` / `COROS_CLIENT_SECRET` secret entries. Exact snippet and ordering rules are in `ren-rollout.md`. |
