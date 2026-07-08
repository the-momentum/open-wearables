# Synaptik Fork Delta & Upgrade Recipe

This fork of [the-momentum/open-wearables](https://github.com/the-momentum/open-wearables)
carries a small, deliberate set of Synaptik customizations on top of a pinned upstream
release. **This file lives ONLY on the `release/*-syn` branch** — never on `main`, because
`main` is a pristine upstream mirror that gets fast-forwarded (overwritten) on every sync.

## Branch model

```
the-momentum (upstream)  ──tag──►  main            (pristine mirror, fast-forward ONLY, 0 syn commits)
                                     │  merge per upgrade
                                     ▼
                           release/x.y-syn          (this branch = main + the delta below)
                                     │  tag  x.y-syn.N
                                     ▼
                     calibra-ow-deploy (OW_REF = tag)   ← production
```

- Production is built by `calibra-ow-deploy/.github/workflows/deploy-openwearables.yml`
  from `OW_REPO = Synpatik-GmbH/open-wearables` at the tag in `OW_REF` (currently `0.5.2-syn.7`).
- Deploys always reference an **immutable tag**, never a branch head.

## Current base

- **Now on: 0.6.2** (`a07818f`) — upgraded from 0.5.2 (`a2060c7`) on 2026-07-07.
- `release/0.6.2-syn` = 6 commits on the 0.6.2 mirror; tag `0.6.2-syn.1` pending deploy.

---

## 0.6.2 upgrade — actual outcome (2026-07-07)

Reconcile of the 0.5.2-syn delta onto upstream 0.6.2. **CI green: 1873 passed, 2 skipped.**

**Dropped as superseded by upstream:**
- **session-lifecycle hardening** (last_synced_at / whoop / data_247) — upstream now reads `last_synced_at` *before* the commit + added its own rollbacks and `pull_inserted`/`pull_updated` accounting (our fresh-session rewrite would have broken that accounting).
- **event_record snapshot-before-after_commit** — upstream #1208 fires the webhook directly, no snapshot dataclasses.
- **Polar TL/distance float** — upstream #1204 does the same widening.

**Reconciled / kept:**
- **config** — adopted upstream's `redis_ssl` field; **kept `ssl_cert_reqs=none`** for the Azure Redis Enterprise endpoint (`redis-ow-nc-dev-gwc`, Balanced_B0). It's the proven-working setting; `required` would *likely* also work (Enterprise uses a public DigiCert G2 cert on the FQDN) but isn't worth the cutover risk. Kept WHOOP `read:profile`. Updated the two upstream `test_redis_url` assertions to expect `none`. → **DEPLOY ACTION: rename env `REDIS_USE_TLS` → `REDIS_SSL`** (value stays `true`); the connection string is otherwise identical.
- **Edwards HR-zone payload** — reworked onto upstream's direct-fire model (**no snapshot dataclasses**). `heart_rate.py` + the `get_workout_hr_zone_minutes` SQL recovered verbatim; zones computed while the session is live and passed through `create_detail` → `_emit_event_record_webhook` → `on_workout_created` (bulk path computes before expunge). Emitted payload is identical to 0.5.2-syn → **.NET adapter parity preserved**.
- **respiratory_rate** + **Polar RHR bridge** — kept; declared the newly-emitted series types in upstream 0.6.2's coverage manifests (`whoop/coverage.py` → `respiratory_rate`, `polar/coverage.py` → `resting_heart_rate`) to satisfy the new `test_provider_coverage`.
- **webhook fast lane** — applied clean.

---

## The durable delta (what must survive every upgrade)

These are genuinely Synaptik-specific and will never be upstreamed. **The reconciliation
checklist for any upgrade is: confirm each of these still applies and still behaves.**

Commit hashes below are the **current `release/0.6.2-syn`** shas (update each upgrade).

| Feature | Commit | Files | Why it's ours | Notes |
|---|---|---|---|---|
| **Edwards HR-zone payload** on `workout.created` | `99508d8` | `event_record_service.py`, `heart_rate.py`, `data_point_series_repository.py`, `outgoing_webhooks/events.py` | **The .NET adapter depends on this** — its `WorkoutHrZoneHealService` replicates the EXACT Edwards algorithm. Dropping/changing it breaks parity. | ⚠️ HIGHEST-RISK. As of 0.6.2 the delivery is **direct-fire** (no snapshot dataclasses). Re-verify payload shape against the adapter after any upstream zone change. |
| **Webhook fast lane** | `9519029` | `outgoing_webhooks/events.py`, `scripts/start/worker.sh` | Latency: priority events → dedicated `webhook_sync` Celery queue (`CELERY_QUEUES`). Consumed by `aca-ow-worker-priority-dev`. | Keep the `worker.sh` CELERY_QUEUES override. |
| **Polar Recharge bridges** | `738186b` | `services/providers/polar/data_247.py`, `polar/coverage.py` | HRV→`rmssd`, RHR→`resting_heart_rate`. Not in upstream. | Must stay declared in `polar/coverage.py` (test_provider_coverage). |
| **respiratory_rate → data_point_series** (Thread 14f) | `1d2f46a` | `data_point_series_repository.py`, `whoop/coverage.py`, sleep save path | Sleep-side RR persistence. | Declared in `whoop/coverage.py`. Upstream `eddf5d9` #1235 is Garmin-side RR (complementary). |
| **WHOOP `read:profile` scope + Redis `ssl_cert_reqs=none`** | `565ae6a` | `config.py`, `tests/utils_tests/test_redis_url.py` | WHOOP app needs the scope; Azure Redis Enterprise proven with `none`. | Uses upstream's `redis_ssl` field → deploy env is **`REDIS_SSL`**. Two `test_redis_url` assertions carry the `none` delta. |

---

## Personal Record write API (net-new)

`PUT` / `GET /api/v1/users/{user_id}/personal-record` — adapter-driven write
API for `public.personal_record`. Upsert keyed on the 1:1 `user_id`
(`ApiKeyDep`, 201 create / 200 update). Body = `birth_date` + `gender`
(`sex` intentionally omitted — read by nothing in OW).

Purpose: let the .NET adapter set `birth_date` so OW computes HR-zone max HR as
`220 − age` (`estimate_max_hr`) at workout ingest instead of the
`DEFAULT_MAX_HR = 190` fallback.

Boundary: OW computes zones ONCE at ingest, so a populated `birth_date` only
affects workouts ingested afterward. Historical workouts keep their maxHr-190
zones and continue to be handled by the .NET adapter's
`WorkoutHrZoneHealService`.

Upstream OW has no write path for `personal_record` (only seed data writes it).

---

## Superseded by upstream — DROPPED at 0.6.2 (executed 2026-07-07)

Reimplemented independently upstream; not carried forward. See the outcome section above.

| Former commit | Superseded by | Outcome |
|---|---|---|
| session-lifecycle hardening (`d436010`/`620a71b`/`c38cf33`) | `ac351ab` #1147 + `f5b9696` #1215 sync refactor | **Dropped** — upstream reads `last_synced_at` pre-commit + new WriteCounts accounting. |
| `d09028c` snapshot ORM attrs before `after_commit` | `e8efeea` #1208 (direct-fire) | **Dropped** — mechanism gone; Edwards reworked onto direct-fire. |
| `9c82908`/`23ad5ea` Polar TL/distance → float | `a10227b` #1204 | **Dropped.** |
| Redis-TLS *field* half of `3e287c0` | `a764df2` #1134 | **Superseded** — took upstream's `redis_ssl` field, kept only `ssl_cert_reqs=none`. |

## Noise — squash/collapse before rebasing (generic, for future upgrades)

- Ruff/style-only and duplicated commits: fold into their feature parents before the rebase (see Appendix A).

---

## Upgrade recipe (run this for every upstream bump)

> One-time cleanup uses **rebase**; recurring upgrades use **merge**. See "Why" below.

### 0. Prep
```bash
git remote get-url upstream || git remote add upstream https://github.com/the-momentum/open-wearables.git
git fetch upstream --tags
git config rerere.enabled true    # remembers conflict resolutions across upgrades
```

### 1. Advance the mirror
```bash
git switch main
git merge --ff-only <new-upstream-tag>   # e.g. 0.6.2 ; must be fast-forward
git push origin main
```
> If `--ff-only` fails, `main` has drifted (someone committed to it) — it must stay pristine.
> Reset it: `git reset --hard <new-upstream-tag>` and force-push (nothing unique should be lost).

### 2. Integrate the delta
**First jump to 0.6.2 (one-time history cleanup → rebase):**
```bash
git switch -c release/0.6.2-syn origin/release/0.5.2-syn
git rebase -i upstream-0.5.2         # squash the "Noise" list first
git rebase --onto main upstream-0.5.2
#   Expect 3 conflicts (sync_vendor_data_task.py, event_record_service.py, config.py).
#   Apply the DROP/skip decisions from the tables above.
```
**Every upgrade after that (merge, so conflicts are resolved once):**
```bash
git switch release/<prev>-syn
git switch -c release/<new>-syn
git merge main                        # rerere replays known resolutions
#   Walk the "durable delta" table; re-check each item still applies + behaves.
```

### 3. Prove it
```bash
cd backend && <test runner>
#   Focus: test_polar_247, test_polar_workouts, test_heart_rate, test_outgoing_webhooks
```
Then **diff engine outputs vs a pre-upgrade snapshot** — especially workout HR-zone and
respiratory payloads — because the .NET adapter's parity is pinned to these.

### 4. Ship
```bash
git tag <new>-syn.1
git push origin release/<new>-syn --tags
# Bump OW_REF: <new>-syn.1 in calibra-ow-deploy/.github/workflows/deploy-openwearables.yml
```
`release/<prev>-syn` and its tag stay untouched → instant rollback by reverting `OW_REF`.

### Why rebase once, merge thereafter
Rebase replays the whole delta from scratch every time → you re-resolve the same conflicts
on every upgrade and must force-push a branch the deploy pipeline tracks. Merge resolves each
conflict once (recorded in the merge commit; merge-base advances) and never force-pushes.
Use rebase only for the initial 0.6.2 cleanup to get a tidy base.

---

## Long-term: shrink this file

The cheapest upgrade is a small delta. Everything in the "Superseded" table proves upstream
will independently fix generic issues. **Upstream the generic bits** (the SQLAlchemy
session/lazy-load hardening, respiratory-rate persistence) via PRs to the-momentum so they
leave the fork permanently. Aim to keep only the ~4 truly-Synaptik features in the durable table.

---

## Appendix A — 0.5.2-syn squash plan (one-time history cleanup)

Run this **before** `git rebase --onto main upstream-0.5.2` to collapse the raw
22-non-merge-commit history into **8 clean feature commits** (verified: runs conflict-free and
produces a byte-identical tree). It is in **original order — no reordering** — so it cannot
self-conflict; every `fixup`/`squash` folds into the feature `pick` directly above it.

`fixup` = discard the folded message (noise / duplicates); `squash` = combine messages
(meaningful sub-commits — reword the result).

```
pick   d436010 fix(worker): cache last_synced_at before workouts commit
squash 620a71b fix(whoop): rollback + re-raise on sleep save failure
squash c38cf33 fix(worker): fresh session for data_247
fixup  35cbdc0 (duplicate of c38cf33)
fixup  26faed1 style: E501 in sync_vendor_data_task
pick   d09028c fix(event_record_service): snapshot ORM attrs before after_commit
fixup  7a923b2 style: ruff format event_record_service
squash 8104bed fix: _emit_event_record_webhook accepts snapshots
squash bc1b5bb refactor: freeze snapshot dataclasses
pick   3e287c0 fix(config): Redis TLS support + WHOOP read:profile scope
pick   513b94d feat: respiratory_rate -> data_point_series (Thread 14f)
pick   feeabca feat: Edwards HR-zone minutes on workout.created (Thread 20B)
fixup  5c33af7 style: ruff format event_record_service
squash 29c0a35 fix: insert HR samples before workout details (zone query)
fixup  ff312ff (duplicate ordering fix)
pick   753ec9c feat(polar): Recharge HRV -> rmssd bridge
squash b2e93f9 feat(polar): Recharge RHR -> resting_heart_rate bridge
pick   9c82908 fix(polar): Training Load Pro + distance -> float
fixup  23ad5ea test(polar): fractional Training Load + distance
pick   01e6eae feat(webhooks): config-driven priority event set
squash 0905a69 feat(webhooks): route to webhook_sync fast lane + CELERY_QUEUES
fixup  94fd4f8 style: ruff format test_outgoing_webhooks
```

Resulting 8 commits and their reconcile role at the `--onto main` step:

| # | Feature commit | Reconcile role at 0.6.2 |
|---|---|---|
| 1 | SQLAlchemy session-lifecycle hardening (last_synced_at / whoop / data_247) | **Drop-candidate** — check vs #1147/#1215 |
| 2 | event_record snapshot-before-after_commit | **Drop** — superseded by #1208 |
| 3 | Redis TLS + WHOOP read:profile scope | **Split** — drop TLS (#1134), keep WHOOP scope |
| 4 | respiratory_rate → data_point_series | Keep (verify vs #1235) |
| 5 | Edwards HR-zone payload | **Keep — the .NET adapter depends on it** |
| 6 | Polar Recharge HRV + RHR bridges | Keep |
| 7 | Polar TL/distance float | **Drop** — superseded by #1204 |
| 8 | Webhook fast lane | Keep |

So the subsequent `--onto` reduces to: drop commits 2 & 7, split 1 & 3, keep the rest;
expect 3 conflicts (`sync_vendor_data_task.py`, `event_record_service.py`, `config.py`).

### Run it non-interactively (optional)

```bash
git config rerere.enabled true                 # do this first
# save the todo block above to /path/to/rebase-todo.txt (action + sha per line)
GIT_SEQUENCE_EDITOR="cp /path/to/rebase-todo.txt" GIT_EDITOR=true \
  git rebase -i upstream-0.5.2
```

Drop `GIT_EDITOR=true` if you want to reword each of the 8 combined messages as you go
(recommended — e.g. commit 1 should read "session-lifecycle hardening", not just "cache
last_synced_at").
