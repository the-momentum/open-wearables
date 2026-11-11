# Upstream syncs and fork-only providers

## The rule

**An upstream sync must not overwrite, drop or break anything the fork needs
to support a fork-only provider, unless upstream now natively supports that
provider. In that case upstream's implementation replaces ours.**

Root `AGENTS.md`, fork-wins rule 9, points here. The rule binds every merge of
`upstream/main` into the fork: the biweekly Devin sync on
`sync/upstream-YYYY-MM-DD` branches, a manual sync, or a cherry-pick.

**Fork-only provider**: listed in
`.agents/skills/support-new-provider/fork-providers.json`.

**Natively supported upstream**: on the upstream ref being merged, a
`ProviderName` member whose value is our slug (or one of the entry's
`aliases`), together with a strategy module
`backend/app/services/providers/<slug>/strategy.py` or a factory case for it.
`fork_providers.py verify` checks exactly this. These do **not** count:

- a mention in a comment, docstring or doc (upstream's
  `models/user_connection.py` has named "coros" for years without supporting
  it);
- an open issue or PR, or an unmerged upstream branch;
- the vendor's data arriving through another provider, such as a COROS
  watch syncing to Apple Health.

If upstream ships a provider for the same brand but you cannot tell whether it
is the same API product, stop and ask the user.

## On every upstream sync

```bash
git fetch upstream && git fetch origin
git switch -c sync/upstream-$(date +%F) origin/main
python3 .agents/skills/support-new-provider/scripts/fork_providers.py verify   # before the merge
```

| `verify` says | Mode for that provider |
|---|---|
| `[OK]` | **Preserve** (below) |
| `[PARTIAL]` | **Preserve**, and read upstream's change. See "Partial upstream support". |
| `[NATIVE]` | **Adoption** (below), in this same sync PR, as its own commit after the merge commit |

Then `git merge upstream/main`. Merge, never rebase: the fork keeps
upstream's history.

### Preserve mode: fork wins

1. **Conflicts in shared files.** In any hunk that contains
   `fork-provider: <slug>` or the slug, keep upstream's change *and* our lines.
   Never resolve a shared file wholesale with `--theirs` or `-X theirs`.
   That is exactly how fork lines get lost.
2. **Generated files** (`docs/openapi.json`, `docs/providers/coverage.mdx`):
   take either side and regenerate (commands in `touchpoints.md` § D).
3. **Owned paths** cannot conflict while the provider is fork-only. If one
   does, upstream has added that path: re-run `verify`, because you are
   probably in adoption mode.
4. **Adapt, don't drop.** Upstream refactors whatever it likes: base
   templates, `api_client`, `Sync247Result`, schemas, SeriesType names. Our
   provider code is invisible to upstream's maintainers, so their refactor
   will not update it. Update the fork provider to the new API inside the sync
   branch, and treat a fork provider that no longer imports, type-checks or
   passes its tests as a merge bug. If upstream removed a shared-file extension
   our provider relied on (say an `api_client` keyword), prefer moving that
   logic into the provider's own module over re-adding the shared edit.
5. **After resolving**, before committing the merge:
   ```bash
   python3 .agents/skills/support-new-provider/scripts/fork_providers.py verify   # must exit 0
   cd backend && uv run ruff check . && uv run ty check . && \
     uv run pytest tests/providers/<slug> tests/providers/test_provider_coverage.py -q   # per fork provider
   ```
   If line counts moved for a legitimate reason, such as upstream reformatting
   a file you have checked by hand, re-run `fork_providers.py register <slug>`
   and commit the updated entry.
6. **In the sync PR description**, add one line per fork-only provider:
   preserved, adapted (what changed), or adopted (see below).

### Adoption mode: upstream wins

Upstream now ships the provider, so our bespoke implementation goes. Do not
keep our code because it "does more". Coverage we lose is reported for a
human to decide, not quietly kept.

**1. Compare first (record findings for the PR; change nothing yet):**

| Compare | Where | Why it matters |
|---|---|---|
| Slug | upstream `ProviderName` value vs ours | A different slug changes stored data and Ren's vocabulary (step 4) |
| Settings names | upstream `config.py` `<slug>_*` fields vs ours | `buildspec.yml` env var names must follow upstream's |
| Default scopes | upstream `<slug>_default_scope` vs ours | Existing grants carry our scopes only |
| OAuth path and auth method | upstream `oauth.py`, `settings._oauth_path` | The redirect URI registered in the provider portal must still match |
| Coverage | `git show upstream/main:backend/app/services/providers/<slug>/coverage.py` vs ours | Series, fields and scores we emitted that upstream does not: Ren may lose data |
| Stored-data conventions | SeriesType per metric, workout start/end handling, `external_id` format, any fork-range (900–999) SeriesType we added | Decides whether history needs a relabel or dedupe (step 4) |

