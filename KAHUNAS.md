# wearables-gateway — Kahunas fork operating rules

This repo is the Kahunas fork of
[the-momentum/open-wearables](https://github.com/the-momentum/open-wearables):
the shared multi-tenant wearables service (KAH-2426). It mints bridge-app
sessions (Biomtrx, KAH-2423), brokers cloud-provider OAuth, normalizes
samples, and forwards them to each tenant's K2 ingestion API. Binding
contracts live in kahunas `docs/adr/0015-wearables-biomtrx-bridge-and-gateway.md`;
programme plan in bridge-app `docs/specification.md`.

## The load-bearing rule

**No health samples at rest.** Samples pass through: ingest → normalize →
forward to the owning tenant → ack. Transient retry buffering only, with an
explicit max in-flight retention and a dead-letter policy. Upstream's sample
storage is removed, and schema review must prove no sample tables remain.

Enforcement points (upstream funnels every path through two chokepoints):

- `backend/app/services/timeseries_service.py::bulk_create_samples`
- `backend/app/services/event_record_service.py`

Both get replaced by the tenant-forwarding delivery pipeline. Additionally
`RAW_PAYLOAD_STORAGE` and `STORE_FIT_FILES` must stay disabled — CI asserts
this; never enable them in any environment.

## Fork discipline

- Upstream baseline: `44a268be623e81995e896b05ed93a56411ddf807`
  (0.6.3 + 38, 2026-08-07). Remote `upstream` →
  `https://github.com/the-momentum/open-wearables.git`.
- Upstream is pre-1.0 and churning. Merges from upstream are deliberate,
  scheduled, and reviewed — never `git pull upstream main` casually.
- Keep Kahunas changes isolated: new modules over edits to upstream files
  wherever possible; Kahunas docs live in this file (upstream `AGENTS.md`
  / `CLAUDE.md` stay upstream-shaped to minimize merge conflicts).
- Never print or commit credentials; env lives in `backend/config/.env`.

## Keep / replace / remove map

**Keep (the value of the fork):**

- Provider connectors and normalizers:
  `backend/app/services/providers/<provider>/` (`data_247.py`,
  `workouts.py`, `oauth.py`, `webhook_handler.py`) — they return plain
  `*Create` schemas before anything touches the DB, exactly what a
  pass-through needs.
- The RN SDK session contract: `sdk_token.py`, `token.py` (refresh
  rotation), `sdk_sync.py` ingestion route, `refresh_token` model.
- HealthKit/Health Connect/Samsung import parsing:
  `backend/app/services/apple/healthkit/import_service.py` and
  `backend/app/constants/series_types/`.
- Celery skeleton, Alembic, docker-compose shape.

**Replace:**

- Sample persistence (`timeseries_service`, `event_record_service`,
  `data_point_series*`, `event_record`, `workout_details`,
  `sleep_details`, `health_score`, archival) → tenant-forwarding pipeline
  with retry buffer + DLQ + contract-fault alarms (notifications-gateway
  status taxonomy, reversed).
- Auth: upstream developer/portal accounts, invitation codes, and global
  API keys are **not exposed**. Bridge sessions mint from WorkOS AuthKit
  tokens (`POST /v1/bridge/sessions`): verify against WorkOS JWKS, resolve
  the single org membership, resolve tenant via the control-plane Upstash
  org index (`kahunas:tenant:v1:org:<workosOrgId>`), fail closed on
  zero/multiple orgs.
- `user_connection` provider tokens: plaintext at rest upstream → encrypted
  (Fernet/KMS) in the fork.

**Remove (dead weight for a headless gateway):**

- `frontend/` (admin dashboard; backend coupling is only `frontend_url`,
  CORS default, and `/api/v1/config`), `mcp/`, and the dashboard-only
  routers (`dashboard`, `config`, `seed_data`, `priorities`, `archival`,
  `invitations`, `developers`).

## Known multi-tenancy holes in upstream (fix before exposure)

Ranked from the fork-baseline audit (2026-08-10):

1. `ApiKeyDep` is a global unscoped bearer of all authority (any key reads
   any user), and API keys are stored plaintext as their own primary key.
   Not exposed in the fork; remove with the portal surface.
2. `user` has no owner/tenant column and `external_user_id` is globally
   unique — the directory schema adds tenant ownership and scopes
   uniqueness.
3. `user_connection` uniqueness `(provider, provider_user_id)` is
   platform-wide; one Garmin account can only map to one user globally.
4. Provider OAuth credentials are per-process env vars (acceptable: one
   platform-wide app per provider is the Kahunas model), but webhook
   secrets defaulting to `secret_key` are not — give every webhook its own
   secret.
5. Global singletons: `archival_settings` (`id = 1` check), Redis keys
   without tenant segments, `sync_all_users` unscoped table scans, Svix
   fan-out paging all developers.
6. `GET /api/v1/oauth/{provider}/authorize` is unauthenticated and takes an
   arbitrary `user_id` — must require an authenticated principal.

## Ports (fleet registry)

| Port | Service |
| --- | --- |
| 8789 | wearables-gateway API (host) |
| 5435 | wearables-gateway Postgres (docker) |
| 6380 | wearables-gateway Redis (docker) |

Prefer `127.0.0.1` over `localhost`. Flower/Svix stay compose-internal.

## Gates

Upstream CI: `ruff check`, `ruff format --check`, `ty check`, pytest
against real Postgres 18 + Redis 7 (`TEST_DATABASE_URL`/`TEST_REDIS_URL`,
testcontainers fallback locally — serialize with the machine-wide
Testcontainers mutex `/tmp/kahunas-tc-run.sh` on shared rigs). `make test`
runs on the host via `uv`. Tests create schema from metadata, not Alembic —
migration changes need an explicit migration-apply check.

## M1 work breakdown (KAH-2426)

1. Strip surface: remove `frontend/`, `mcp/`, dashboard routers, seed-admin
   bootstrap; CI paths updated. No behavior change to kept routes.
2. Tenant directory + WorkOS session mint (`/v1/bridge/sessions`), replacing
   developer/API-key auth on all exposed routes; encrypt
   `user_connection` tokens.
3. Forwarding pipeline: replace the two storage chokepoints with the
   K2 delivery worker (control-plane service token, `idempotency-key`,
   retry/DLQ, status taxonomy); drop sample tables in a fork migration.
4. Schema review + privacy: prove no samples at rest, consent-withdrawal
   and DSR erasure routes over operational state.

One atomic commit per task; Devin review is the merge gate.
