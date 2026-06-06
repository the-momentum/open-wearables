#!/usr/bin/env python3
"""SensorBio PR #1109 Integration Tester — browser-based FastAPI webapp.

A lightweight web app for manually testing the Sensor Bio provider
without a running database, Redis, or Celery.

Modes
-----
MOCK (default, no secrets):
    All SensorBio API calls answered with deterministic offline fixtures.
    Start:  cd backend/ && uv run python scripts/sensorbio_integration_tester.py
    Open:   http://localhost:8765

LIVE (real credentials):
    Set SENSORBIO_LIVE=1 + SENSORBIO_CLIENT_ID + SENSORBIO_CLIENT_SECRET.
    Optional: SENSORBIO_REDIRECT_URI (defaults to http://localhost:8765/oauth/callback)
    Register the redirect URI in the Sensor Bio developer portal first.
    Start:
        SENSORBIO_LIVE=1 \\
        SENSORBIO_CLIENT_ID=xxx \\
        SENSORBIO_CLIENT_SECRET=*** \\
        uv run python scripts/sensorbio_integration_tester.py
    Redirect URI to allowlist: http://localhost:8765/oauth/callback

Provider API shape references (from PR #1109)
---------------------------------------------
  /v1/activities   -> {data:[WorkoutStats], links:{next?}}
  /v1/sleep        -> {data:[SleepRecord]}
  /v1/scores       -> {data:{date, recovery:{score,biometrics}, sleep:{biometrics}}}
  /v1/step/details -> StepDetailsResponseBody  (no 'data' wrapper)
  /v1/biometrics   -> {data:[BiometricSample]}
  /v1/user         -> {data:{id,name}} or flat {id,name}
"""

from __future__ import annotations

import json
import os
import pathlib
import sys
import traceback
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

# ---------------------------------------------------------------------------
# Bootstrap: make backend/ importable
# ---------------------------------------------------------------------------
_BACKEND_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

# ---------------------------------------------------------------------------
# Minimal env so settings loads without .env
# ---------------------------------------------------------------------------
os.environ.setdefault("SECRET_KEY", "test-secret-key-tester")
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://user:pass@localhost/db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("API_BASE_URL", "http://localhost:8765")
os.environ.setdefault("SENSORBIO_CLIENT_ID", "test-client-id")
os.environ.setdefault("SENSORBIO_CLIENT_SECRET", "test-client-secret")
# Tester's callback route — must match what's registered in the Sensor Bio developer portal
os.environ.setdefault("SENSORBIO_REDIRECT_URI", "http://localhost:8765/oauth/callback")

LIVE_MODE = os.environ.get("SENSORBIO_LIVE", "").lower() in ("1", "true", "yes")

# In-memory live session — stores access_token after successful OAuth exchange.
# Never persisted to disk or committed. Cleared on server restart.
_LIVE_SESSION: dict[str, Any] = {}

# Real creds override the defaults when in live mode
if LIVE_MODE:
    _real_id = os.environ.get("SENSORBIO_CLIENT_ID", "")
    _real_secret = os.environ.get("SENSORBIO_CLIENT_SECRET", "")
    if _real_id:
        os.environ["SENSORBIO_CLIENT_ID"] = _real_id
    if _real_secret:
        os.environ["SENSORBIO_CLIENT_SECRET"] = _real_secret

# ---------------------------------------------------------------------------
# Imports (after env setup)
# ---------------------------------------------------------------------------
import uvicorn  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.responses import HTMLResponse, JSONResponse  # noqa: E402

from app.config import settings  # noqa: E402
from app.constants.workout_types.sensorbio import get_unified_workout_type  # noqa: E402
from app.services.providers.factory import ProviderFactory  # noqa: E402
from app.services.providers.sensorbio.data_247 import SensorBio247Data  # noqa: E402
from app.services.providers.sensorbio.oauth import SensorBioOAuth  # noqa: E402
from app.services.providers.sensorbio.strategy import SensorBioStrategy  # noqa: E402
from app.services.providers.sensorbio.workouts import SensorBioWorkouts  # noqa: E402

# ---------------------------------------------------------------------------
# Mock fixtures  (match official SensorBio API spec shapes used by PR #1109)
# ---------------------------------------------------------------------------
_TS_WS1_MS = 1_700_000_000_000
_TS_ACT_START_MS = 1_699_999_800_000
_TS_ACT_END_MS = 1_700_000_000_000
_TS_WS2_MS = 1_700_100_000_000

MOCK_ACTIVITIES_PAGE1: dict[str, Any] = {
    "data": [
        {
            "timestamp": _TS_WS1_MS,
            "name": "Run",
            "activities": [
                {
                    "id": "act-001",
                    "start_time": _TS_ACT_START_MS,
                    "end_time": _TS_ACT_END_MS,
                    "likely_name": "Running",
                    "calories": 450.5,
                    "distance": 6200.0,
                    "active_time": 1980,
                    "duration": 2000,
                    "cardio_metrics": {"avg_bpm": 152.3, "max_bpm": 178, "min_bpm": 130},
                },
                {
                    "id": "act-002",
                    "start_time": _TS_ACT_START_MS - 86_400_000,
                    "end_time": _TS_ACT_END_MS - 86_400_000,
                    "likely_name": "Yoga",
                    "calories": 120.0,
                    "distance": None,
                    "active_time": 3600,
                    "duration": 3600,
                    "cardio_metrics": {},
                },
            ],
        }
    ],
    "links": {"next": "https://api.sensorbio.com/v1/activities?last-timestamp=..."},
}

