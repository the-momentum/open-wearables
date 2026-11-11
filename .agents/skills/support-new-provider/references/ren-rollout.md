# Ren rollout: credentials, deploy, verification, handoff

Facts below were verified on 2026-11-11 from `buildspec.yml`, `ren-infra` and
ren-backend `origin/main`. For anything account-specific that looks stale,
check `ren-bbb/areas/eng/` and ask Ryan (he owns AWS and the OW fork).

## How Ren runs Open Wearables

- **One deployment, no staging.** A single OW deployment (ECS cluster
  `open-wearables`, us-east-1) serves Ren staging *and* production. Every push
  to the fork's `main` runs the `open-wearables` CodeBuild project, which
  builds and deploys backend, worker, beat and frontend from `buildspec.yml`.
  Merging is deploying.
- **New providers ship dark.** On startup OW seeds settings and priority rows
  for every `ProviderName`, enabled by default (`credentials_configured=false`
  until secrets exist). Ren users still can't see the provider: MAS lists
  `GET /api/v1/oauth/providers?enabled_only=true` but skips any slug missing
  from ren-backend's `_PROVIDER_CATEGORIES`. So the fork PR can merge before
  the Ren-side PRs, and it should.
- **Public URLs.** `API_BASE_URL=https://api.ren.so`. Listener rules on
  `ren-mas-alb` (`ren-infra/load_balancers.tf`) already send these paths to the
  OW backend, for every provider slug: `/api/v1/oauth/*/callback`,
  `/api/v1/oauth/callback/*`, `/api/v1/oauth/success`, `/api/v1/oauth/error`
  and `/api/v1/providers/*/webhooks`. The rest of OW, including `authorize`,
  is reachable only inside the VPC: MAS calls it over Cloud Map. No
  load-balancer change is needed. For a provider `<slug>`:
  - OAuth redirect URI to register with the provider:
    `https://api.ren.so/api/v1/oauth/<slug>/callback`
  - Webhook URL, only if webhooks are used:
    `https://api.ren.so/api/v1/providers/<slug>/webhooks`
- **Pull mode.** OW beat runs `sync_all_users` every `SYNC_INTERVAL_SECONDS`.
  ren-backend's measurement-cacher pulls from OW hourly, and DAS also reacts to
  OW's outgoing `sync.completed` webhook (Svix). *Incoming* provider webhooks
  stay off unless an admin switches that provider's live-sync mode, so a
  `rest_pull` provider is all Ren needs.
- **Secrets.** AWS Secrets Manager, us-east-1. Provider app credentials live
  in `ren-<slug>-client-credentials` as a JSON object
  `{"client_id": "...", "client_secret": "..."}`. ECS resolves single keys
  with `valueFrom: "<arn>:client_id::"`. The task execution role's
  `ren-secrets-read` policy covers `ren-*`, so no IAM change is needed.
  Withings is the documented exception: two plain-string secrets. Don't copy
  it.
- **Admin access** to the dashboard and API is through SSM port-forwarding via
  the jumphost. The exact commands are in the header comment of
  `buildspec.yml`.

## 1. `buildspec.yml` wiring (part of the provider PR)

Use the **optional** pattern (the same one as `GOOGLE_PROJECT_ID`). The secret
usually doesn't exist when the code merges, because developer-program approval
can take weeks. With the mandatory pattern, a missing secret becomes an
invalid `valueFrom`, the new task definitions fail to start, and the
deployment circuit breaker rolls back **every** OW service, not just this
provider.

```yaml
# env.variables: next to the other provider secrets
    # COROS app credentials ({"client_id","client_secret"}). Optional: the
    # provider stays credentials_configured=false until the secret exists.
    COROS_CREDENTIALS_SECRET: ren-coros-client-credentials
```

```bash
# build phase: next to GOOGLE_PROJECT_ID_ARN
        COROS_CREDENTIALS_ARN="$(secret_arn "$COROS_CREDENTIALS_SECRET" 2>/dev/null || true)"
# in the BACKEND_SECRETS jq call, add an argument:
          --arg coros_credentials "$COROS_CREDENTIALS_ARN" \
# and extend the program's tail after the google_project_id conditional:
          ] + (if $google_project_id != "" then
            [{"name":"GOOGLE_PROJECT_ID","valueFrom":$google_project_id}]
          else [] end)
          + (if $coros_credentials != "" then [
            {"name":"COROS_CLIENT_ID","valueFrom":($coros_credentials + ":client_id::")},
            {"name":"COROS_CLIENT_SECRET","valueFrom":($coros_credentials + ":client_secret::")}
          ] else [] end)')"
```

- Worker and beat inherit the secret through `WORKER_BEAT_SECRETS`, which is
  filtered from `BACKEND_SECRETS`. Nothing else to add. They need it, because
  token refresh and API calls run in the worker.
- Task definitions are built at deploy time. Creating the secret later takes
  effect on the **next** deploy: the next push to `main`, or a manual
  `aws codebuild start-build --project-name open-wearables`, which only a
  human runs.