**2. Take upstream's implementation:**

- Owned paths: where upstream has the file, take theirs
  (`git checkout upstream/main -- <path>`); where it doesn't, delete ours
  (`git rm`). Our helper modules, schemas, tests and docs page go. Upstream's
  replace them.
- Shared files: remove every `fork-provider: <slug>` line and block, and keep
  upstream's lines for that provider (enum position, factory case, config
  fields, priority number, device type, score ranges, ...).
- Re-apply fork-wins rules 1–8 to the code you just took (most often: str-ify
  `user_id: UUID`).
- `python3 .agents/skills/support-new-provider/scripts/fork_providers.py unregister <slug>`.

**3. Keep Ren's deployment working.** `buildspec.yml` stays fork-owned: it is
deploy wiring, not provider implementation.

- If upstream's settings names differ from ours, rename the
  `<SLUG>_CLIENT_ID` / `<SLUG>_CLIENT_SECRET` entries in `buildspec.yml` and
  keep the same Secrets Manager secret.
- If upstream's default scope asks for more than Ren's existing grants and
  provider app cover, pin `<SLUG>_DEFAULT_SCOPE` to Ren's scopes through the
  buildspec environment. Then confirm upstream's code tolerates a missing
  scope; if it doesn't, gate it the way fork-wins rule 3 gates Google Health.
- If upstream's redirect path differs, the provider portal registration has to
  change before the deploy. That is a human step, so flag it in the PR.

**4. Data continuity.** OW's Postgres holds real users' data: one deployment
serves Ren staging and production.

- **Same slug** (the expected case, because phase 0 picks upstream's likely
  name): connections, tokens, data sources and settings rows carry on as they
  are.
- **Different slug**: needs an idempotent data migration in
  `backend/scripts/data_migrations/` with `--dry-run`, wired into
  `scripts/start/app.sh` (precedent: `split_google_provider.py`). It renames
  `provider` in `user_connection`, `data_source`, `provider_settings`,
  `provider_priority` and `health_score`, and checks `sync_run` and
  `data_type_coverage`. It also needs a coordinated ren-backend change, because
  DAS stores OW slugs in `app_data.integration_name`. **Stop and get the
  user's go-ahead before merging a sync that does this.**
- **Different metric mapping** (we stored a metric under one SeriesType,
  upstream under another, or we used a fork-range type): old rows stay under
  our mapping. Relabel them with a data migration (precedents:
  `scripts/data_migrations/relabel_ultrahuman_*`) and narrow
  `data_type_coverage` as `backend/AGENTS.md` § Data migrations requires.
  Never delete a fork SeriesType definition that has rows; keep it or move it
  to `RETIRED_SERIES_TYPE_IDS`.
- **Different event identity** (other start/end handling or `external_id`):
  the next sync can duplicate past workouts and sleeps, because event records
  are unique per `(data_source_id, start_datetime, end_datetime)`. Estimate
  the impact with a read-only query first. Dedupe with a data migration if
  needed.

**5. Lost coverage.** List anything Ren consumed that upstream's
implementation doesn't emit under **"Lost with adoption"** in the sync PR
description, addressed to Ryan. Do not re-add bespoke code in the sync.
Re-adding a field on top of upstream's provider is a separate decision,
recorded as a new fork-wins rule (precedent: rule 8, Oura sleep latency).

**6. Verify.** `verify` exits 0. Upstream's provider tests pass with the fork
rules applied. The full suite shows no new failures against `main`. After the
merge deploys, re-run the post-deploy checks in `ren-rollout.md` § 5 against
the shared production deployment.

## Partial upstream support

Upstream has an enum member or a strategy module, but not a registered
provider: half-merged work, or a renamed concept. Keep ours (preserve mode)
and make the merge compile. If upstream added the same enum member, keep
exactly one: upstream's line, without our duplicate. Re-run `register` so the
counts match the new baseline, and describe it in the PR so the user knows
native support is coming.

## Why it is shaped this way

- Upstream's maintainers can't see fork-only code, so any upstream refactor
  can break it silently. The registry, the markers and `verify` make that
  breakage loud.
- Once upstream supports a provider, a parallel implementation would double
  the merge cost on every sync and miss upstream's fixes. So upstream wins.
- Picking upstream's naming conventions up front (slug, settings names, ID
  ranges that can't collide) turns adoption into a code swap instead of a data
  migration.
