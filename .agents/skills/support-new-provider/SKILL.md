---
name: support-new-provider
description: >-
  Standard procedure for supporting a new wearable or health-data provider
  (COROS, Amazfit, Eight Sleep, ...) that upstream Open Wearables lacks, in
  the frontbacklabs/open-wearables fork. Covers the upstream preflight,
  provider research, strategy, OAuth, data handlers, marked shared-file
  registration, tests, docs, Ren's AWS deploy wiring, the Ren-side handoff,
  and the fork-only provider registry that protects the work in upstream
  syncs. Use for "support <provider> in our open wearables fork",
  "add/integrate <provider>", and for any upstream sync that touches a
  fork-only provider.
---

# Support a new provider in the Open Wearables fork

`frontbacklabs/open-wearables` is Ren's fork of `the-momentum/open-wearables`.
Ren's iOS app and backend reach every wearable through it. This skill takes
a request like **"support COROS in our open wearables fork"** to a reviewed PR
on the fork that:

- adds the provider the way upstream's own providers are built;
- registers it as a **fork-only provider**, so upstream syncs can't silently
  drop it;
- wires its credentials into Ren's deployment;
- lists exactly what is left for humans and for the Ren repos.

Examples use slug `coros` and display name `COROS`; substitute the real ones.

## Ground rules

- Read the root `AGENTS.md` first, especially the **fork-wins rules**, which
  apply to everything you write. Then read `backend/AGENTS.md` (layers,
  logging, Sentry and PII rules).
- Work on a branch `feat/provider-<slug>` off a fresh `origin/main`. Open the
  PR against the **fork's** `main`. Never push to `main`, never open an
  upstream PR unless asked, and never deploy by hand. Merging to `main`
  deploys to the one OW deployment that serves Ren staging *and* production.
- No real health data, credentials or personal data in code, fixtures, logs,
  commits or PRs.
- **The upstream-sync rule** (the reason this skill exists):
  **an upstream sync must not overwrite, drop or break anything the fork needs
  for a fork-only provider, unless upstream now natively supports that
  provider; then upstream's implementation replaces ours.** It is enforced by
  `fork-providers.json` with `scripts/fork_providers.py` and fork-wins rule 9
  in `AGENTS.md`. Details: `references/upstream-sync.md`.
- Don't block on credentials. Build and test against the provider's
  documented API with fixtures, and list the live checks as pending.
- Upstream's `docs/dev-guides/how-to-add-new-provider.mdx` (linked from the
  root and backend `AGENTS.md`) is useful background but partly out of date.
  Where it disagrees, the code wins, then this skill.

**Stop and ask the user only at these points:**
1. Preflight finds upstream support, partial support, or an open upstream PR
   for this provider (phase 0).