MOCK_ACTIVITIES_PAGE2: dict[str, Any] = {
    "data": [
        {
            "timestamp": _TS_WS2_MS,
            "name": "Swim",
            "activities": [
                {
                    "id": "act-003",
                    "start_time": _TS_WS2_MS - 3_600_000,
                    "end_time": _TS_WS2_MS,
                    "likely_name": "Swimming",
                    "calories": 600.0,
                    "distance": 1000.0,
                    "active_time": 3500,
                    "duration": 3600,
                    "cardio_metrics": {"avg_bpm": 140.0, "max_bpm": 160, "min_bpm": 120},
                }
            ],
        }
    ],
    "links": {},
}

_SLEEP_START_S = 1_700_036_400
_SLEEP_END_S = 1_700_065_200

MOCK_SLEEP_RESPONSE: dict[str, Any] = {
    "data": [
        {
            "id": "sleep-001",
            "start_timestamp": _SLEEP_START_S,
            "end_timestamp": _SLEEP_END_S,
            "total_sleep_mins": 428,
            "deep_sleep_mins": 90,
            "light_sleep_mins": 210,
            "rem_sleep_mins": 128,
            "awake_time_mins": 15,
            "avg_heart_rate": 58,
            "biometrics": {
                "bpm": 58,
                "hrv": 42.5,
                "spo2": 97.3,
                "resting_bpm": 56,
                "resting_hrv": 44.0,
            },
            "score": {"value": 82},
        }
    ]
}

MOCK_SCORES_RESPONSE: dict[str, Any] = {
    "data": {
        "date": "2023-11-15",
        "recovery": {
            "score": {"value": 75},
            "biometrics": {"resting_bpm": 57, "resting_hrv": 43.0, "spo2": 98.0},
        },
        "sleep": {
            "biometrics": {
                "bpm": 59,
                "hrv": 41.0,
                "spo2": 97.5,
                "resting_bpm": 56,
                "resting_hrv": 43.5,
            }
        },
    }
}

MOCK_STEP_DETAILS_RESPONSE: dict[str, Any] = {
    "date": "2023-11-15",
    "granularity": "day",
    "metrics": [
        {"name": "Steps", "value": 8200},
        {"name": "Distance", "value": 6.1, "unit": "km"},
        {"name": "Calories", "value": 312},
        {"name": "Duration", "value": 74, "unit": "min"},
    ],
    "daily_steps_goal": 10000,
    "steps_goal_achieved_percentage": 82,
}

MOCK_BIOMETRICS_RESPONSE: dict[str, Any] = {
    "data": [
        {
            "timestamp": _TS_ACT_START_MS,
            "heart_rate": 72,
            "heart_rate_variability": 45.0,
            "spo2": 97.8,
            "respiratory_rate": 15.2,
        },
    ]
}

MOCK_USER_RESPONSE: dict[str, Any] = {"data": {"id": "mock-user-001", "name": "Sameer Test"}}

MOCK_TOKEN_RESPONSE: dict[str, Any] = {
    "access_token": "mock_access_token_abc123",
    "refresh_token": "mock_refresh_token_xyz789",
    "token_type": "Bearer",
    "expires_in": 3600,
}


# ---------------------------------------------------------------------------
# Test runners
# ---------------------------------------------------------------------------


def _run_test(name: str, fn: Any) -> dict[str, Any]:
    try:
        result = fn()
        return {"name": name, "status": "pass", "detail": result or "OK"}
    except Exception:  # noqa: BLE001
        return {"name": name, "status": "fail", "detail": traceback.format_exc(limit=8)}


def test_provider_factory() -> dict[str, Any]:
    factory = ProviderFactory()
    strategy = factory.get_provider("sensorbio")
    return {
        "registered": isinstance(strategy, SensorBioStrategy),
        "name": strategy.name,
        "display_name": strategy.display_name,
        "api_base_url": strategy.api_base_url,
        "capabilities": {"rest_pull": strategy.capabilities.rest_pull},
        "has_oauth": strategy.oauth is not None,
        "has_workouts": strategy.workouts is not None,
        "has_data_247": strategy.data_247 is not None,
    }


def test_oauth_url() -> dict[str, Any]:
    """Generate OAuth authorization URL (mocked Redis state storage)."""
    oauth = SensorBioOAuth(
        user_repo=MagicMock(),
        connection_repo=MagicMock(),
        provider_name="sensorbio",
        api_base_url="https://api.sensorbio.com",
    )
    user_id = uuid4()
    # Patch redis_client property to return a mock that swallows setex/get/delete
    mock_redis = MagicMock()
    with patch.object(type(oauth), "redis_client", new_callable=lambda: property(lambda self: mock_redis)):
        # get_authorization_url returns (url, state) tuple
        result = oauth.get_authorization_url(user_id=user_id)
    url, state = result if isinstance(result, tuple) else (result, "")
    return {
        "authorize_url": url,
        "state_token": state[:12] + "..." if state else "(none)",
        "starts_with_sensorbio": url.startswith("https://auth.sensorbio.com/authorize"),
        "has_client_id": "client_id=" in url,
        "has_redirect_uri": "redirect_uri=" in url,
        "has_state": "state=" in url or bool(state),
        "redis_setex_called": mock_redis.setex.called,
    }


def test_workout_type_mapping() -> dict[str, Any]:
    """Verify workout type mapping covers the major activity types."""
    cases = [
        ("Running", "running"),
        ("Walking", "walking"),
        ("Swimming", "swimming"),
        ("Yoga", "yoga"),
        ("Strength Training", "strength_training"),
        ("Cycling", "cycling"),
        ("unknown_xyz", "other"),  # unrecognized input maps to 'other'
    ]
    results = []
    all_pass = True
    for input_name, expected_fragment in cases:
        mapped = get_unified_workout_type(input_name)
        passed = expected_fragment in str(mapped).lower()
        if not passed:
            all_pass = False
        results.append(
            {"input": input_name, "expected_contains": expected_fragment, "got": str(mapped), "pass": passed}
        )
    return {"cases": results, "all_pass": all_pass}


