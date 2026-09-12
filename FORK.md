# FORK.md — how this fork diverges from upstream

Fork of [the-momentum/open-wearables](https://github.com/the-momentum/open-wearables),
self-hosted on a single-node k3s cluster.

`AGENTS.md`, `backend/AGENTS.md` and `frontend/AGENTS.md` are **upstream's** and
describe the project generally. **This file is the fork-specific layer**: how our
divergence is structured, and the failure modes it has actually produced. Most of
what follows was learned by breaking something.

---

## 1. The ow-patches system

We deliberately avoid editing upstream source. Instead, `ow-patches/local/<id>.py`
files monkey-patch upstream symbols at import time. `backend/app/__init__.py`
calls `_apply_ow_patches()` once at process startup, which loads
`ow-patches/apply.py` and installs whatever is enabled.

Why: a `git merge upstream/main` then never conflicts on those files, so
reconciles stay cheap.

**`ow-patches/PATCHES.md` is the registry and the source of truth.** Every patch
has an entry with `what_we_changed`, `retire_when` and a `replacement_kind`.

### Three ways a patch reaches the running app

`PATCHES_ENABLED` in `apply.py` is **only a flag dict — it does not install
anything.** Installation is driven by three separate mechanisms:

| Mechanism | Where | Notes |
|---|---|---|
| `_STANDALONE_PATCHES` | tuple in `apply.py` | `apply_patches()` iterates this and calls each module's `install()` |
| `_COMPOSED_PATCHES` | tuple in `apply.py` | wired by `_compose_sleep_summaries` / `_compose_activity_summaries`; note a composer must call `install()` explicitly if the patch also replaces a symbol |
| inline in a composer | code in `apply.py` | the composer implements the behaviour directly; the patch file is documentation only (currently only `fix-summary-timezone-echo`) |

**Adding a flag without wiring it produces a patch that reports as enabled
everywhere and never runs.** That has happened twice — see §3.

Current state (2026-09-13): 15 backend patches registered, 12 enabled, 3 retired, 8 standalone, 3 composed (plus 3 `structural` entries: celery-late-acks, historical-sync-chunking, frontend-display-timezone).

### `replacement_kind` and why it matters

- `wholesale-replace` — reimplements an upstream method body. **These shadow
  upstream.** A merge will not conflict (we never touch the upstream file), so if
  upstream rewrites that method our copy silently wins and drops their changes.
  This is the single most dangerous category.
- `decorate` — wraps upstream and post-processes. Inherits upstream changes.
- `structural` — a real source edit (schema field, DB column, frontend). Conflicts
  normally at merge time.
- `standalone` — a self-contained function swap with no upstream body to go stale.

---

## 2. Hard rules

**Never patch a file the fork owns.** Patches exist to avoid upstream conflicts.
Applying one to fork-owned source buys every shadowing hazard and none of the
benefit. `fix-calories-total-mislabelled` monkey-patched
`GarminConnect247Data.save_daily_stats_for_date` — a fork-only file — and silently
shadowed later edits to that same method. New fields simply never ran, with no
error and no failing test. It happened a second time:
`fix-garmin-connect-rate-limit-backoff` replaced `load_and_save_all` in the same
file and hid the VO2max sync added on 2026-08-29 until the 2026-09-13 reconcile
audit noticed (retired into source that day). Fork-owned code is edited directly.

**`garmin_connect/` is fork-only.** It does not exist upstream. Edit it directly;
it will never conflict.

**The image must contain `ow-patches/`.** See §4 — this is not optional and has
bitten production.

**Assume a `wholesale-replace` patch is stale until you have diffed it.**
"Installs without raising" is a very weak signal.

**Prefer range-capable provider endpoints over per-day loops.** Request volume is
the binding constraint on `garmin_connect` — a per-day endpoint multiplies by the
size of the sync window. This is not theoretical: an hourly sync with a per-day
loop got the Garmin account IP rate-limited and then **locked**.

---

## 3. Failure modes this system has actually produced

Each of these was silent. None raised, none failed a test at the time.

1. **The whole patch directory missing from the image** → every patch inert, app
   boots clean. `_apply_ow_patches()` returned early when it could not find the
   directory. Now guarded by `OW_PATCHES_REQUIRED`.
2. **A flag with no wiring** → `fix-garmin-connect-rate-limit-backoff` shipped
   inert because its id was added to `PATCHES_ENABLED` but not
   `_STANDALONE_PATCHES`. Its own tests passed because the fixture called
   `install()` directly.
3. **A composer loading a module without installing it** →
   `fix-sleep-stages-missing`'s Ultrahuman half was inert while PATCHES.md
   asserted it was live.
4. **A wholesale-replace patch falling behind upstream** → upstream added
   `DataSource.device_type` to two aggregate queries; both UTC-bucketing patches
   shadowed it away, so the API returned `device_type: null` forever. Every
   consumer reads it with `.get()`, so nothing failed.
5. **A test loading its own copy of a patch** → the rate-limit test registered the
   patch under a different module name and installed it over the real one, both
   polluting other tests and hiding (2).
6. **A rebase dropping a fork-only keyword argument** → reconciling
   `fix-spo2-respiratory-missing` onto upstream's rewritten `load_and_save_all`
   copied upstream's body faithfully and lost `source=` from the `vo2_max` and
   `active_time` constructors. Since a `data_source` row is keyed on
   `(user_id, device_model, source)`, those two series began writing to a second,
   NULL-source row — the provider's history split in half, with no error. The
   same shape from the other direction: `garmin_connect` set `device_model=` on
   its `EventRecordCreate` but on none of its eight `TimeSeriesSampleCreate`
   calls, so one watch resolved to two identities. **A faithful copy of
   upstream's body is not automatically a correct patch** — the fork's added
   arguments have to be re-applied deliberately, which is what Phase 4 of the
   reconcile skill is for.

### The four guard tests

Keep them green; they exist because of the list above.

| Test | Catches |
|---|---|
| `backend/tests/test_ow_patches_guard.py` | the directory missing from the image (`OW_PATCHES_REQUIRED`) |
| `backend/tests/test_ow_patches_installed.py` | a patch that is enabled but not actually installed — asserts every patched symbol's `__module__` is an `_ow_patches*` module, and that the flag dict and the wiring tuples agree |
| `backend/tests/test_ow_patches_column_drift.py` | a wholesale-replace patch that has dropped an ORM column upstream added |
| `backend/tests/test_ow_patches_identity_drift.py` | a patch or fork-owned provider that omits `source=` / is inconsistent about `device_model=` on a persisted-row constructor, splitting one device across two `data_source` identities |

---

## 4. Deployment

**`ow-patches/` lives at the repo root, outside the `./backend` build context**,
so upstream's `backend/Dockerfile` cannot `COPY` it. Without help, the image ships
without patches, `_apply_ow_patches()` finds nothing, and **every patch silently
no-ops** — while the structural halves (DB columns, schema fields, frontend edits)
are still present, producing "the field exists but is always null".

Three guards, keep all three:

1. **`Dockerfile.ow-patches`** (repo root) — fork-owned overlay layering
   `ow-patches` onto the upstream-built image and setting `OW_PATCHES_DIR` +
   `OW_PATCHES_REQUIRED=1`. CI and `scripts/build-push.sh` both build through it
   and then assert `apply.py` is present in the result.
2. **`OW_PATCHES_REQUIRED=1`** — turns a missing directory into a hard startup
   failure naming every path searched, instead of a silent skip.
3. **Deployment manifests must run the overlay image.** A plain
   `podman build ./backend` ships an unpatched image again.

Check a running cluster:

```bash
kubectl -n open-wearables exec deploy/app -- ls /root_project/ow-patches/apply.py
```

**Publishing** is `.github/workflows/publish-ghcr.yml` (fork-owned; upstream's
`publish-images.yml` targets Docker Hub credentials we do not have). The backend
builds in two steps — upstream image, then the overlay — and pushes to
`ghcr.io/<owner>/open-wearables-{platform,frontend}`. `scripts/build-push.sh` does
the same locally for fast iteration.

`VITE_API_URL` is **not** baked into the frontend image: `runtime-config.ts`
resolves it at runtime from container env, so one image serves any environment.
The deployment must set it, or the browser falls back to `http://localhost:8000`.

---

## 5. Reconciling with upstream

Use the **`upstream-reconcile` skill** (`.claude/skills/upstream-reconcile/`).
It encodes the full procedure, including the shadow audit that `check_upstream.py`
cannot do on its own.

Quick orientation:

```bash
git fetch upstream
python ow-patches/check_upstream.py          # drift report
python ow-patches/check_upstream.py --update-baseline   # ONLY after re-verifying
```

`ow-patches/.upstream-baseline` records the last fully-reconciled upstream commit.

> The baseline is refreshed only at the END of a reconcile, after every flagged
> `wholesale-replace` patch has been body-diffed. A refreshed baseline on
> unverified patches hides the drift from the next reconcile.

### `check_upstream.py` blind spots

It reports *which files upstream touched*, not whether our copy still matches. Two
specific gaps to compensate for manually:

- **Semantic drift.** It flagged the file that had lost `device_type`, but could
  not see the missing column. A human or an agent must diff the bodies.
- **`structural` patches, including everything frontend.** It reported
  `frontend-display-timezone` as "no drift / keep" while that patch owned most of
  the conflicts in the 2026-08 merge. A green row there means "not tracked", not
  "safe".

---

## 6. Fork-only additions worth knowing

| Thing | Where |
|---|---|
| `garmin_connect` provider (credential-based Garmin scraper) | `backend/app/services/providers/garmin_connect/` |
| Patch system | `ow-patches/` |
| Image overlay | `Dockerfile.ow-patches` |
| GHCR publishing | `.github/workflows/publish-ghcr.yml` |
| Local build/deploy | `scripts/build-push.sh`, `make push_local_k3s` |
| Reconcile skill | `.claude/skills/upstream-reconcile/` |
| Longevity tracking context | [`LONGEVITY.md`](./LONGEVITY.md) |

[`LONGEVITY.md`](./LONGEVITY.md) records which of this platform's signals carry
outcome evidence, which are vendor decoration, and the device-vs-population
calibration offsets that otherwise corrupt any benchmarking. Read it before
adding a health metric to a dashboard or setting a target on one — several
prominent wearable numbers (Body Battery, readiness scores, fitness age, SpO2,
deep-sleep minutes) have no validation behind them at all.

### `garmin_connect` request budget

It authenticates by scraping Garmin Connect with real credentials; there is no
official API for personal use (Garmin's Health API is a B2B integration). Every
request counts:

- Login is the rate-limited endpoint. The session token store is persisted on a
  PVC so restarts do not force re-authentication.
- A restored session must have `display_name` hydrated before use — `client.load()`
  authenticates but leaves it `None`, and several endpoints interpolate it into
  their URL.
- Rate limits and account locks are recorded in Redis
  (`garmin_connect:rate_limit_cooldown`) with an escalating backoff, and the sync
  aborts the whole run rather than retrying per date.