2. The provider has no documented server-side API that OW's OAuth-and-REST
   model fits. Examples: only an on-device SDK (that is mobile SDK work), only
   an MCP server or an AI-assistant connector, only a manual file export, or
   API docs available only under a partner agreement Ren doesn't have yet.
   Report what the provider does offer and stop. Check ren-bbb `digests/` and
   `decisions/` first: someone may already have evaluated the provider (for
   COROS, Ryan noted on 2026-11-06 that its MCP doesn't fit the current setup).
3. Covering what Ren needs requires scopes or data beyond the minimum, or
   paid API tiers.

## Phase 0: Preflight. Does this need building at all?

```bash
git fetch upstream && git fetch origin
git switch -c feat/provider-coros origin/main
python3 .agents/skills/support-new-provider/scripts/fork_providers.py preflight coros [--alias <other name>]
```

1. **Pick the slug** before running preflight. It is what upstream would
   name it: the brand in lowercase snake_case (`coros`, `eight_sleep`). Check
   upstream's "Provider request: X" issue title. It must not be a substring of
   another `ProviderName` value or contain one, because
   `from_source_string` matches by substring; preflight checks this. Choosing
   upstream's likely name now turns a future adoption into a code swap
   instead of a data migration.
2. Preflight also prints how many upstream commits the fork is missing. If
   that is large, the next sync will probably change APIs your provider uses.
   Build anyway, note it in the PR, and expect to adapt the provider during
   that sync (preserve mode in `references/upstream-sync.md`).
3. Act on the verdict:

| Verdict (exit code) | Do this |
|---|---|
| `ALREADY_IN_FORK` (3) | Nothing to build. Only the deploy wiring and Ren handoff remain (`references/ren-rollout.md`). Tell the user. |
| `UPSTREAM_NATIVE` / `UPSTREAM_PARTIAL` (2) | **Don't build a bespoke integration.** Tell the user upstream has it. The path is the next upstream sync, or cherry-picking upstream's provider commits onto a branch, followed by the deploy wiring and handoff. |
| Exit 1 | The slug has a problem (format or substring overlap). Pick another and re-run. |
| `NOT_IN_UPSTREAM` (0), with an **open upstream PR** for this provider in the list | Ask: port that PR as our fork-only implementation (recommended when it looks complete, since adoption later is near-trivial), or build our own? |
| `NOT_IN_UPSTREAM` (0), nothing in flight | Continue to phase 1. |

## Phase 1: Research the provider and write the integration brief

Read the provider's developer docs and fill this in. It goes in the PR body,
and the docs page in phase 5 reuses it.

```markdown
## <Display> integration brief
- Access: developer/partner program? approval needed? sandbox or test accounts?
- OAuth: authorize URL · token URL · PKCE? · client auth (BODY | BASIC_AUTH) · scopes (minimal set) ·
  token lifetime and refresh · revoke endpoint · user-identity endpoint (stable provider user id)
- Data endpoints: for each, the path, params (date range, paging), units, timezone semantics, rate limits
- History limit: how far back (max_historical_days)
- Push: none | ping (refetch) | stream (full payload); signature scheme; subscriptions: portal | API (app-level | per-user)
- Mapping: each provider metric → SeriesType / EventRecordDetail field / HealthScoreCategory (existing ones; flag any gap)
- Archetype and exemplar: <from references/architecture.md>
```

Choose the **archetype** and the **exemplar provider** to copy from the table
in `references/architecture.md`. For a typical OAuth plus REST provider with
sleep, daily data and workouts, that is `sensorbio`. Read the exemplar's
strategy, oauth, coverage, data_247, workouts and tests before writing code.

## Phase 2: Build the provider module (owned files)

Create the owned files listed in `references/touchpoints.md` § A by copying
the exemplar's structure, following `references/implementation-rules.md`:

- `backend/app/services/providers/coros/`: `__init__.py`, `strategy.py`,
  `coverage.py`, `oauth.py`, plus `workouts.py`, `data_247.py` and
  `webhook_handler.py` / `webhook_service.py` as the brief requires.
- `backend/app/schemas/providers/coros/`: Pydantic models of the API
  payloads.
- `backend/app/constants/workout_types/coros.py`, imported directly. Add
  `constants/series_types/coros.py` if needed.
- `backend/app/static/provider-icons/coros.svg`.

The essentials:
- `user_id` is always `str` (fork-wins rule 1).
- Use `coverage.py` as the single source of truth for what the provider emits.
- Make HTTP calls through `make_authenticated_request`, and store raw
  responses with `store_raw_payload`.
- In `load_and_save_all`, run one `sync_run` step per data type.
- Day values carry `period`, session values carry `session`.
- UTC-aware datetimes everywhere.
- Prefer existing `SeriesType` / `WorkoutType` values.

## Phase 3: Register in shared files (few, small, marked)

Make the edits in `references/touchpoints.md` § B. Every added line carries
`# fork-provider: coros`, or sits inside a marked block:

- `schemas/enums/provider.py`: the member in the fork block after `INTERNAL`,
  and a `DEFAULT_PROVIDER_PRIORITY` entry numbered **101+**.
- `services/providers/factory.py`: the import, and the case **first** in the
  `match`. Add the enum member and the factory case together.
- `config.py`: a marked block with `coros_client_id`, `coros_client_secret`
  and `coros_default_scope` (no `_redirect_uri`).
- `backend/config/.env.example`: a marked placeholder block.
- `docs/providers/supported.mdx`: one row.

Then § C, only where the provider needs it: device type, score ranges, webhook
secret validator, log redaction, celery tasks, a fork-range `SeriesType`.
Respect § E (do-not-touch). No migrations, no frontend changes.

## Phase 4: Tests and quality gates

Write `backend/tests/providers/coros/` (`conftest.py` plus the files in
`references/implementation-rules.md` § Tests). Fixtures follow the
documented API shapes, with no real user data. Then, from `backend/`:

```bash
uv run ruff check . --fix && uv run ruff format . && uv run ty check .
uv run pytest tests/providers/coros tests/providers/test_provider_coverage.py \
  tests/providers/test_provider_factory.py tests/repositories/test_provider_priority_repository.py \
  tests/schemas/test_provider_name.py tests/services/test_provider_settings_service.py -q
uv run python scripts/generate_coverage_docs.py && uv run python scripts/export_openapi.py
uv run pytest -q   # whole suite; compare with the same run on main
```

Docker must be running (testcontainers). **The fork runs no CI tests on
PRs**, so these local runs are the gate. Report any failure that is new
against `main`; failures already on `main` (UUID-assuming upstream tests) are
expected.

## Phase 5: Docs

- `docs/providers/coros-api-integration.mdx`: modelled on
  `sensorbio-api-integration.mdx`. Cover access requirements, credentials,
  the redirect URI (`{API_BASE_URL}/api/v1/oauth/coros/callback`), scopes,
  data coverage, sync behaviour and known limits. State near the top that it
  is a fork-only integration.
- The `supported.mdx` row is in phase 3. `coverage.mdx` and `openapi.json` are
  regenerated, never hand-edited.

## Phase 6: Register as a fork-only provider (the sync guard)

```bash
python3 .agents/skills/support-new-provider/scripts/fork_providers.py register coros \
  --display-name COROS [--alias <name upstream might use>] --note "<one line: archetype, access status>"
python3 .agents/skills/support-new-provider/scripts/fork_providers.py verify   # exit 0
```

`register` records the owned paths and, per shared file, how many lines
mentioning the slug the fork carries beyond upstream's. Review the diff of
`fork-providers.json` (are all your shared files listed?) and commit it with
the provider. Re-run `register` whenever you change shared files later.

## Phase 7: Ren deployment wiring

Follow `references/ren-rollout.md`:
- § 1: `buildspec.yml`, using the **optional-secret** pattern so a missing
  secret can't break deploys. Dry-run the jq.
- § 3: the local end-to-end, if development credentials exist.
- § 2: list the human-only steps for the user. They are developer access, the
  redirect URI `https://api.ren.so/api/v1/oauth/coros/callback`, and the
  Secrets Manager secret `ren-coros-client-credentials`.

## Phase 8: PR and handoff

- Use conventional commits; one logical commit per phase is fine. The PR title
  is `feat(integrations): add COROS provider (fork-only)`. Fill in
  `.github/PULL_REQUEST_TEMPLATE.md` and include the integration brief, the
  test evidence (commands plus results; whether live-tested), the
  human-only steps still pending, and "Registered in `fork-providers.json`".
- Merging deploys immediately, but the provider stays dark for Ren users until
  ren-backend lists it in `_PROVIDER_CATEGORIES`. Merge the fork PR first.
- Finish with a message to the user: PR link, what is verified and what
  isn't, pending human steps, and the Ren-side handoff list
  (`references/ren-rollout.md` § 6). Offer to open those PRs; don't fold them
  into this one.

## Definition of done

- [ ] Preflight run; verdict and any upstream PRs or issues noted in the PR
- [ ] Integration brief in the PR body; archetype and exemplar named
- [ ] Owned files: provider module, payload schemas, workout-type map, icon,
      tests, docs page
- [ ] Shared files: enum and priority (101+), factory, config, `.env.example`,
      `supported.mdx`, all marked; conditional ones only where needed;
      nothing from the do-not-touch list
- [ ] `user_id: str` throughout; scopes minimal; no health values or PII in
      logs or Sentry
- [ ] ruff, ty, provider tests and guard tests pass; full suite has no new
      failures against `main`; coverage docs and OpenAPI regenerated
- [ ] `fork_providers.py register` committed; `verify` exits 0
- [ ] `buildspec.yml` wired with the optional-secret pattern; jq dry-run
      passes
- [ ] PR open against the fork's `main`, with pending human steps and the
      Ren-side handoff listed

## Upstream syncs (summary)

Before and after every `git merge upstream/main`, run
`python3 .agents/skills/support-new-provider/scripts/fork_providers.py verify`.

| Result | Meaning | Action |
|---|---|---|
| `[OK]` | Fork-only provider intact, not in upstream | Preserve mode. Keep marked lines in conflicts (never take a shared file wholesale `--theirs`), and adapt the provider to upstream API changes. |
| `[MISSING]` | The merge dropped fork lines or files | Restore them from the fork side before committing the merge |
| `[NATIVE]` | Upstream now supports it | **Adoption: upstream wins.** Replace our implementation with upstream's, keep Ren's deploy wiring working, handle data continuity, list lost coverage, then `unregister`. |
| `[PARTIAL]` | Upstream has part of it | Keep ours, make it compile, tell the user |

Full procedure: `references/upstream-sync.md`.

## Files in this skill

| File | Use it for |
|---|---|
| `references/architecture.md` | How providers plug in, components, capabilities, archetypes and exemplars, where each value is stored, guard tests |
| `references/touchpoints.md` | Every file to create or edit, marker convention, conditional edits, do-not-touch list |
| `references/implementation-rules.md` | Per-component conventions, fork rules in code, new SeriesType rules, tests, verification commands |
| `references/upstream-sync.md` | The sync rule, preserve mode, adoption mode, partial support |
| `references/ren-rollout.md` | `buildspec.yml`, secrets, human steps, local and post-deploy checks, ren-backend / ren-swift / ren-bbb handoff |
| `fork-providers.json` | The registry of fork-only providers (written by the script) |
| `scripts/fork_providers.py` | `preflight`, `register`, `verify`, `unregister`, `list` (stdlib Python 3.8+) |