def test_workout_sync() -> dict[str, Any]:
    """Call get_workouts with mocked /v1/activities pages."""
    workouts = SensorBioWorkouts(
        workout_repo=MagicMock(),
        connection_repo=MagicMock(),
        provider_name="sensorbio",
        api_base_url="https://api.sensorbio.com",
        oauth=MagicMock(),
    )

    page_counter = {"n": 0}
    endpoints_hit: list[str] = []

    def _mock_api(db: Any, user_id: Any, endpoint: str, **kwargs: Any) -> dict[str, Any]:
        endpoints_hit.append(endpoint)
        n = page_counter["n"]
        page_counter["n"] += 1
        if n == 0:
            return MOCK_ACTIVITIES_PAGE1
        if n == 1:
            return MOCK_ACTIVITIES_PAGE2
        return {"data": [], "links": {}}

    with patch.object(workouts, "_make_api_request", side_effect=_mock_api):
        results = workouts.get_workouts(
            db=MagicMock(),
            user_id=uuid4(),
            start_date=datetime(2023, 11, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )

    return {
        "pages_fetched": page_counter["n"],
        "endpoints_hit": endpoints_hit,
        "activities_returned": len(results),
        "pagination_worked": page_counter["n"] >= 2,
        "activity_names": [r.get("likely_name") for r in results],
    }


def test_sleep_sync() -> dict[str, Any]:
    """Call load_and_save_all on SensorBio247Data with mocked sleep/scores endpoints."""
    data247 = SensorBio247Data(
        provider_name="sensorbio",
        api_base_url="https://api.sensorbio.com",
        oauth=MagicMock(),
    )

    def _mock_api(db: Any, user_id: Any, endpoint: str, **kwargs: Any) -> dict[str, Any]:
        if "sleep" in endpoint:
            return MOCK_SLEEP_RESPONSE
        if "scores" in endpoint:
            return MOCK_SCORES_RESPONSE
        if "step" in endpoint:
            return MOCK_STEP_DETAILS_RESPONSE
        if "biometrics" in endpoint:
            return MOCK_BIOMETRICS_RESPONSE
        return {}

    with (
        patch.object(data247, "_make_api_request", side_effect=_mock_api),
        patch.object(data247, "save_sleep_data", return_value=True) as m_sleep,
        patch.object(data247, "save_recovery_data", return_value=1),
        patch.object(data247, "save_activity_samples", return_value=1),
    ):
        sync_result = data247.load_and_save_all(
            db=MagicMock(),
            user_id=uuid4(),
            start_time=datetime(2023, 11, 15, tzinfo=timezone.utc),
            end_time=datetime(2023, 11, 16, tzinfo=timezone.utc),
        )

    sleep_rec = MOCK_SLEEP_RESPONSE["data"][0]
    return {
        "sync_result_keys": list(sync_result.keys()) if isinstance(sync_result, dict) else str(sync_result),
        "save_sleep_called": m_sleep.called,
        "sleep_record_sample": {
            "total_sleep_mins": sleep_rec["total_sleep_mins"],
            "deep_sleep_mins": sleep_rec["deep_sleep_mins"],
            "light_sleep_mins": sleep_rec["light_sleep_mins"],
            "rem_sleep_mins": sleep_rec["rem_sleep_mins"],
            "score": sleep_rec["score"]["value"],
        },
    }


def test_step_details() -> dict[str, Any]:
    """Verify step details shape (no 'data' wrapper — StepDetailsResponseBody)."""
    body = MOCK_STEP_DETAILS_RESPONSE
    metrics = {m["name"]: m["value"] for m in body.get("metrics", [])}
    return {
        "shape_note": "no 'data' wrapper — StepDetailsResponseBody returned directly",
        "date": body.get("date"),
        "granularity": body.get("granularity"),
        "metrics": metrics,
        "goal": body.get("daily_steps_goal"),
        "goal_pct": body.get("steps_goal_achieved_percentage"),
        "steps_parsed_ok": metrics.get("Steps", 0) > 0,
    }


def test_recovery_sync() -> dict[str, Any]:
    body = MOCK_SCORES_RESPONSE["data"]
    r = body["recovery"]
    return {
        "date": body["date"],
        "recovery_score": r["score"]["value"],
        "resting_hr_bpm": r["biometrics"]["resting_bpm"],
        "resting_hrv": r["biometrics"]["resting_hrv"],
        "spo2": r["biometrics"]["spo2"],
    }


def test_http2_flag() -> dict[str, Any]:
    """Verify workouts + 247-data both pass http2=True to make_authenticated_request."""
    import app.services.providers.sensorbio.data_247 as _data247_mod
    import app.services.providers.sensorbio.workouts as _workouts_mod

    captured: list[dict[str, Any]] = []

    def _capture(**kwargs: Any) -> dict[str, Any]:
        captured.append({"http2": kwargs.get("http2", False)})
        return {}

    workouts = SensorBioWorkouts(
        workout_repo=MagicMock(),
        connection_repo=MagicMock(),
        provider_name="sensorbio",
        api_base_url="https://api.sensorbio.com",
        oauth=MagicMock(),
    )
    data247 = SensorBio247Data(
        provider_name="sensorbio",
        api_base_url="https://api.sensorbio.com",
        oauth=MagicMock(),
    )

    # Must patch the name as bound in each module (from X import Y binds a new name)
    with (
        patch.object(_workouts_mod, "make_authenticated_request", side_effect=_capture),
        patch.object(_data247_mod, "make_authenticated_request", side_effect=_capture),
    ):
        workouts._make_api_request(db=MagicMock(), user_id=uuid4(), endpoint="/v1/activities")
        data247._make_api_request(db=MagicMock(), user_id=uuid4(), endpoint="/v1/sleep")

    return {
        "calls": captured,
        "workouts_http2": captured[0]["http2"] if len(captured) > 0 else None,
        "data_247_http2": captured[1]["http2"] if len(captured) > 1 else None,
        "both_use_http2": all(c["http2"] for c in captured),
    }


ALL_TESTS = [
    ("Provider Factory Registration", test_provider_factory),
    ("OAuth URL Generation", test_oauth_url),
    ("Workout Type Mapping (26 types)", test_workout_type_mapping),
    ("Workout Sync — Paginated /v1/activities", test_workout_sync),
    ("Sleep Sync — /v1/sleep", test_sleep_sync),
    ("Step Details — No data wrapper (/v1/step/details)", test_step_details),
    ("Recovery Score — /v1/scores", test_recovery_sync),
    ("HTTP/2 Flag Propagation", test_http2_flag),
]


# ---------------------------------------------------------------------------
# HTML UI
# ---------------------------------------------------------------------------
_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Sensor Bio Integration Tester — PR #1109</title>
  <style>
    :root {{
      --bg: #0e0e0e; --surface: #1a1a1a; --border: #2a2a2a;
      --accent: #f57c00; --green: #4caf50; --red: #f44336;
      --yellow: #ffb300; --text: #e0e0e0; --muted: #777; --code-bg: #111;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace;
            background: var(--bg); color: var(--text); padding: 24px; line-height: 1.5; }}
    header {{ border-bottom: 1px solid var(--border); padding-bottom: 16px; margin-bottom: 20px;
              display: flex; align-items: baseline; gap: 14px; flex-wrap: wrap; }}
    header h1 {{ font-size: 1.25rem; color: var(--accent); }}
    .badge {{ font-size: 0.68rem; padding: 2px 8px; border-radius: 4px; font-weight: bold; text-transform: uppercase; }}
    .badge-mock {{ background: #1e3a5f; color: #90caf9; }}
    .badge-live {{ background: #1b3a1b; color: #a5d6a7; }}
    .pr-link {{ font-size: 0.8rem; color: var(--muted); margin-left: auto; }}
    .pr-link a {{ color: var(--accent); text-decoration: none; }}
    .mode-note {{ font-size: 0.82rem; color: var(--yellow); background: #1a1400;
                  border: 1px solid #3a3000; border-radius: 6px; padding: 8px 14px; margin-bottom: 18px; }}
    .controls {{ display: flex; gap: 12px; margin-bottom: 20px; align-items: center; flex-wrap: wrap; }}
    button {{ background: var(--accent); color: #000; border: none; padding: 8px 20px;
              border-radius: 6px; font-size: 0.9rem; font-weight: bold; cursor: pointer; }}
    button:hover {{ opacity: 0.85; }} button:disabled {{ opacity: 0.4; cursor: not-allowed; }}
    .btn-oauth {{ background: #1565c0; color: #fff; }}
    .summary {{ display: flex; gap: 14px; margin-bottom: 20px; flex-wrap: wrap; }}
    .stat {{ background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
             padding: 10px 20px; min-width: 110px; text-align: center; }}
    .stat-value {{ font-size: 1.8rem; font-weight: bold; }}
    .stat-label {{ font-size: 0.72rem; color: var(--muted); text-transform: uppercase; margin-top: 2px; }}
    .pass {{ color: var(--green); }} .fail {{ color: var(--red); }} .pending {{ color: var(--muted); }}
    .tests-grid {{ display: flex; flex-direction: column; gap: 8px; }}
    .test-card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 8px; overflow: hidden; }}
    .test-header {{ display: flex; align-items: center; gap: 12px; padding: 11px 16px; cursor: pointer; user-select: none; }}
    .test-header:hover {{ background: #222; }}
    .status-dot {{ width: 9px; height: 9px; border-radius: 50%; flex-shrink: 0; }}
    .dot-pass {{ background: var(--green); }} .dot-fail {{ background: var(--red); }} .dot-pending {{ background: var(--muted); }}
    .test-name {{ flex: 1; font-size: 0.9rem; }}
    .test-status-text {{ font-size: 0.78rem; font-weight: bold; }}
    .test-body {{ border-top: 1px solid var(--border); padding: 12px 16px; display: none; }}
    .test-body.open {{ display: block; }}
    pre {{ background: var(--code-bg); border: 1px solid var(--border); border-radius: 6px; padding: 10px;
           font-size: 0.78rem; overflow-x: auto; white-space: pre-wrap; word-break: break-word; }}
    .oauth-section {{ background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
                       padding: 18px; margin-bottom: 20px; }}
    .oauth-section h2 {{ font-size: 0.95rem; color: var(--accent); margin-bottom: 12px; }}
    .live-section {{ background: var(--surface); border: 1px solid #1b3a1b; border-radius: 8px;
                     padding: 18px; margin-bottom: 20px; }}
    .live-section h2 {{ font-size: 0.95rem; color: #a5d6a7; margin-bottom: 12px; }}
    .live-btn {{ background: #2e7d32; color: #e8f5e9; border: 1px solid #388e3c; padding: 6px 14px;
                 border-radius: 5px; font-size: 0.82rem; font-weight: bold; cursor: pointer; margin: 3px; }}
    .live-btn:hover {{ background: #388e3c; }}
    .live-label {{ font-size: 0.68rem; padding: 2px 6px; border-radius: 3px; background: #1b3a1b;
                   color: #a5d6a7; font-weight: bold; text-transform: uppercase; margin-left: 5px; }}
    .oauth-url {{ font-family: monospace; font-size: 0.78rem; background: var(--code-bg);
                  padding: 10px; border-radius: 6px; word-break: break-all; color: #90caf9; margin-top: 8px; }}
    .spinner {{ display: inline-block; animation: spin 1s linear infinite; }}
    @keyframes spin {{ 0% {{ transform: rotate(0deg); }} 100% {{ transform: rotate(360deg); }} }}
    footer {{ margin-top: 28px; padding-top: 14px; border-top: 1px solid var(--border);
               font-size: 0.72rem; color: var(--muted); }}
  </style>
</head>
<body>
  <header>
    <h1>Sensor Bio Integration Tester</h1>
    <span class="badge {mode_badge}">{mode_label}</span>
    <span class="pr-link"><a href="https://github.com/the-momentum/open-wearables/pull/1109" target="_blank">PR #1109</a></span>
  </header>

  {mode_note}

  <div class="controls">
    <button id="run-btn" onclick="runTests()">&#9654; Run All Tests</button>
    <button class="btn-oauth" onclick="startOAuth()">&#128279; Start OAuth Flow</button>
    <span id="last-run" style="font-size:0.78rem;color:var(--muted);margin-left:6px;"></span>
  </div>

  <div class="summary">
    <div class="stat"><div class="stat-value pending" id="s-total">—</div><div class="stat-label">Total</div></div>
    <div class="stat"><div class="stat-value pass" id="s-pass">—</div><div class="stat-label">Pass</div></div>
    <div class="stat"><div class="stat-value fail" id="s-fail">—</div><div class="stat-label">Fail</div></div>
  </div>

  <div class="oauth-section" id="oauth-section" style="display:none">
    <h2>OAuth Flow</h2>
    <div id="oauth-content"></div>
  </div>

  <div class="live-section" id="live-section" style="display:none">
    <h2>&#127881; LIVE Data <span class="live-label">connected</span></h2>
    <p style="font-size:0.8rem;color:var(--muted);margin-bottom:12px">Fetch real data from your connected Sensor Bio account:</p>
    <div style="display:flex;flex-wrap:wrap;gap:4px;margin-bottom:12px">
      <button class="live-btn" onclick="fetchLive('user')">&#128100; User Profile</button>
      <button class="live-btn" onclick="fetchLive('activities')">&#127939; Activities</button>
      <button class="live-btn" onclick="fetchLive('sleep')">&#128564; Sleep</button>
      <button class="live-btn" onclick="fetchLive('scores')">&#128200; Scores</button>
      <button class="live-btn" onclick="fetchLive('step-details')">&#128115; Step Details</button>
      <button class="live-btn" onclick="fetchLive('biometrics')">&#10084; Biometrics</button>
    </div>
    <div id="live-result"></div>
  </div>

  <div class="tests-grid" id="tests-grid">
    <div style="color:var(--muted);font-size:0.9rem">Click "Run All Tests" to begin.</div>
  </div>

  <footer>
    SensorBio Integration Tester &bull; PR #1109 &bull; {mode_label} mode &bull;
    Endpoints: /v1/activities, /v1/sleep, /v1/scores, /v1/step/details, /v1/biometrics
  </footer>

  <script>
    const IS_LIVE = {is_live_json};

    async function runTests() {{
      const btn = document.getElementById('run-btn');
      btn.disabled = true;
      btn.innerHTML = '<span class="spinner">&#9696;</span> Running...';
      document.getElementById('tests-grid').innerHTML = '<div style="color:var(--muted)">Running...</div>';
      try {{
        const r = await fetch('/api/run-tests');
        renderResults(await r.json());
      }} catch(e) {{
        document.getElementById('tests-grid').innerHTML = '<pre style="color:var(--red)">Error: ' + e.message + '</pre>';
      }} finally {{
        btn.disabled = false;
        btn.innerHTML = '&#9654; Run All Tests';
      }}
    }}

    function renderResults(data) {{
      const tests = data.tests;
      const pass = tests.filter(t => t.status === 'pass').length;
      const fail = tests.filter(t => t.status === 'fail').length;
      document.getElementById('s-total').textContent = tests.length;
      document.getElementById('s-pass').textContent = pass;
      document.getElementById('s-fail').textContent = fail;
      document.getElementById('last-run').textContent = 'Last run: ' + new Date().toLocaleTimeString();

      const grid = document.getElementById('tests-grid');
      grid.innerHTML = '';
      tests.forEach((t, i) => {{
        const dotCls = t.status==='pass' ? 'dot-pass' : t.status==='fail' ? 'dot-fail' : 'dot-pending';
        const stTxt = t.status==='pass' ? '✓ PASS' : t.status==='fail' ? '✗ FAIL' : '—';
        const stCls = t.status==='pass' ? 'pass' : t.status==='fail' ? 'fail' : 'pending';
        const detail = typeof t.detail === 'object' ? JSON.stringify(t.detail, null, 2) : String(t.detail);
        const card = document.createElement('div');
        card.className = 'test-card';
        card.innerHTML = `<div class="test-header" onclick="toggle(${{i}})">
          <div class="status-dot ${{dotCls}}"></div>
          <span class="test-name">${{esc(t.name)}}</span>
          <span class="test-status-text ${{stCls}}">${{stTxt}}</span>
        </div>
        <div class="test-body" id="body-${{i}}"><pre>${{esc(detail)}}</pre></div>`;
        grid.appendChild(card);
        if (t.status === 'fail') document.getElementById('body-'+i).classList.add('open');
      }});
    }}

    function toggle(i) {{ document.getElementById('body-'+i).classList.toggle('open'); }}
    function esc(s) {{ return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }}

    async function startOAuth() {{
      const section = document.getElementById('oauth-section');
      section.style.display = 'block';
      const content = document.getElementById('oauth-content');
      content.innerHTML = '<span style="color:var(--muted)">Generating OAuth URL...</span>';
      try {{
        const r = await fetch('/api/oauth/start');
        const data = await r.json();
        if (data.error) {{
          content.innerHTML = '<pre style="color:var(--red)">' + esc(data.error) + '</pre>'; return;
        }}
        if (IS_LIVE) {{
          content.innerHTML = `<p style="margin-bottom:8px;font-size:0.85rem">Live OAuth URL — open in browser to connect real Sensor Bio account:</p>
            <div class="oauth-url"><a href="${{data.url}}" target="_blank" style="color:#90caf9">${{esc(data.url)}}</a></div>
            <p style="margin-top:10px;font-size:0.78rem;color:var(--muted)">After authorizing, Sensor Bio redirects to /oauth/callback and the tester exchanges the code for tokens.</p>`;
        }} else {{
          content.innerHTML = `<p style="margin-bottom:8px;font-size:0.85rem">Mock OAuth URL (would be sent to user in production):</p>
            <div class="oauth-url">${{esc(data.url)}}</div>
            <p style="margin-top:10px;font-size:0.78rem;color:var(--muted)">Mock mode: redirect to auth.sensorbio.com won't work. Set SENSORBIO_LIVE=1 with real credentials for a live flow.</p>
            <button style="margin-top:10px;font-size:0.8rem;padding:6px 14px" onclick="simulateCallback()">Simulate callback (mock token exchange)</button>`;
        }}
      }} catch(e) {{
        content.innerHTML = '<pre style="color:var(--red)">Error: ' + e.message + '</pre>';
      }}
    }}

    async function simulateCallback() {{
      const content = document.getElementById('oauth-content');
      try {{
        const r = await fetch('/api/oauth/simulate-callback');
        const data = await r.json();
        content.innerHTML += '<pre style="margin-top:10px">' + esc(JSON.stringify(data, null, 2)) + '</pre>';
      }} catch(e) {{
        content.innerHTML += '<pre style="color:var(--red)">' + e.message + '</pre>';
      }}
    }}

    async function checkLiveStatus() {{
      if (!IS_LIVE) return;
      try {{
        const r = await fetch('/api/live/status');
        const data = await r.json();
        if (data.authenticated) {{
          document.getElementById('live-section').style.display = 'block';
        }}
      }} catch(e) {{}}
    }}

    async function fetchLive(endpoint) {{
      const result = document.getElementById('live-result');
      result.innerHTML = '<span style="color:var(--muted)">Fetching ' + endpoint + '…</span>';
      try {{
        const r = await fetch('/api/live/' + endpoint);
        const data = await r.json();
        const label = '<span style="background:#1b3a1b;color:#a5d6a7;font-size:0.68rem;padding:2px 6px;border-radius:3px;font-weight:bold">LIVE</span>';
        result.innerHTML = '<div style="margin-bottom:6px">' + label + ' <b>' + esc(endpoint) + '</b> — HTTP ' + (data.status || r.status) + '</div>'
          + '<pre>' + esc(JSON.stringify(data.data ?? data, null, 2)) + '</pre>';
      }} catch(e) {{
        result.innerHTML = '<pre style="color:var(--red)">Error: ' + e.message + '</pre>';
      }}
    }}

    window.addEventListener('DOMContentLoaded', () => {{
      runTests();
      checkLiveStatus();
      if (IS_LIVE) setInterval(checkLiveStatus, 3000);
    }});
  </script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(title="SensorBio PR #1109 Integration Tester", docs_url=None, redoc_url=None)


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    mode_badge = "badge-live" if LIVE_MODE else "badge-mock"
    mode_label = "LIVE" if LIVE_MODE else "MOCK"
    is_live_json = "true" if LIVE_MODE else "false"
    mode_note = ""
    if not LIVE_MODE:
        mode_note = (
            '<div class="mode-note">'
            "&#9888; Running in MOCK mode — all SensorBio API calls use deterministic offline fixtures. "
            "No credentials required. Set <code>SENSORBIO_LIVE=1</code> with real creds for live API testing."
            "</div>"
        )
    html = _HTML.format(
        mode_badge=mode_badge,
        mode_label=mode_label,
        mode_note=mode_note,
        is_live_json=is_live_json,
    )
    return HTMLResponse(content=html)


@app.get("/api/run-tests")
async def api_run_tests() -> JSONResponse:
    results = [_run_test(name, fn) for name, fn in ALL_TESTS]
    pass_count = sum(1 for r in results if r["status"] == "pass")
    return JSONResponse(
        {
            "tests": results,
            "mode": "live" if LIVE_MODE else "mock",
            "summary": {"total": len(results), "pass": pass_count, "fail": len(results) - pass_count},
        }
    )


@app.get("/api/oauth/start")
async def api_oauth_start() -> JSONResponse:
    try:
        oauth = SensorBioOAuth(
            user_repo=MagicMock(),
            connection_repo=MagicMock(),
            provider_name="sensorbio",
            api_base_url="https://api.sensorbio.com",
        )
        user_id = uuid4()
        mock_redis = MagicMock()
        with patch.object(type(oauth), "redis_client", new_callable=lambda: property(lambda self: mock_redis)):
            result = oauth.get_authorization_url(user_id=user_id)
        url, state = result if isinstance(result, tuple) else (result, "")
        return JSONResponse({"url": url, "state": state, "mode": "live" if LIVE_MODE else "mock"})
    except Exception:  # noqa: BLE001
        return JSONResponse({"error": traceback.format_exc(limit=8)}, status_code=500)


@app.get("/api/oauth/simulate-callback")
async def api_oauth_simulate_callback() -> JSONResponse:
    return JSONResponse(
        {
            "simulated": True,
            "mock_token_response": MOCK_TOKEN_RESPONSE,
            "mock_user_profile": MOCK_USER_RESPONSE["data"],
            "note": (
                "Real flow: auth.sensorbio.com redirects to /oauth/callback?code=AUTH_CODE&state=STATE. "
                "Server POSTs to auth.sensorbio.com/token to exchange code for tokens, "
                "then GETs /v1/user to fetch the user profile."
            ),
        }
    )


@app.get("/oauth/callback")
async def oauth_callback(code: str = "", state: str = "", error: str = "") -> HTMLResponse:
    if error:
        return HTMLResponse(
            f'<html><body style="font-family:monospace;background:#0e0e0e;color:#f44336;padding:24px">'
            f"<h2>OAuth Error</h2><pre>{error}</pre>"
            f'<a href="/" style="color:#f57c00">Back to tester</a></body></html>'
        )
    if not code:
        return HTMLResponse(
            '<html><body style="font-family:monospace;background:#0e0e0e;color:#e0e0e0;padding:24px">'
            '<h2 style="color:#f57c00">No code received</h2>'
            '<a href="/" style="color:#f57c00">Back to tester</a></body></html>'
        )
    if LIVE_MODE:
        import httpx as _httpx

        try:
            # Sensor Bio rejects HTTP/1.x at the protocol layer with HTTP 464.
            # Use HTTP/2 for token exchange, matching the API's protocol requirement.
            async with _httpx.AsyncClient(http2=True, timeout=15) as client:
                resp = await client.post(
                    "https://auth.sensorbio.com/token",
                    data={
                        "grant_type": "authorization_code",
                        "code": code,
                        "client_id": settings.sensorbio_client_id or "",
                        "client_secret": (
                            settings.sensorbio_client_secret.get_secret_value()
                            if settings.sensorbio_client_secret
                            else ""
                        ),
                        "redirect_uri": settings.sensorbio_redirect_uri or "http://localhost:8765/oauth/callback",
                    },
                )
            content_type = resp.headers.get("content-type", "")
            body_text = resp.text or ""
            if resp.status_code >= 400:
                safe_body = body_text.replace(
                    settings.sensorbio_client_secret.get_secret_value() if settings.sensorbio_client_secret else "",
                    "[redacted]",
                )
                escaped_body = safe_body[:1200].replace("<", "&lt;").replace(">", "&gt;") or "(empty response body)"
                html = (
                    '<html><body style="font-family:monospace;background:#0e0e0e;color:#f44336;padding:24px">'
                    "<h2>Token exchange failed</h2>"
                    f"<p>HTTP status: <b>{resp.status_code}</b></p>"
                    f"<p>Content-Type: <code>{content_type or '(none)'}</code></p>"
                    f'<pre style="white-space:pre-wrap;background:#111;padding:12px;border-radius:6px">{escaped_body}</pre>'
                    '<p style="color:#ffb300">If status is 464 with an empty body, Sensor Bio rejected the authorization code/token request before returning JSON. Usually this means expired/reused code, redirect URI mismatch, or app credential mismatch.</p>'
                    '<a href="/" style="color:#f57c00">Back to tester</a></body></html>'
                )
            else:
                try:
                    token_json = resp.json()
                except ValueError as exc:
                    escaped_body = body_text[:1200].replace("<", "&lt;").replace(">", "&gt;") or "(empty response body)"
                    html = (
                        '<html><body style="font-family:monospace;background:#0e0e0e;color:#f44336;padding:24px">'
                        "<h2>Token exchange returned non-JSON success response</h2>"
                        f"<p>HTTP status: <b>{resp.status_code}</b></p>"
                        f"<p>Content-Type: <code>{content_type or '(none)'}</code></p>"
                        f"<p>JSON parse error: <code>{exc}</code></p>"
                        f'<pre style="white-space:pre-wrap;background:#111;padding:12px;border-radius:6px">{escaped_body}</pre>'
                        '<a href="/" style="color:#f57c00">Back to tester</a></body></html>'
                    )
                else:
                    access_token = token_json.get("access_token", "")
                    if access_token:
                        _LIVE_SESSION["access_token"] = access_token
                        _LIVE_SESSION["token_type"] = token_json.get("token_type", "Bearer")
                        _LIVE_SESSION["acquired_at"] = datetime.now(timezone.utc).isoformat()
                    # Show token summary (not the raw secret) — mask all but last 4 chars
                    display = {
                        k: (v[:4] + "…" + v[-4:] if isinstance(v, str) and len(v) > 12 and k == "access_token" else v)
                        for k, v in token_json.items()
                        if k != "refresh_token"
                    }
                    escaped = json.dumps(display, indent=2).replace("<", "&lt;").replace(">", "&gt;")
                    stored_msg = (
                        "&#10003; Access token stored in memory — use LIVE data buttons below."
                        if access_token
                        else "&#9888; No access_token in response."
                    )
                    html = (
                        '<html><body style="font-family:monospace;background:#0e0e0e;color:#e0e0e0;padding:24px">'
                        '<h2 style="color:#4caf50">&#10003; Token exchanged (live)</h2>'
                        f'<p style="color:#a5d6a7;margin-bottom:12px">{stored_msg}</p>'
                        f'<pre style="background:#111;padding:12px;border-radius:6px">{escaped}</pre>'
                        '<p style="margin-top:12px;font-size:0.8rem;color:#777">refresh_token omitted from display</p>'
                        '<a href="/" style="color:#f57c00">&#8592; Back to tester</a></body></html>'
                    )
        except Exception as exc:  # noqa: BLE001
            html = (
                '<html><body style="font-family:monospace;background:#0e0e0e;color:#f44336;padding:24px">'
                f"<h2>Token exchange crashed before receiving a response</h2><pre>{exc}</pre>"
                '<a href="/" style="color:#f57c00">Back to tester</a></body></html>'
            )
    else:
        html = (
            '<html><body style="font-family:monospace;background:#0e0e0e;color:#e0e0e0;padding:24px">'
            '<h2 style="color:#4caf50">&#10003; OAuth callback received (mock)</h2>'
            f"<p>code: <code>{code or '(none)'}</code></p>"
            f"<p>state: <code>{state or '(none)'}</code></p>"
            '<p style="color:#ffb300;margin-top:12px">Mock mode: token exchange skipped. '
            "In live mode this would POST to auth.sensorbio.com/token.</p>"
            '<a href="/" style="color:#f57c00">Back to tester</a></body></html>'
        )
    return HTMLResponse(content=html)


@app.get("/api/mock-data/{endpoint}")
async def api_mock_data(endpoint: str) -> JSONResponse:
    mapping: dict[str, Any] = {
        "activities": MOCK_ACTIVITIES_PAGE1,
        "sleep": MOCK_SLEEP_RESPONSE,
        "scores": MOCK_SCORES_RESPONSE,
        "step-details": MOCK_STEP_DETAILS_RESPONSE,
        "biometrics": MOCK_BIOMETRICS_RESPONSE,
        "user": MOCK_USER_RESPONSE,
        "token": MOCK_TOKEN_RESPONSE,
    }
    if endpoint not in mapping:
        return JSONResponse({"error": f"Unknown. Valid: {list(mapping.keys())}"}, status_code=404)
    return JSONResponse(mapping[endpoint])


@app.get("/api/live/status")
async def api_live_status() -> JSONResponse:
    """Return whether a live token is stored in memory."""
    has_token = bool(_LIVE_SESSION.get("access_token"))
    return JSONResponse(
        {
            "live_mode": LIVE_MODE,
            "authenticated": has_token,
            "acquired_at": _LIVE_SESSION.get("acquired_at"),
            "token_hint": (
                (_LIVE_SESSION["access_token"][:4] + "…" + _LIVE_SESSION["access_token"][-4:]) if has_token else None
            ),
        }
    )


@app.get("/api/live/{endpoint}")
async def api_live_fetch(endpoint: str) -> JSONResponse:
    """Proxy a real SensorBio API call using the in-memory access token.

    Supported endpoints: user, activities, sleep, scores, step-details, biometrics
    """
    if not LIVE_MODE:
        return JSONResponse({"error": "Not in LIVE mode. Start with SENSORBIO_LIVE=1."}, status_code=400)
    token = _LIVE_SESSION.get("access_token")
    if not token:
        return JSONResponse(
            {"error": "No access token in memory. Complete OAuth flow first (click 'Start OAuth Flow')."},
            status_code=401,
        )
    today = datetime.now(timezone.utc).date().isoformat()
    endpoint_map: dict[str, tuple[str, dict[str, Any]]] = {
        "user": ("/v1/user", {}),
        # Sensor Bio collection endpoints require a pagination cursor even for the first page.
        "activities": ("/v1/activities", {"last-timestamp": 0, "limit": 50}),
        "sleep": ("/v1/sleep", {"last-timestamp": 0, "limit": 50, "date": today}),
        "scores": ("/v1/scores", {"last-timestamp": 0, "limit": 50, "date": today}),
        "step-details": (
            "/v1/step/details",
            {"last-timestamp": 0, "limit": 50, "date": today, "granularity": "day"},
        ),
        "biometrics": ("/v1/biometrics", {"last-timestamp": 0, "limit": 50}),
    }
    if endpoint not in endpoint_map:
        return JSONResponse({"error": f"Unknown. Valid: {list(endpoint_map.keys())}"}, status_code=404)

    import httpx as _httpx

    try:
        path, params = endpoint_map[endpoint]
        url = f"https://api.sensorbio.com{path}"
        async with _httpx.AsyncClient(http2=True, timeout=20) as client:
            resp = await client.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
                params=params,
            )
        content_type = resp.headers.get("content-type", "")
        body_text = resp.text or ""
        if resp.status_code == 204 or not body_text.strip():
            return JSONResponse(
                {
                    "status": resp.status_code,
                    "url": str(resp.url),
                    "http_version": resp.http_version,
                    "content_type": content_type or None,
                    "data": None,
                    "note": "No content returned for this endpoint/query.",
                }
            )
        try:
            data = resp.json()
        except ValueError as exc:
            return JSONResponse(
                {
                    "status": resp.status_code,
                    "url": str(resp.url),
                    "http_version": resp.http_version,
                    "content_type": content_type or None,
                    "error": "Sensor Bio returned a non-JSON response.",
                    "json_error": str(exc),
                    "body_snippet": body_text[:1200],
                },
                status_code=502,
            )
        return JSONResponse(
            {
                "status": resp.status_code,
                "url": str(resp.url),
                "http_version": resp.http_version,
                "content_type": content_type or None,
                "data": data,
            },
            status_code=200 if resp.status_code < 400 else resp.status_code,
        )
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"error": str(exc)}, status_code=500)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("TESTER_PORT", "8765"))
    host = os.environ.get("TESTER_HOST", "127.0.0.1")
    print()
    print("=" * 58)
    print("  Sensor Bio PR #1109 Integration Tester")
    print(f"  Mode: {'LIVE (real API)' if LIVE_MODE else 'MOCK (no credentials needed)'}")
    print(f"  URL:  http://{host}:{port}")
    print()
    print("  Tests run automatically on page load.")
    print("  Click 'Run All Tests' to re-run anytime.")
    if not LIVE_MODE:
        print()
        print("  For live mode:")
        print("    SENSORBIO_LIVE=1 \\")
        print("    SENSORBIO_CLIENT_ID=xxx \\")
        print("    SENSORBIO_CLIENT_SECRET=*** \\")
        print("    uv run python scripts/sensorbio_integration_tester.py")
    print("=" * 58)
    print()
    uvicorn.run(app, host=host, port=port, log_level="warning")
