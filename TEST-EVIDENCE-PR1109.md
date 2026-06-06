# PR #1109 — SensorBio Provider Test Evidence

**Branch:** `sensr-provider-stub` (sontakey/open-wearables → the-momentum/open-wearables)  
**PR URL:** https://github.com/the-momentum/open-wearables/pull/1109  
**Date:** 2026-06-05  
**Tester:** Kanban worker (work profile)

---

## How to reproduce

```bash
# Clone the PR branch (or use existing worktree at /tmp/open-wearables-kanban)
git clone --branch sensr-provider-stub https://github.com/sontakey/open-wearables.git
cd open-wearables/backend

# Install deps (Python 3.13 required)
uv sync --group dev --group code-quality

# 1. Unit / provider tests (no DB, no secrets)
SECRET_KEY=test uv run pytest tests/providers/sensorbio tests/providers/test_provider_factory.py -q

# 2. E2E harness (offline mock mode, no secrets)
uv run python scripts/manual_test_sensorbio_app.py

# 3. Code quality
uv run ruff check app/services/providers/sensorbio/ app/constants/workout_types/sensorbio.py
uv run ruff format --check app/services/providers/sensorbio/ app/constants/workout_types/sensorbio.py
uv run ty check app/services/providers/sensorbio/

# 4. Live-API mode (requires real Sensor Bio credentials)
# Set SENSORBIO_CLIENT_ID, SENSORBIO_CLIENT_SECRET in backend/.env, then:
SENSORBIO_LIVE=1 uv run python scripts/manual_test_sensorbio_app.py
```

---

## Evidence

### Unit tests — 52/52 passed

```
collected 52 items

tests/providers/sensorbio/test_sensorbio_api_spec.py .............  [25%]
tests/providers/sensorbio/test_sensorbio_oauth.py ...               [30%]
tests/providers/sensorbio/test_sensorbio_strategy.py ........       [46%]
tests/providers/sensorbio/test_sensorbio_workout_types.py ...       [51%]
tests/providers/test_provider_factory.py .........................   [100%]

52 passed in 3.50s
```

### E2E harness — 131/131 checks passed

```
════════════════════════════════════════════════════════════
  SensorBio E2E Test Harness
════════════════════════════════════════════════════════════
  Repo:   /tmp/open-wearables-sensr
  Branch: sensr-provider-stub
  Mode:   MOCKED (offline)

  1 · OAuth URL Generation          — 11/11 PASS
  2 · Token-Exchange Stub           —  5/5  PASS
  3 · Provider Factory              —  9/9  PASS
  4 · Workout Type Mapping          — 19/19 PASS
  5 · Workout Sync /v1/activities   — 21/21 PASS
  6 · HTTP/2 Flag Propagation       —  2/2  PASS
  7 · Sleep Sync /v1/sleep          — 18/18 PASS
  8 · Recovery Sync /v1/scores      —  9/9  PASS
  9 · Step Details /v1/step/details — 12/12 PASS
 10 · API Response Shape Assertions — 25/25 PASS

  RESULTS:  131/131 checks passed

All checks passed. SensorBio integration is working correctly.
```

### Code quality — clean

```
ruff check:   All checks passed!
ruff format:  6 files already formatted
ty check:     All checks passed!
```

---

## Fixes applied during this run

One small fixup commit was applied on top of the PR branch
(`aade34f fix(sensorbio): ruff format + ty type fixes`):

| File | Issue | Fix |
|---|---|---|
| `workouts.py` | ruff format violation (line too long) | Applied `ruff format` |
| `workouts.py` | `_extract_dates` params typed `int\|float` but called with `Any\|None` | Widened to `int\|float\|None` |
| `data_247.py` | `save_sleep_data` return type `None` but all paths explicitly `return False/True` | Changed to `-> bool`, updated `load_and_save_sleep` to use return value for count |
| `strategy.py` | `__init__` missing return type annotation | Added `-> None` |

All 52 unit tests and 131 E2E checks pass after this fix.

---

## What is NOT tested (requires live credentials or full DB)

- OAuth callback with a real Sensor Bio code (needs live `SENSORBIO_CLIENT_ID` + user account)
- DB persistence (`save_sleep_data`, `save_recovery_data`, `save_workouts`) — needs PostgreSQL
- Full API integration tests (`tests/integrations/test_sensr_import.py`) — not yet written per original PR scope
- End-to-end browser OAuth flow (Playwright, requires running stack)

See `TEST-MATRIX-SENSR-PR.md` in this workspace for the full test plan (§4 staging, §5 E2E browser, §6 mobile).

---

## Blockers for merge

None from this run. The code quality and offline functional tests are clean.
Remaining gates before merge (per `TEST-MATRIX-SENSR-PR.md` §10):
- Staging smoke (S-03 /v1/user, S-07 /v1/biometrics) — requires live creds
- GitHub Actions CI all green on branch
- E2E provider connect flow screenshot (E-01 through E-03)