- Keep lines at or under 100 characters (PR #21 wrapped the file).
- Dry-run the edited jq program locally with dummy `--arg` values, once with
  the ARN empty and once set, before you commit. A syntax error here breaks
  every deploy.
- Non-secret overrides (a scope string, say) go in `SHARED_ENVIRONMENT`. Avoid
  them unless the default in `config.py` is wrong for Ren.
- Webhook shared secrets: prefer deriving from `SECRET_KEY` in `config.py`
  (see `touchpoints.md` § C), so there is no extra secret to wire.

## 2. Human-only steps (ask the user; an agent can't do these)

1. **Developer access.** Apply for or create the provider's developer app.
   Many vendors gate API access behind a partner application, COROS among
   them. Record the approval status in the PR.
2. **Register the redirect URI** `https://api.ren.so/api/v1/oauth/<slug>/callback`.
   For local testing also register
   `http://localhost:8000/api/v1/oauth/<slug>/callback` if the portal allows a
   second one.
3. **Create the secret** `ren-<slug>-client-credentials` in us-east-1 with
   `client_id` and `client_secret`.
4. **Webhooks** (only if built and wanted): register
   `https://api.ren.so/api/v1/providers/<slug>/webhooks` in the portal, or
   rely on `webhook_registration_api` when an admin switches live-sync mode
   to `webhook`.

An agent may check that the secret **exists** (AWS MCP, `DescribeSecret` by
name). Never call `GetSecretValue`, and never paste credential values into
chat, code, commits or the PR.

## 3. Local end-to-end (needs development credentials)

```bash
# backend/config/.env (gitignored): COROS_CLIENT_ID=... COROS_CLIENT_SECRET=...
docker compose up -d && docker compose logs -f app
# Dashboard http://localhost:3000 (admin@admin.com / your-secure-password):
# create a test user and an API key.
curl "http://localhost:8000/api/v1/oauth/coros/authorize?user_id=<test-uid>"
#   open authorization_url, sign in with a test account, expect the success page
curl -X POST -H "X-Open-Wearables-API-Key: <key>" \
  "http://localhost:8000/api/v1/providers/coros/users/<test-uid>/sync/historical"
docker compose logs -f celery-worker   # the sync run and its per-data-type counts
```

Check the data on the dashboard's user page, the timeseries, workouts and
sleep endpoints, and `GET /api/v1/meta/coverage`. Paste redacted evidence
(counts, a sample response with personal values removed) into the PR. The PR
template asks for proof against a real account.

## 4. Merge

- The PR goes to `frontbacklabs/open-wearables` `main`, **never** upstream.
  Ryan reviews and merges.
- Opening an upstream PR to contribute the provider is optional, and an
  outward-facing action. Only do it if the user asks; if upstream merges it,
  the next sync adopts it (`upstream-sync.md`).

## 5. Post-deploy verification (after the CodeBuild run finishes)

Through the SSM tunnel (`localhost:8000` and `localhost:3000`):

- `GET /api/v1/oauth/providers` has `<slug>` with `is_enabled: true`,
  `live_sync_mode: "pull"`, and `credentials_configured: true` once the secret
  exists.
- The backend, worker and beat services are healthy. The `ren-health` skill
  in ren-bbb checks production health.
- Once credentials exist, connect a **test** account on a dedicated test
  Firebase UID (never a real user's), run a historical sync, and confirm data
  arrives.

## 6. Ren-side handoff (separate repos, separate PRs)

The provider reaches users only after these. Each repo has its own
`AGENTS.md` and skills; follow them. Offer to do these PRs. Don't fold them
into the fork PR.

**ren-backend** (follow `.agents/skills/integrating-self-hosted-open-wearables`
and `.agents/skills/semantic-model-management`). Precedent: commit `3663381`,
"feat(integrations): support the Withings provider".
- An Alembic migration adding the slug to the `app_data.integration_name`
  enum (copy `migrations/versions/0071_withings_provider.py`).
- `src/services/data_access/orm.py`: `integration_name_type`.
- `src/shared/types.py`: `IntegrationName`.
- `src/services/mobile_api/integrations.py`: `_PROVIDER_CATEGORIES`
  (`device`, `data_platform` or `app`). This entry is what makes MAS show the
  provider.
- Regenerated `openapi/*.json` and the migration tests.
- Confirm DAS maps every SeriesType the provider emits into measurements. A
  brand-new series type needs mapping there.

**ren-swift** (iOS):
- `Ren/Sources/Networking/MobileAPI/MobileAPIContracts.swift`: the provider
  enum, plus the regenerated `MobileAPI/Generated/*` client.
- `Ren/Sources/Wearables/ProviderLogo.swift` (and a logo asset),
  `WearableConnectionService.swift`, `WearableProviderDetailView.swift`.
- `Ren/Sources/Analytics/AnalyticsEvent.swift`.

**ren-bbb** (push to `main` per its `AGENTS.md`), at the right time:
- `areas/eng/system-overview.md` (Wearables ingestion list): when the
  ren-backend PR merges, because the provider is connectable from then on.
- `areas/product/features.md` (the **public** supported-device list): only once
  an app build that can connect the provider has shipped. A provider merged in
  OW but hidden from the app must not be advertised.

These locations were verified on 2026-11-11. To find the current ones, grep
each repo for an existing provider slug such as `sensorbio`.
