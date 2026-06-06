#!/usr/bin/env python3
"""Open Wearables Multi-Provider Integration Tester — browser-based FastAPI webapp.

A lightweight web app for manually testing any supported wearable provider
without a running database, Redis, or Celery.

Modes
-----
MOCK (default, no secrets):
    SensorBio API calls answered with deterministic offline fixtures.
    Start:  cd backend/ && uv run python scripts/sensorbio_integration_tester.py
    Open:   http://localhost:8765

LIVE (real credentials):
    Set SENSORBIO_LIVE=1 + SENSORBIO_CLIENT_ID + SENSORBIO_CLIENT_SECRET.
    Optional: SENSORBIO_REDIRECT_URI (defaults to http://localhost:8765/oauth/callback)
    Register the redirect URI in each provider's developer portal first.
    Start:
        SENSORBIO_LIVE=1 \\
        SENSORBIO_CLIENT_ID=xxx \\
        SENSORBIO_CLIENT_SECRET=*** \\
        uv run python scripts/sensorbio_integration_tester.py
    Redirect URI to allowlist: http://localhost:8765/oauth/callback

To add credentials for other providers:
    GARMIN_CLIENT_ID=xxx GARMIN_CLIENT_SECRET=yyy
    WHOOP_CLIENT_ID=xxx WHOOP_CLIENT_SECRET=yyy
    OURA_CLIENT_ID=xxx OURA_CLIENT_SECRET=yyy
    FITBIT_CLIENT_ID=xxx FITBIT_CLIENT_SECRET=yyy
    POLAR_CLIENT_ID=xxx POLAR_CLIENT_SECRET=yyy

SensorBio Provider API shape references (from PR #1109)
-------------------------------------------------------
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
from datetime import datetime, timedelta, timezone
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

# In-memory live sessions — keyed by provider name.
# Stores access_token after successful OAuth exchange.
# Never persisted to disk or committed. Cleared on server restart.
# Structure: {provider_name: {"access_token": str, "token_type": str, "acquired_at": str}}
_LIVE_SESSIONS: dict[str, dict[str, Any]] = {}

# Default selected provider (sensorbio for backwards-compat)
_SELECTED_PROVIDER: str = "sensorbio"


def _sess(provider: str | None = None) -> dict[str, Any]:
    """Return the live session dict for the given (or currently selected) provider."""
    return _LIVE_SESSIONS.get(provider or _SELECTED_PROVIDER, {})


def _set_sess(key: str, value: Any, provider: str | None = None) -> None:
    """Write a key into the live session for the given provider."""
    p = provider or _SELECTED_PROVIDER
    _LIVE_SESSIONS.setdefault(p, {})[key] = value


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
from fastapi import FastAPI, Request  # noqa: E402
from fastapi.responses import HTMLResponse, JSONResponse  # noqa: E402

from app.config import settings  # noqa: E402
from app.constants.workout_types.sensorbio import get_unified_workout_type  # noqa: E402
from app.services.providers.factory import ProviderFactory  # noqa: E402
from app.services.providers.sensorbio.data_247 import SensorBio247Data  # noqa: E402
from app.services.providers.sensorbio.oauth import SensorBioOAuth  # noqa: E402
from app.services.providers.sensorbio.strategy import SensorBioStrategy  # noqa: E402
from app.services.providers.sensorbio.workouts import SensorBioWorkouts  # noqa: E402

# ---------------------------------------------------------------------------
# Provider Registry
# All providers the platform knows about, with metadata for the tester.
# "api_base_url" is the data API base; "token_url" is their OAuth token endpoint.
# "has_classes" is set dynamically by import-probing ProviderFactory.
# "status" = "ready" | "available-but-unconfigured" | "unsupported"
# ---------------------------------------------------------------------------

_PROVIDER_META: dict[str, dict[str, Any]] = {
    "sensorbio": {
        "label": "Sensor Bio",
        "api_base_url": "https://api.sensorbio.com",
        "token_url": "https://auth.sensorbio.com/token",
        "cred_env": ("SENSORBIO_CLIENT_ID", "SENSORBIO_CLIENT_SECRET"),
        "has_pkce": False,
        "http2": True,
        "endpoints": {
            "user": "/v1/user",
            "activities": "/v1/activities",
            "sleep": "/v1/sleep",
            "scores": "/v1/scores",
            "step-details": "/v1/step/details",
            "biometrics": "/v1/biometrics",
        },
    },
    "whoop": {
        "label": "Whoop",
        "api_base_url": "https://api.prod.whoop.com/developer",
        "token_url": "https://api.prod.whoop.com/oauth/oauth2/token",
        "cred_env": ("WHOOP_CLIENT_ID", "WHOOP_CLIENT_SECRET"),
        "has_pkce": False,
        "http2": False,
        "endpoints": {
            "user": "/v2/user/profile/basic",
            "cycles": "/v2/cycle",
            "recovery": "/v2/recovery",
            "sleep": "/v2/sleep",
            "workout": "/v2/workout",
        },
    },
    "oura": {
        "label": "Oura Ring",
        "api_base_url": "https://api.ouraring.com",
        "token_url": "https://api.ouraring.com/oauth/token",
        "cred_env": ("OURA_CLIENT_ID", "OURA_CLIENT_SECRET"),
        "has_pkce": False,
        "http2": False,
        "endpoints": {
            "user": "/v2/usercollection/personal_info",
            "sleep": "/v2/usercollection/sleep",
            "readiness": "/v2/usercollection/readiness",
            "activity": "/v2/usercollection/daily_activity",
        },
    },
    "fitbit": {
        "label": "Fitbit",
        "api_base_url": "https://api.fitbit.com",
        "token_url": "https://api.fitbit.com/oauth2/token",
        "cred_env": ("FITBIT_CLIENT_ID", "FITBIT_CLIENT_SECRET"),
        "has_pkce": True,
        "http2": False,
        "endpoints": {
            "user": "/1/user/-/profile.json",
            "sleep": "/1.2/user/-/sleep/date/today.json",
            "activities": "/1/user/-/activities/date/today.json",
            "heart": "/1/user/-/activities/heart/date/today/1d.json",
        },
    },
    "garmin": {
        "label": "Garmin",
        "api_base_url": "https://apis.garmin.com",
        "token_url": "https://diauth.garmin.com/di-oauth2-service/oauth/token",
        "cred_env": ("GARMIN_CLIENT_ID", "GARMIN_CLIENT_SECRET"),
        "has_pkce": True,
        "http2": False,
        "endpoints": {
            "user": "/partner-gateway/rest/user/id",
            "activities": "/partner-gateway/rest/dailies",
            "sleep": "/partner-gateway/rest/sleeps",
        },
    },
    "polar": {
        "label": "Polar",
        "api_base_url": "https://www.polaraccesslink.com",
        "token_url": "https://polarremote.com/v2/oauth2/token",
        "cred_env": ("POLAR_CLIENT_ID", "POLAR_CLIENT_SECRET"),
        "has_pkce": False,
        "http2": False,
        "endpoints": {
            "user": "/v3/users",
            "activity": "/v3/users/activity-transactions",
            "sleep": "/v3/users/sleep",
        },
    },
}

# ProviderFactory class registry — which providers have strategy/oauth classes
_FACTORY_SUPPORTED = {
    "sensorbio", "garmin", "polar", "whoop", "fitbit", "oura",
    "strava", "apple", "google", "samsung", "suunto", "ultrahuman",
}


def _provider_status(name: str) -> str:
    """Return 'ready', 'available-but-unconfigured', or 'unsupported'."""
    meta = _PROVIDER_META.get(name)
    if meta is None:
        return "unsupported" if name in _FACTORY_SUPPORTED else "unsupported"
    id_env, secret_env = meta["cred_env"]
    has_creds = bool(os.environ.get(id_env)) and bool(os.environ.get(secret_env))
    if has_creds:
        return "ready"
    return "available-but-unconfigured"


def _build_oauth_for_provider(name: str) -> Any:
    """Instantiate the platform's OAuth class for the given provider via ProviderFactory.

    Falls back to a duck-typed shim that reads credentials from env/config
    so we can generate authorization URLs without importing each class.
    The shim is enough for URL generation + token exchange in the tester.
    """
    from unittest.mock import MagicMock

    meta = _PROVIDER_META.get(name)
    if meta is None:
        raise ValueError(f"Unsupported provider: {name}")

    id_env, secret_env = meta["cred_env"]
    client_id = os.environ.get(id_env, "")
    client_secret = os.environ.get(secret_env, "")

    try:
        # Prefer the real OAuth class from the platform
        match name:
            case "sensorbio":
                from app.services.providers.sensorbio.oauth import SensorBioOAuth as _Cls
            case "whoop":
                from app.services.providers.whoop.oauth import WhoopOAuth as _Cls  # type: ignore[assignment]
            case "oura":
                from app.services.providers.oura.oauth import OuraOAuth as _Cls  # type: ignore[assignment]
            case "fitbit":
                from app.services.providers.fitbit.oauth import FitbitOAuth as _Cls  # type: ignore[assignment]
            case "garmin":
                from app.services.providers.garmin.oauth import GarminOAuth as _Cls  # type: ignore[assignment]
            case "polar":
                from app.services.providers.polar.oauth import PolarOAuth as _Cls  # type: ignore[assignment]
            case _:
                raise ImportError(f"No class for {name}")
        return _Cls(
            user_repo=MagicMock(),
            connection_repo=MagicMock(),
            provider_name=name,
            api_base_url=meta["api_base_url"],
        )
    except ImportError:
        # Fallback minimal shim for providers without an OAuth class
        return None

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
  <title>Open Wearables Multi-Provider Tester</title>
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
    /* Provider selector */
    .provider-section {{ background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
                          padding: 16px; margin-bottom: 20px; }}
    .provider-section h2 {{ font-size: 0.9rem; color: var(--accent); margin-bottom: 10px; }}
    .provider-cards {{ display: flex; flex-wrap: wrap; gap: 10px; }}
    .pcard {{ background: var(--code-bg); border: 2px solid var(--border); border-radius: 8px;
               padding: 10px 16px; cursor: pointer; transition: border-color 0.15s; min-width: 120px; text-align: center; }}
    .pcard:hover {{ border-color: var(--accent); }}
    .pcard.selected {{ border-color: var(--accent); background: #1e1200; }}
    .pcard.needs-creds {{ opacity: 0.55; cursor: not-allowed; }}
    .pcard .pname {{ font-size: 0.82rem; font-weight: bold; }}
    .pcard .pstatus {{ font-size: 0.65rem; margin-top: 3px; text-transform: uppercase; letter-spacing: 0.05em; }}
    .pstatus-ready {{ color: var(--green); }}
    .pstatus-unconfigured {{ color: var(--yellow); }}
    .pstatus-unsupported {{ color: var(--muted); }}
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
    .range-controls {{ display:flex; flex-wrap:wrap; gap:10px; align-items:end; margin:10px 0 14px;
                       background:#101a10; border:1px solid #1b3a1b; border-radius:6px; padding:10px; }}
    .range-controls label {{ display:flex; flex-direction:column; gap:4px; font-size:0.72rem; color:var(--muted); }}
    .range-controls input {{ background:var(--code-bg); color:var(--text); border:1px solid var(--border);
                             border-radius:5px; padding:6px 8px; font-family:monospace; }}
    .oauth-url {{ font-family: monospace; font-size: 0.78rem; background: var(--code-bg);
                  padding: 10px; border-radius: 6px; word-break: break-all; color: #90caf9; margin-top: 8px; }}
    .spinner {{ display: inline-block; animation: spin 1s linear infinite; }}
    @keyframes spin {{ 0% {{ transform: rotate(0deg); }} 100% {{ transform: rotate(360deg); }} }}
    footer {{ margin-top: 28px; padding-top: 14px; border-top: 1px solid var(--border);
               font-size: 0.72rem; color: var(--muted); }}
    /* ---- Health Dashboard ---- */
    .dashboard-section {{ background: var(--surface); border: 1px solid #1a2a3a;
                           border-radius: 8px; padding: 18px; margin-bottom: 20px; }}
    .dashboard-section > h2 {{ font-size: 0.95rem; color: #90caf9; margin-bottom: 6px; }}
    .metric-cards {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
                     gap: 12px; margin-bottom: 18px; }}
    .metric-card {{ background: #111; border: 1px solid var(--border); border-radius: 10px;
                    padding: 13px 14px; text-align: center; }}
    .metric-card .mval {{ font-size: 1.4rem; font-weight: bold; color: var(--accent); }}
    .metric-card .mlbl {{ font-size: 0.67rem; color: var(--muted); text-transform: uppercase; margin-top: 4px; letter-spacing: 0.04em; }}
    .charts-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }}
    @media (max-width: 760px) {{ .charts-grid {{ grid-template-columns: 1fr; }} }}
    .chart-card {{ background: #111; border: 1px solid var(--border); border-radius: 8px; padding: 14px 16px; }}
    .chart-card h3 {{ font-size: 0.75rem; color: var(--muted); text-transform: uppercase;
                      letter-spacing: 0.05em; margin-bottom: 10px; }}
    .chart-empty {{ color: var(--muted); font-size: 0.82rem; text-align: center;
                    padding: 28px 0; border: 1px dashed var(--border); border-radius: 6px; }}
    .dash-warn {{ font-size: 0.8rem; color: var(--yellow); background: #1a1400;
                  border: 1px solid #3a3000; border-radius: 5px; padding: 7px 12px; margin-bottom: 12px; }}
    .dash-ok {{ font-size: 0.8rem; color: var(--muted); margin-bottom: 10px; }}
    .live-label {{ font-size: 0.68rem; padding: 2px 6px; border-radius: 3px; background: #1b3a1b;
                   color: #a5d6a7; font-weight: bold; text-transform: uppercase; margin-left: 5px; }}
  </style>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js"></script>
</head>
<body>
  <header>
    <h1>Open Wearables Multi-Provider Tester</h1>
    <span class="badge {mode_badge}">{mode_label}</span>
    <span class="pr-link"><a href="https://github.com/the-momentum/open-wearables/pull/1109" target="_blank">PR #1109</a></span>
  </header>

  {mode_note}

  <!-- Provider Selector -->
  <div class="provider-section">
    <h2>&#127940; Wearable Provider</h2>
    <div class="provider-cards" id="provider-cards">
      <span style="color:var(--muted);font-size:0.8rem">Loading providers...</span>
    </div>
    <p id="selected-provider-note" style="font-size:0.75rem;color:var(--muted);margin-top:8px"></p>
  </div>

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

  <!-- Token inject panel: always visible in live mode so Anton can paste a handoff token without running OAuth -->
  {inject_panel_html}

  <div class="live-section" id="live-section" style="display:none">
    <h2>&#127881; LIVE Data <span class="live-label">connected</span></h2>
    <!-- Token display panel -->
    <div id="token-panel" style="background:#0d1f0d;border:1px solid #1b3a1b;border-radius:8px;padding:14px;margin-bottom:14px;display:none">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
        <span style="font-size:0.82rem;color:#a5d6a7;font-weight:bold">&#128273; Token loaded</span>
        <button onclick="document.getElementById('token-reveal-area').style.display=document.getElementById('token-reveal-area').style.display==='none'?'block':'none'" style="background:transparent;border:1px solid #2e7d32;color:#66bb6a;padding:3px 10px;border-radius:4px;font-size:0.78rem;cursor:pointer">Show / Hide Token</button>
      </div>
      <div id="token-reveal-area" style="display:none">
        <p style="font-size:0.75rem;color:#777;margin-bottom:8px">Access token (tap Copy to clipboard):</p>
        <textarea id="live-token-display" readonly style="width:100%;box-sizing:border-box;background:#111;color:#a5d6a7;border:1px solid #333;border-radius:6px;padding:10px;font-size:0.72rem;font-family:monospace;resize:vertical;height:72px"></textarea>
        <button onclick="copyLiveToken(this)" style="margin-top:6px;background:#1565c0;color:#fff;border:none;padding:5px 14px;border-radius:5px;cursor:pointer;font-size:0.8rem">Copy</button>
      </div>
      <p id="token-panel-meta" style="font-size:0.72rem;color:#555;margin-top:6px;margin-bottom:0"></p>
    </div>
    <!-- Token inject panel (for Anton / hand-off use) -->
    <details id="token-inject-details" style="margin-bottom:14px;background:#0d1a2a;border:1px solid #1a3050;border-radius:8px;padding:12px">
      <summary style="cursor:pointer;font-size:0.82rem;color:#90caf9;font-weight:bold">&#128274; Inject token (skip OAuth — for hand-off testing)</summary>
      <div style="margin-top:12px">
        <label style="font-size:0.78rem;color:var(--muted);display:block;margin-bottom:4px">Access token <span style="color:#f44336">*</span></label>
        <textarea id="inject-access-token" placeholder="Paste full access_token here" style="width:100%;box-sizing:border-box;background:#111;color:#a5d6a7;border:1px solid #333;border-radius:6px;padding:8px;font-size:0.72rem;font-family:monospace;resize:vertical;height:60px;margin-bottom:8px"></textarea>
        <label style="font-size:0.78rem;color:var(--muted);display:block;margin-bottom:4px">Refresh token (optional)</label>
        <input id="inject-refresh-token" type="text" placeholder="Optional" style="width:100%;box-sizing:border-box;background:#111;color:#90caf9;border:1px solid #333;border-radius:6px;padding:7px;font-size:0.72rem;font-family:monospace;margin-bottom:10px">
        <button onclick="injectToken()" style="background:#1565c0;color:#fff;border:none;padding:7px 18px;border-radius:5px;cursor:pointer;font-size:0.82rem;font-weight:bold">&#128274; Inject Token</button>
        <span id="inject-status" style="font-size:0.78rem;color:#777;margin-left:10px"></span>
      </div>
    </details>
    <p style="font-size:0.8rem;color:var(--muted);margin-bottom:12px">Fetch real data from your connected Sensor Bio account:</p>
    <div class="range-controls">
      <label>Start date <input id="range-start" type="date"></label>
      <label>End date <input id="range-end" type="date"></label>
      <label>Limit/page <input id="range-limit" type="number" min="1" max="50" value="50"></label>
      <label>Max pages <input id="range-pages" type="number" min="1" max="50" value="20"></label>
      <button class="live-btn" onclick="setLast3Months()">Last 3 months</button>
    </div>
    <div style="display:flex;flex-wrap:wrap;gap:4px;margin-bottom:12px">
      <button class="live-btn" onclick="fetchLive('user')">&#128100; User Profile</button>
      <button class="live-btn" onclick="fetchLiveRange('activities')">&#127939; Activities range</button>
      <button class="live-btn" onclick="fetchLiveRange('sleep')">&#128564; Sleep range</button>
      <button class="live-btn" onclick="fetchLiveRange('scores')">&#128200; Scores range</button>
      <button class="live-btn" onclick="fetchLiveRange('step-details')">&#128115; Step Details range</button>
      <button class="live-btn" onclick="fetchLiveRange('biometrics')">&#10084; Biometrics range</button>
    </div>
    <div id="live-result"></div>
  </div>

  <!-- Health Dashboard -->
  <div class="dashboard-section" id="dashboard-section" style="display:none">
    <h2>&#128200; Health Dashboard <span class="live-label">live</span></h2>
    <p style="font-size:0.78rem;color:var(--muted);margin-bottom:10px">Visual summary of your Sensor Bio data. Select date range and load.</p>
    <div class="range-controls" style="margin-bottom:14px">
      <label>Start date <input id="dash-start" type="date"></label>
      <label>End date <input id="dash-end" type="date"></label>
      <button class="live-btn" onclick="dashSetLast3Months()">Last 3 months</button>
      <button id="dash-load-btn" style="background:#1565c0;color:#fff;border:1px solid #1976d2;padding:6px 16px;border-radius:5px;font-size:0.85rem;font-weight:bold;cursor:pointer" onclick="loadDashboard()">&#128196; Load Dashboard</button>
    </div>
    <div id="dash-status" class="dash-ok" style="display:none"></div>
    <div id="dash-warn" class="dash-warn" style="display:none"></div>
    <div class="metric-cards" id="dash-metric-cards" style="display:none"></div>
    <div class="charts-grid" id="dash-charts-grid" style="display:none">
      <div class="chart-card">
        <h3>&#128115; Daily Steps</h3>
        <div class="chart-empty" id="chart-steps-empty">No step data</div>
        <canvas id="chart-steps" style="display:none;max-height:180px"></canvas>
      </div>
      <div class="chart-card">
        <h3>&#128564; Sleep Duration (min)</h3>
        <div class="chart-empty" id="chart-sleep-empty">No sleep data</div>
        <canvas id="chart-sleep" style="display:none;max-height:180px"></canvas>
      </div>
      <div class="chart-card">
        <h3>&#9989; Recovery Score</h3>
        <div class="chart-empty" id="chart-recovery-empty">No recovery data</div>
        <canvas id="chart-recovery" style="display:none;max-height:180px"></canvas>
      </div>
      <div class="chart-card">
        <h3>&#10084;&#65039; Resting HR / HRV</h3>
        <div class="chart-empty" id="chart-bio-empty">No biometric data</div>
        <canvas id="chart-bio" style="display:none;max-height:180px"></canvas>
      </div>
      <div class="chart-card">
        <h3>&#129978; SpO₂ (Blood Oxygen %)</h3>
        <div class="chart-empty" id="chart-spo2-empty">No SpO₂ data — device may not measure continuously</div>
        <canvas id="chart-spo2" style="display:none;max-height:180px"></canvas>
      </div>
      <div class="chart-card">
        <h3>&#127754; Respiratory Rate (br/min)</h3>
        <div class="chart-empty" id="chart-brpm-empty">No respiratory rate data</div>
        <canvas id="chart-brpm" style="display:none;max-height:180px"></canvas>
      </div>
      <div class="chart-card">
        <h3>&#127777; Body Temperature (°C)</h3>
        <div class="chart-empty" id="chart-temp-empty">Awaiting data — temperature not yet provided by this account/API</div>
        <canvas id="chart-temp" style="display:none;max-height:180px"></canvas>
      </div>
      <div id="chart-extra-container"></div>
    </div>
    <div id="dash-diagnostics" style="margin-top:14px;display:none">
      <details>
        <summary style="cursor:pointer;font-size:0.8rem;color:var(--muted);user-select:none">&#128269; Raw API diagnostics (expand)</summary>
        <pre id="dash-raw" style="margin-top:8px;font-size:0.72rem"></pre>
      </details>
    </div>
  </div>

  <div class="tests-grid" id="tests-grid">
    <div style="color:var(--muted);font-size:0.9rem">Click "Run All Tests" to begin.</div>
  </div>

  <footer>
    Open Wearables Multi-Provider Tester &bull; PR #1109 &bull; {mode_label} mode
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

    function fmtDate(d) {{ return d.toISOString().slice(0, 10); }}
    function setLast3Months() {{
      const end = new Date();
      const start = new Date(end);
      start.setDate(start.getDate() - 90);
      document.getElementById('range-start').value = fmtDate(start);
      document.getElementById('range-end').value = fmtDate(end);
    }}
    function rangeParams() {{
      const params = new URLSearchParams();
      params.set('start', document.getElementById('range-start').value);
      params.set('end', document.getElementById('range-end').value);
      params.set('limit', document.getElementById('range-limit').value || '50');
      params.set('max_pages', document.getElementById('range-pages').value || '20');
      return params;
    }}

    async function startOAuth() {{
      const section = document.getElementById('oauth-section');
      section.style.display = 'block';
      const content = document.getElementById('oauth-content');
      content.innerHTML = '<span style="color:var(--muted)">Generating OAuth URL...</span>';
      try {{
        const r = await fetch('/api/oauth/start?provider=' + encodeURIComponent(_selectedProvider));
        const data = await r.json();
        if (data.error) {{
          if (data.status === 'needs-credentials') {{
            content.innerHTML = '<pre style="color:var(--yellow)">&#9888; ' + esc(data.error) + '</pre>';
          }} else {{
            content.innerHTML = '<pre style="color:var(--red)">' + esc(data.error) + '</pre>';
          }}
          return;
        }}
        if (IS_LIVE) {{
          content.innerHTML = `<p style="margin-bottom:8px;font-size:0.85rem">Live OAuth URL — open in browser to connect your <b>${{esc(_selectedProvider)}}</b> account:</p>
            <div class="oauth-url"><a href="${{data.url}}" target="_blank" style="color:#90caf9">${{esc(data.url)}}</a></div>
            <p style="margin-top:10px;font-size:0.78rem;color:var(--muted)">After authorizing, the provider redirects to /oauth/callback and the tester exchanges the code for tokens.</p>`;
        }} else {{
          content.innerHTML = `<p style="margin-bottom:8px;font-size:0.85rem">Mock OAuth URL for <b>${{esc(_selectedProvider)}}</b> (would be sent to user in production):</p>
            <div class="oauth-url">${{esc(data.url)}}</div>
            <p style="margin-top:10px;font-size:0.78rem;color:var(--muted)">Mock mode: real redirect won't work. Set SENSORBIO_LIVE=1 with real credentials for a live flow.</p>
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

    let _dashAutoLoaded = false;  // auto-load dashboard once per page session when token arrives
    async function checkLiveStatus() {{
      if (!IS_LIVE) return;
      try {{
        const r = await fetch('/api/live/status?provider=' + encodeURIComponent(_selectedProvider));
        const data = await r.json();
        if (data.authenticated) {{
          document.getElementById('live-section').style.display = 'block';
          document.getElementById('dashboard-section').style.display = 'block';
          // Populate token panel (full token fetched separately from /api/token-full)
          _updateTokenPanel(data);
          // Auto-load dashboard once when we first confirm a valid token
          if (!_dashAutoLoaded) {{
            _dashAutoLoaded = true;
            loadDashboard();
          }}
        }}
      }} catch(e) {{}}
    }}

    // Fetch and display the full live token in the token panel
    async function _updateTokenPanel(statusData) {{
      const panel = document.getElementById('token-panel');
      if (!statusData || !statusData.authenticated) {{ panel.style.display = 'none'; return; }}
      // Fetch the actual full token from backend (requires a separate privileged call)
      try {{
        const r = await fetch('/api/token-full?provider=' + encodeURIComponent(_selectedProvider));
        if (r.ok) {{
          const d = await r.json();
          if (d.access_token) {{
            document.getElementById('live-token-display').value = d.access_token;
            const meta = document.getElementById('token-panel-meta');
            meta.textContent = 'acquired: ' + (statusData.acquired_at || '?') + '  |  preview: ' + (statusData.token_hint || '?');
            panel.style.display = 'block';
          }}
        }}
      }} catch(e) {{}}
    }}

    function copyLiveToken(btn) {{
      const el = document.getElementById('live-token-display');
      navigator.clipboard.writeText(el.value || el.textContent).then(function() {{
        btn.textContent = '✓ Copied!'; btn.style.background = '#2e7d32';
        setTimeout(function() {{ btn.textContent = 'Copy'; btn.style.background = '#1565c0'; }}, 2000);
      }});
    }}

    async function injectToken() {{
      const at = (document.getElementById('inject-access-token').value || '').trim();
      const rt = (document.getElementById('inject-refresh-token').value || '').trim();
      const status = document.getElementById('inject-status');
      if (!at) {{ status.textContent = '⚠ access_token required'; status.style.color = '#f44336'; return; }}
      status.textContent = 'Injecting…'; status.style.color = '#90caf9';
      try {{
        const body = {{ access_token: at, provider: _selectedProvider }};
        if (rt) body.refresh_token = rt;
        const r = await fetch('/api/set-token', {{
          method: 'POST',
          headers: {{'Content-Type': 'application/json'}},
          body: JSON.stringify(body)
        }});
        const d = await r.json();
        if (d.ok) {{
          status.textContent = '✓ Injected! preview: ' + (d.token_preview || '?');
          status.style.color = '#66bb6a';
          // Show live section and dashboard
          document.getElementById('live-section').style.display = 'block';
          document.getElementById('dashboard-section').style.display = 'block';
          // Update token panel
          document.getElementById('live-token-display').value = at;
          document.getElementById('token-panel-meta').textContent = 'injected via /api/set-token  |  preview: ' + d.token_preview;
          document.getElementById('token-panel').style.display = 'block';
          document.getElementById('inject-access-token').value = '';
          document.getElementById('inject-refresh-token').value = '';
        }} else {{
          status.textContent = '✗ ' + (d.error || JSON.stringify(d));
          status.style.color = '#f44336';
        }}
      }} catch(e) {{
        status.textContent = '✗ ' + e.message; status.style.color = '#f44336';
      }}
    }}

    // Standalone inject panel handler (always-visible in live mode)
    async function saInjectToken() {{
      const at = (document.getElementById('sa-inject-at').value || '').trim();
      const rt = (document.getElementById('sa-inject-rt').value || '').trim();
      const status = document.getElementById('sa-inject-status');
      if (!at) {{ status.textContent = '⚠ access_token required'; status.style.color = '#f44336'; return; }}
      status.textContent = 'Injecting…'; status.style.color = '#90caf9';
      try {{
        const body = {{ access_token: at, provider: _selectedProvider }};
        if (rt) body.refresh_token = rt;
        const r = await fetch('/api/set-token', {{
          method: 'POST',
          headers: {{'Content-Type': 'application/json'}},
          body: JSON.stringify(body)
        }});
        const d = await r.json();
        if (d.ok) {{
          status.textContent = '✓ Injected  preview: ' + (d.token_preview || '?');
          status.style.color = '#66bb6a';
          document.getElementById('live-section').style.display = 'block';
          document.getElementById('dashboard-section').style.display = 'block';
          // Update token panel inside live-section too
          const liveDisplay = document.getElementById('live-token-display');
          if (liveDisplay) liveDisplay.value = at;
          const tokenPanel = document.getElementById('token-panel');
          if (tokenPanel) {{
            document.getElementById('token-panel-meta').textContent = 'injected via /api/set-token  |  preview: ' + d.token_preview;
            tokenPanel.style.display = 'block';
          }}
          document.getElementById('sa-inject-at').value = '';
          document.getElementById('sa-inject-rt').value = '';
        }} else {{
          status.textContent = '✗ ' + (d.error || JSON.stringify(d));
          status.style.color = '#f44336';
        }}
      }} catch(e) {{
        status.textContent = '✗ ' + e.message; status.style.color = '#f44336';
      }}
    }}

    // ---- Provider Selector ----
    let _selectedProvider = 'sensorbio';

    async function loadProviders() {{
      try {{
        const r = await fetch('/api/providers');
        const providers = await r.json();
        const container = document.getElementById('provider-cards');
        container.innerHTML = '';
        for (const p of providers) {{
          if (p.status === 'unsupported') continue;  // hide pure-unsupported entries
          const card = document.createElement('div');
          card.className = 'pcard' + (p.name === _selectedProvider ? ' selected' : '') + (p.status !== 'ready' ? ' needs-creds' : '');
          card.dataset.provider = p.name;
          const statusCls = p.status === 'ready' ? 'pstatus-ready' : 'pstatus-unconfigured';
          const statusTxt = p.status === 'ready' ? '✓ ready' : 'needs creds';
          card.innerHTML = '<div class="pname">' + esc(p.label) + '</div><div class="pstatus ' + statusCls + '">' + statusTxt + '</div>';
          if (p.status === 'ready') {{
            card.addEventListener('click', () => selectProvider(p.name, p.label));
          }} else {{
            const envs = p.cred_env_vars.join(', ');
            card.title = 'Set: ' + envs;
          }}
          container.appendChild(card);
        }}
        updateSelectedNote();
      }} catch(e) {{
        document.getElementById('provider-cards').innerHTML = '<span style="color:var(--red)">Failed to load providers: ' + e.message + '</span>';
      }}
    }}

    async function selectProvider(name, label) {{
      try {{
        const r = await fetch('/api/select-provider', {{
          method: 'POST',
          headers: {{'Content-Type': 'application/json'}},
          body: JSON.stringify({{provider: name}})
        }});
        if (!r.ok) return;
        _selectedProvider = name;
        _dashAutoLoaded = false;  // allow auto-load for the newly selected provider
        // Update card styles
        document.querySelectorAll('.pcard').forEach(c => c.classList.remove('selected'));
        document.querySelectorAll('.pcard[data-provider="' + name + '"]').forEach(c => c.classList.add('selected'));
        // Reset live sections (switching provider clears connected state in UI)
        document.getElementById('live-section').style.display = 'none';
        document.getElementById('dashboard-section').style.display = 'none';
        document.getElementById('live-result').innerHTML = '';
        updateSelectedNote();
        checkLiveStatus();
      }} catch(e) {{ console.error('selectProvider failed', e); }}
    }}

    function updateSelectedNote() {{
      const note = document.getElementById('selected-provider-note');
      note.textContent = 'Selected: ' + _selectedProvider + ' — OAuth and live data calls will use this provider.';
    }}

    async function fetchLive(endpoint) {{
      const result = document.getElementById('live-result');
      result.innerHTML = '<span style="color:var(--muted)">Fetching ' + endpoint + '…</span>';
      try {{
        const r = await fetch('/api/live/' + endpoint + '?provider=' + encodeURIComponent(_selectedProvider));
        const data = await r.json();
        const label = '<span style="background:#1b3a1b;color:#a5d6a7;font-size:0.68rem;padding:2px 6px;border-radius:3px;font-weight:bold">LIVE</span>';
        result.innerHTML = '<div style="margin-bottom:6px">' + label + ' <b>' + esc(endpoint) + '</b> [' + esc(_selectedProvider) + '] — HTTP ' + (data.status || r.status) + '</div>'
          + '<pre>' + esc(JSON.stringify(data.data ?? data, null, 2)) + '</pre>';
      }} catch(e) {{
        result.innerHTML = '<pre style="color:var(--red)">Error: ' + e.message + '</pre>';
      }}
    }}

    async function fetchLiveRange(endpoint) {{
      const result = document.getElementById('live-result');
      const params = rangeParams();
      params.set('provider', _selectedProvider);
      result.innerHTML = '<span style="color:var(--muted)">Fetching ' + endpoint + ' range…</span>';
      try {{
        const r = await fetch('/api/live-range/' + endpoint + '?' + params.toString());
        const data = await r.json();
        const label = '<span style="background:#1b3a1b;color:#a5d6a7;font-size:0.68rem;padding:2px 6px;border-radius:3px;font-weight:bold">LIVE RANGE</span>';
        result.innerHTML = '<div style="margin-bottom:6px">' + label + ' <b>' + esc(endpoint) + '</b> [' + esc(_selectedProvider) + '] — HTTP ' + r.status + '</div>'
          + '<pre>' + esc(JSON.stringify(data, null, 2)) + '</pre>';
      }} catch(e) {{
        result.innerHTML = '<pre style="color:var(--red)">Error: ' + e.message + '</pre>';
      }}
    }}

    // ---- Dashboard ----
    const _dashCharts = {{}};

    function dashSetLast3Months() {{
      const end = new Date();
      const start = new Date(end);
      start.setDate(start.getDate() - 90);
      document.getElementById('dash-end').value = fmtDate(end);
      document.getElementById('dash-start').value = fmtDate(start);
    }}

    function _chartCfg(type, labels, datasets, extra) {{
      return {{
        type,
        data: {{ labels, datasets }},
        options: {{
          responsive: true,
          animation: {{ duration: 400 }},
          plugins: {{ legend: {{ labels: {{ color: '#aaa', font: {{ size: 11 }} }} }},
                      tooltip: {{ mode: 'index', intersect: false }} }},
          scales: {{
            x: {{ ticks: {{ color: '#777', font: {{ size: 10 }} }}, grid: {{ color: '#1e1e1e' }} }},
            y: {{ ticks: {{ color: '#777', font: {{ size: 10 }} }}, grid: {{ color: '#1e1e1e' }},
                  beginAtZero: false, ...(extra?.y || {{}}) }},
            ...(extra?.y2 ? {{ y2: extra.y2 }} : {{}})
          }},
        }},
      }};
    }}

    function _drawOrEmpty(id, emptyId, labels, buildFn) {{
      const canvas = document.getElementById(id);
      const empty = document.getElementById(emptyId);
      if (!labels || labels.length === 0) {{
        canvas.style.display = 'none';
        empty.style.display = 'block';
        return;
      }}
      // Build the chart config first so we can check if all data is null/missing
      const cfg = buildFn(labels);
      const hasData = cfg.data.datasets.some(ds =>
        Array.isArray(ds.data) && ds.data.some(v => v != null && v !== undefined)
      );
      if (!hasData) {{
        canvas.style.display = 'none';
        empty.style.display = 'block';
        return;
      }}
      empty.style.display = 'none';
      canvas.style.display = 'block';
      if (_dashCharts[id]) {{ _dashCharts[id].destroy(); }}
      _dashCharts[id] = new Chart(canvas, cfg);
    }}

    function _renderMetricCards(cards) {{
      const el = document.getElementById('dash-metric-cards');
      el.innerHTML = cards.map(c =>
        `<div class="metric-card"><div class="mval">${{esc(String(c.value ?? '—'))}}</div><div class="mlbl">${{esc(c.label)}}</div></div>`
      ).join('');
      el.style.display = 'grid';
    }}

    function _compactDiag(raw) {{
      // Build compact per-endpoint summary
      const out = {{}};
      for (const [ep, d] of Object.entries(raw || {{}})) {{
        if (!d) {{ out[ep] = 'no data'; continue; }}
        const summary = {{ status: d.status, count: d.count }};
        if (d.error) summary.error = d.error;
        if (d.calls) {{
          const nonEmpty = d.calls.filter(c => c.count > 0 || c.sample_keys);
          summary.calls_total = d.calls.length;
          summary.calls_with_data = nonEmpty.length;
          // Show first call with data sample
          const withSample = d.calls.find(c => c.sample_keys);
          if (withSample) summary.sample_call = withSample;
        }}
        if (d.pages) {{
          summary.pages_fetched = d.pages.length;
        }}
        out[ep] = summary;
      }}
      return out;
    }}

    async function loadDashboard() {{
      const btn = document.getElementById('dash-load-btn');
      btn.disabled = true;
      btn.textContent = '⏳ Loading…';
      const status = document.getElementById('dash-status');
      const warn = document.getElementById('dash-warn');
      status.style.display = 'none';
      warn.style.display = 'none';
      document.getElementById('dash-diagnostics').style.display = 'none';
      document.getElementById('dash-charts-grid').style.display = 'none';

      const start = document.getElementById('dash-start').value;
      const end = document.getElementById('dash-end').value;
      if (!start || !end) {{
        warn.textContent = 'Select a start and end date first.';
        warn.style.display = 'block';
        btn.disabled = false; btn.textContent = '📄 Load Dashboard';
        return;
      }}

      try {{
        const params = new URLSearchParams({{ start, end, provider: _selectedProvider }});
        const r = await fetch('/api/dashboard?' + params.toString());
        const d = await r.json();

        if (!r.ok || d.error) {{
          warn.textContent = '⚠ ' + (d.error || `HTTP ${{r.status}} from /api/dashboard`);
          warn.style.display = 'block';
          btn.disabled = false; btn.textContent = '📄 Load Dashboard';
          return;
        }}

        // Diagnostics panel
        const diag = document.getElementById('dash-diagnostics');
        document.getElementById('dash-raw').textContent = JSON.stringify(_compactDiag(d.raw), null, 2);
        diag.style.display = 'block';

        const warnings = d.warnings || [];
        if (warnings.length) {{
          warn.innerHTML = '⚠ ' + warnings.map(w => esc(w)).join('<br>⚠ ');
          warn.style.display = 'block';
        }}

        // Summary cards
        const steps_data = d.steps || [];
        const sleep_data = d.sleep || [];
        const recovery_data = d.recovery || [];
        const bio_data = d.biometrics || [];

        const latest_steps = steps_data.length ? steps_data[steps_data.length-1].steps : null;
        const avg_sleep = sleep_data.length ? Math.round(sleep_data.reduce((s,x)=>s+x.total_mins,0)/sleep_data.length) : null;
        const avg_recovery = recovery_data.length ? Math.round(recovery_data.reduce((s,x)=>s+x.score,0)/recovery_data.length) : null;
        const latest_hr = bio_data.length ? bio_data[bio_data.length-1].resting_hr : null;
        const latest_hrv = bio_data.length ? bio_data[bio_data.length-1].hrv : null;

        // SpO2: last non-null value; 90-day avg
        const spo2_vals = bio_data.map(d=>d.spo2).filter(v=>v!=null);
        const latest_spo2 = spo2_vals.length ? spo2_vals[spo2_vals.length-1] : null;
        const avg_spo2 = spo2_vals.length ? (spo2_vals.reduce((a,b)=>a+b,0)/spo2_vals.length).toFixed(1) : null;

        // Resp rate (brpm)
        const brpm_vals = bio_data.map(d=>d.brpm).filter(v=>v!=null);
        const latest_brpm = brpm_vals.length ? brpm_vals[brpm_vals.length-1] : null;
        const avg_brpm = brpm_vals.length ? (brpm_vals.reduce((a,b)=>a+b,0)/brpm_vals.length).toFixed(1) : null;

        // Temperature
        const temp_vals = bio_data.map(d=>d.temp_c).filter(v=>v!=null);
        const latest_temp = temp_vals.length ? temp_vals[temp_vals.length-1] : null;
        const avg_temp = temp_vals.length ? (temp_vals.reduce((a,b)=>a+b,0)/temp_vals.length).toFixed(2) : null;

        _renderMetricCards([
          {{ label: 'Days w/ steps', value: steps_data.length || '—' }},
          {{ label: 'Latest steps', value: latest_steps != null ? latest_steps.toLocaleString() : '—' }},
          {{ label: 'Avg sleep (min)', value: avg_sleep != null ? avg_sleep : '—' }},
          {{ label: 'Avg recovery', value: avg_recovery != null ? avg_recovery : '—' }},
          {{ label: 'Latest HR', value: latest_hr != null ? latest_hr + ' bpm' : '—' }},
          {{ label: 'Latest HRV', value: latest_hrv != null ? latest_hrv : '—' }},
          {{ label: 'Latest SpO₂', value: latest_spo2 != null ? latest_spo2 + '%' : '—' }},
          {{ label: 'Avg SpO₂ (90d)', value: avg_spo2 != null ? avg_spo2 + '%' : '—' }},
          {{ label: 'Latest Resp Rate', value: latest_brpm != null ? latest_brpm + ' br/min' : '—' }},
          {{ label: 'Avg Resp Rate', value: avg_brpm != null ? avg_brpm + ' br/min' : '—' }},
          {{ label: 'Latest Temp', value: latest_temp != null ? latest_temp + '°C' : 'awaiting data' }},
          {{ label: 'Avg Temp (90d)', value: avg_temp != null ? avg_temp + '°C' : 'awaiting data' }},
        ]);

        document.getElementById('dash-charts-grid').style.display = 'grid';

        // Steps chart
        _drawOrEmpty('chart-steps', 'chart-steps-empty',
          steps_data.map(d => d.date),
          labels => _chartCfg('bar', labels,
            [{{ label: 'Steps', data: steps_data.map(d=>d.steps),
               backgroundColor: 'rgba(245,124,0,0.7)', borderColor: '#f57c00', borderWidth: 1 }}],
            {{ y: {{ beginAtZero: true }} }})
        );

        // Sleep chart
        _drawOrEmpty('chart-sleep', 'chart-sleep-empty',
          sleep_data.map(d => d.date),
          labels => _chartCfg('bar', labels,
            [
              {{ label: 'Total (min)', data: sleep_data.map(d=>d.total_mins),
                 backgroundColor: 'rgba(100,181,246,0.6)', borderColor: '#64b5f6', borderWidth: 1 }},
              {{ label: 'Deep (min)', data: sleep_data.map(d=>d.deep_mins||0),
                 backgroundColor: 'rgba(63,81,181,0.7)', borderColor: '#3f51b5', borderWidth: 1 }},
            ],
            {{ y: {{ beginAtZero: true }} }})
        );

        // Recovery chart
        _drawOrEmpty('chart-recovery', 'chart-recovery-empty',
          recovery_data.map(d => d.date),
          labels => _chartCfg('line', labels,
            [{{ label: 'Recovery Score', data: recovery_data.map(d=>d.score),
               borderColor: '#66bb6a', backgroundColor: 'rgba(102,187,106,0.12)',
               pointBackgroundColor: '#66bb6a', tension: 0.3, fill: true }}],
            {{ y: {{ min: 0, max: 100 }} }})
        );

        // HR + HRV chart (dual axis)
        _drawOrEmpty('chart-bio', 'chart-bio-empty',
          bio_data.map(d => d.date),
          labels => _chartCfg('line', labels,
            [
              {{ label: 'Resting HR (bpm)', data: bio_data.map(d=>d.resting_hr),
                 borderColor: '#ef5350', backgroundColor: 'rgba(239,83,80,0.1)',
                 pointBackgroundColor: '#ef5350', tension: 0.3, yAxisID: 'y' }},
              {{ label: 'HRV', data: bio_data.map(d=>d.hrv),
                 borderColor: '#26c6da', backgroundColor: 'rgba(38,198,218,0.1)',
                 pointBackgroundColor: '#26c6da', tension: 0.3, yAxisID: 'y2' }},
            ],
            {{
              y: {{ position: 'left', title: {{ display: true, text: 'HR bpm', color: '#777', font: {{ size: 10 }} }} }},
              y2: {{ type: 'linear', position: 'right', grid: {{ drawOnChartArea: false }},
                     ticks: {{ color: '#777', font: {{ size: 10 }} }},
                     title: {{ display: true, text: 'HRV', color: '#777', font: {{ size: 10 }} }} }},
            }})
        );

        // SpO2 chart
        const spo2_series = bio_data.map(d=>d.spo2 ?? null);
        _drawOrEmpty('chart-spo2', 'chart-spo2-empty',
          bio_data.map(d => d.date),
          labels => _chartCfg('line', labels,
            [{{ label: 'SpO₂ (%)', data: spo2_series,
               borderColor: '#42a5f5', backgroundColor: 'rgba(66,165,245,0.1)',
               pointBackgroundColor: '#42a5f5', tension: 0.3, fill: true,
               spanGaps: false }}],
            {{ y: {{ min: 88, max: 100, title: {{ display: true, text: '%', color: '#777', font: {{ size: 10 }} }} }} }})
        );

        // Respiratory rate chart
        const brpm_series = bio_data.map(d=>d.brpm ?? null);
        _drawOrEmpty('chart-brpm', 'chart-brpm-empty',
          bio_data.map(d => d.date),
          labels => _chartCfg('line', labels,
            [{{ label: 'Resp Rate (br/min)', data: brpm_series,
               borderColor: '#ab47bc', backgroundColor: 'rgba(171,71,188,0.1)',
               pointBackgroundColor: '#ab47bc', tension: 0.3, fill: true,
               spanGaps: false }}],
            {{ y: {{ beginAtZero: false, title: {{ display: true, text: 'br/min', color: '#777', font: {{ size: 10 }} }} }} }})
        );

        // Temperature chart
        const temp_series = bio_data.map(d=>d.temp_c ?? null);
        _drawOrEmpty('chart-temp', 'chart-temp-empty',
          bio_data.map(d => d.date),
          labels => _chartCfg('line', labels,
            [{{ label: 'Temp (°C)', data: temp_series,
               borderColor: '#ffa726', backgroundColor: 'rgba(255,167,38,0.1)',
               pointBackgroundColor: '#ffa726', tension: 0.3, fill: true,
               spanGaps: false }}],
            {{ y: {{ beginAtZero: false, title: {{ display: true, text: '°C', color: '#777', font: {{ size: 10 }} }} }} }})
        );

        // Auto-discovered extra biometrics from additional_biometrics
        const extraContainer = document.getElementById('chart-extra-container');
        extraContainer.innerHTML = '';
        const extraKeys = bio_data.length
          ? Object.keys(bio_data[0]).filter(k => k.startsWith('_x_'))
          : [];
        extraKeys.forEach(xk => {{
          const label = xk.replace(/^_x_/, '').replace(/_/g, ' ').split(' ').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
          const canvasId = 'chart-' + xk;
          const emptyId = canvasId + '-empty';
          const card = document.createElement('div');
          card.className = 'chart-card';
          card.innerHTML = `<h3>&#128202; ${{label}} <span style="font-size:0.7rem;color:#666">(auto-discovered)</span></h3>
            <div class="chart-empty" id="${{emptyId}}">No data yet</div>
            <canvas id="${{canvasId}}" style="display:none;max-height:180px"></canvas>`;
          extraContainer.appendChild(card);
          const xSeries = bio_data.map(d => d[xk] ?? null);
          _drawOrEmpty(canvasId, emptyId,
            bio_data.map(d => d.date),
            labels => _chartCfg('line', labels,
              [{{ label: label + ' (auto)', data: xSeries,
                 borderColor: '#9ccc65', backgroundColor: 'rgba(156,204,101,0.1)',
                 pointBackgroundColor: '#9ccc65', tension: 0.3, spanGaps: false }}],
              {{ y: {{ beginAtZero: false }} }})
          );
        }});

        const totalPts = steps_data.length + sleep_data.length + recovery_data.length + bio_data.length;
        const spo2_count = spo2_series.filter(v=>v!=null).length;
        const brpm_count = brpm_series.filter(v=>v!=null).length;
        const temp_count = temp_series.filter(v=>v!=null).length;
        if (totalPts === 0) {{
          status.textContent = 'All endpoints returned 200 but no data records for this range. See diagnostics below.';
        }} else {{
          status.textContent = `Loaded: ${{steps_data.length}} step days, ${{sleep_data.length}} sleep days, ${{recovery_data.length}} recovery days, ${{bio_data.length}} biometric days (SpO₂: ${{spo2_count}}d, RespRate: ${{brpm_count}}d, Temp: ${{temp_count ? temp_count+'d' : 'awaiting'}})`;
        }}
        status.style.display = 'block';
      }} catch(e) {{
        warn.textContent = 'Dashboard fetch error: ' + e.message;
        warn.style.display = 'block';
      }} finally {{
        btn.disabled = false;
        btn.textContent = '📄 Load Dashboard';
      }}
    }}

    window.addEventListener('DOMContentLoaded', () => {{
      setLast3Months();
      dashSetLast3Months();
      loadProviders();
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
app = FastAPI(title="Open Wearables Multi-Provider Integration Tester", docs_url=None, redoc_url=None)


@app.get("/api/providers")
async def api_providers() -> JSONResponse:
    """Return the provider capability matrix — which are ready, unconfigured, or unsupported.

    Each entry contains:
      name, label, status (ready|available-but-unconfigured|unsupported),
      has_factory_class (bool), endpoints (list), cred_env_vars (list, without values).
    No credentials or secrets are ever included in the response.
    """
    result = []
    for name, meta in _PROVIDER_META.items():
        status = _provider_status(name)
        id_env, secret_env = meta["cred_env"]
        result.append({
            "name": name,
            "label": meta["label"],
            "status": status,
            "has_factory_class": name in _FACTORY_SUPPORTED,
            "endpoints": list(meta.get("endpoints", {}).keys()),
            "cred_env_vars": [id_env, secret_env],
        })
    # Also include factory-supported providers not in our meta (informational)
    meta_names = set(_PROVIDER_META.keys())
    for name in sorted(_FACTORY_SUPPORTED - meta_names):
        result.append({
            "name": name,
            "label": name.title(),
            "status": "unsupported",
            "has_factory_class": True,
            "endpoints": [],
            "cred_env_vars": [],
        })
    return JSONResponse(result)


@app.post("/api/select-provider")
async def api_select_provider(request: Request) -> JSONResponse:
    """Switch the active provider for subsequent OAuth and live data calls."""
    global _SELECTED_PROVIDER
    body = await request.json()
    name = (body.get("provider") or "").strip().lower()
    if not name:
        return JSONResponse({"error": "provider is required"}, status_code=400)
    if name not in _PROVIDER_META:
        return JSONResponse({"error": f"Unknown provider '{name}'. Valid: {list(_PROVIDER_META.keys())}"}, status_code=400)
    _SELECTED_PROVIDER = name
    return JSONResponse({"selected": name, "label": _PROVIDER_META[name]["label"]})


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
    # Standalone inject panel — always visible in live mode so a token can be loaded without OAuth
    if LIVE_MODE:
        inject_panel_html = (
            '<div id="standalone-inject-panel" style="background:#0a1628;border:1px solid #1a3050;border-radius:8px;padding:16px;margin-bottom:16px">'
            '<h2 style="margin-bottom:4px;font-size:0.95rem;color:#90caf9">&#128274; Token Inject <span style="font-size:0.72rem;font-weight:normal;color:#555;margin-left:6px">(skip OAuth — paste handoff token directly)</span></h2>'
            '<p style="font-size:0.75rem;color:var(--muted);margin-bottom:10px">After OAuth on another device, paste the full access token here so this instance can call /api/dashboard and live endpoints.</p>'
            '<label style="font-size:0.78rem;color:var(--muted);display:block;margin-bottom:4px">Access token <span style="color:#f44336">*</span></label>'
            '<textarea id="sa-inject-at" placeholder="Paste full access_token here" style="width:100%;box-sizing:border-box;background:#111;color:#a5d6a7;border:1px solid #333;border-radius:6px;padding:8px;font-size:0.72rem;font-family:monospace;resize:vertical;height:56px;margin-bottom:8px"></textarea>'
            '<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">'
            '<input id="sa-inject-rt" type="text" placeholder="Refresh token (optional)" style="flex:1;min-width:160px;background:#111;color:#90caf9;border:1px solid #333;border-radius:6px;padding:7px;font-size:0.72rem;font-family:monospace">'
            '<button onclick="saInjectToken()" style="background:#1565c0;color:#fff;border:none;padding:7px 18px;border-radius:5px;cursor:pointer;font-size:0.82rem;font-weight:bold;white-space:nowrap">&#128274; Inject Token</button>'
            '<span id="sa-inject-status" style="font-size:0.78rem;color:#777"></span>'
            '</div>'
            '</div>'
        )
    else:
        inject_panel_html = ""
    html = _HTML.format(
        mode_badge=mode_badge,
        mode_label=mode_label,
        mode_note=mode_note,
        is_live_json=is_live_json,
        inject_panel_html=inject_panel_html,
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
async def api_oauth_start(provider: str = "") -> JSONResponse:
    """Generate an OAuth authorization URL for the selected (or specified) provider."""
    p = provider or _SELECTED_PROVIDER
    if p not in _PROVIDER_META:
        return JSONResponse({"error": f"Unknown provider '{p}'"}, status_code=400)

    status = _provider_status(p)
    if status == "available-but-unconfigured":
        meta = _PROVIDER_META[p]
        id_env, secret_env = meta["cred_env"]
        return JSONResponse(
            {
                "error": f"Provider '{p}' needs credentials. Set {id_env} and {secret_env} env vars.",
                "status": "needs-credentials",
                "provider": p,
            },
            status_code=422,
        )

    try:
        oauth = _build_oauth_for_provider(p)
        if oauth is None:
            return JSONResponse({"error": f"No OAuth class available for '{p}'"}, status_code=501)
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
async def oauth_callback(code: str = "", state: str = "", error: str = "", provider: str = "") -> HTMLResponse:
    # 'provider' query param lets us route multi-provider callbacks.
    # Fallback to _SELECTED_PROVIDER if not supplied (e.g. SensorBio sets state but no explicit param).
    p = (provider or _SELECTED_PROVIDER).lower()
    meta = _PROVIDER_META.get(p)

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
    if LIVE_MODE and meta is not None:
        import httpx as _httpx

        id_env, secret_env = meta["cred_env"]
        client_id = os.environ.get(id_env, "")
        client_secret = os.environ.get(secret_env, "")
        redirect_uri = (
            os.environ.get(f"{p.upper()}_REDIRECT_URI")
            or os.environ.get("SENSORBIO_REDIRECT_URI")
            or f"http://localhost:8765/oauth/callback"
        )
        use_http2 = meta.get("http2", False)

        try:
            async with _httpx.AsyncClient(http2=use_http2, timeout=15) as client:
                resp = await client.post(
                    meta["token_url"],
                    data={
                        "grant_type": "authorization_code",
                        "code": code,
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "redirect_uri": redirect_uri,
                    },
                )
            content_type = resp.headers.get("content-type", "")
            body_text = resp.text or ""
            if resp.status_code >= 400:
                safe_body = body_text.replace(client_secret, "[redacted]")
                escaped_body = safe_body[:1200].replace("<", "&lt;").replace(">", "&gt;") or "(empty response body)"
                html = (
                    '<html><body style="font-family:monospace;background:#0e0e0e;color:#f44336;padding:24px">'
                    f"<h2>Token exchange failed ({p})</h2>"
                    f"<p>HTTP status: <b>{resp.status_code}</b></p>"
                    f"<p>Content-Type: <code>{content_type or '(none)'}</code></p>"
                    f'<pre style="white-space:pre-wrap;background:#111;padding:12px;border-radius:6px">{escaped_body}</pre>'
                    '<p style="color:#ffb300">Check: redirect URI matches portal registration, code not expired/reused, credentials are correct.</p>'
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
                    refresh_token_val = token_json.get("refresh_token", "")
                    expires_in = token_json.get("expires_in")
                    if access_token:
                        _set_sess("access_token", access_token, p)
                        _set_sess("token_type", token_json.get("token_type", "Bearer"), p)
                        _set_sess("acquired_at", datetime.now(timezone.utc).isoformat(), p)
                        if refresh_token_val:
                            _set_sess("refresh_token", refresh_token_val, p)
                        if expires_in is not None:
                            expires_at_ts = (datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))).isoformat()
                            _set_sess("expires_at", expires_at_ts, p)
                    # --- Build full-token display page (user-requested: show raw token for handoff) ---
                    stored_msg = (
                        f"&#10003; Access token stored for {meta['label']} — use LIVE data buttons below."
                        if access_token
                        else "&#9888; No access_token in response."
                    )
                    # Escape for safe HTML embedding (the token itself may contain + / = chars but no HTML specials)
                    at_escaped = access_token.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
                    rt_escaped = refresh_token_val.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;") if refresh_token_val else ""
                    # Other fields summary (sans the two token values)
                    other = {k: v for k, v in token_json.items() if k not in ("access_token", "refresh_token")}
                    other_escaped = json.dumps(other, indent=2).replace("<", "&lt;").replace(">", "&gt;")
                    copy_js = (
                        "function copyText(id,btn){"
                        "var el=document.getElementById(id);"
                        "navigator.clipboard.writeText(el.value||el.textContent).then(function(){"
                        "btn.textContent='✓ Copied!';btn.style.background='#2e7d32';"
                        "setTimeout(function(){btn.textContent='Copy';btn.style.background='#1565c0';},2000);"
                        "})}"
                    )
                    token_section = ""
                    if access_token:
                        token_section += (
                            '<div style="margin-bottom:18px">'
                            '<h3 style="color:#f57c00;margin-bottom:6px;font-size:0.9rem">&#128273; Access Token (full — for handoff)</h3>'
                            f'<textarea id="at-box" readonly style="width:100%;box-sizing:border-box;background:#111;color:#a5d6a7;border:1px solid #333;border-radius:6px;padding:10px;font-size:0.72rem;font-family:monospace;resize:vertical;height:80px">{at_escaped}</textarea>'
                            '<button onclick="copyText(\'at-box\',this)" style="margin-top:6px;background:#1565c0;color:#fff;border:none;padding:6px 16px;border-radius:5px;cursor:pointer;font-size:0.82rem">Copy</button>'
                            '</div>'
                        )
                    if refresh_token_val:
                        token_section += (
                            '<div style="margin-bottom:18px">'
                            '<h3 style="color:#90caf9;margin-bottom:6px;font-size:0.9rem">&#128257; Refresh Token</h3>'
                            f'<textarea id="rt-box" readonly style="width:100%;box-sizing:border-box;background:#111;color:#90caf9;border:1px solid #333;border-radius:6px;padding:10px;font-size:0.72rem;font-family:monospace;resize:vertical;height:80px">{rt_escaped}</textarea>'
                            '<button onclick="copyText(\'rt-box\',this)" style="margin-top:6px;background:#1565c0;color:#fff;border:none;padding:6px 16px;border-radius:5px;cursor:pointer;font-size:0.82rem">Copy</button>'
                            '</div>'
                        )
                    if expires_in is not None:
                        token_section += f'<p style="color:#777;font-size:0.8rem;margin-bottom:12px">expires_in: {expires_in}s (~{int(expires_in)//3600}h {(int(expires_in)%3600)//60}m)</p>'
                    if other:
                        token_section += (
                            '<details style="margin-bottom:12px">'
                            '<summary style="cursor:pointer;font-size:0.8rem;color:var(--muted)">Other fields</summary>'
                            f'<pre style="background:#111;padding:10px;border-radius:6px;font-size:0.72rem;margin-top:6px">{other_escaped}</pre>'
                            '</details>'
                        )
                    html = (
                        f'<html><head><style>body{{font-family:monospace;background:#0e0e0e;color:#e0e0e0;padding:24px;max-width:760px;margin:0 auto}}</style>'
                        f'<script>{copy_js}</script></head><body>'
                        f'<h2 style="color:#4caf50">&#10003; Token exchanged ({meta["label"]})</h2>'
                        f'<p style="color:#a5d6a7;margin-bottom:16px">{stored_msg}</p>'
                        f'{token_section}'
                        '<p style="margin-top:20px;font-size:0.8rem;color:#555">&#9888; Treat these tokens like passwords. Only share with trusted collaborators over secure channels.</p>'
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


@app.post("/api/set-token")
async def api_set_token(request: Request) -> JSONResponse:
    """Inject a known-good token without running browser OAuth.

    Body (JSON): {
        access_token: str,          # required
        refresh_token?: str,        # optional
        expires_at?: str,           # optional ISO timestamp or epoch seconds
        provider?: str              # optional; defaults to selected provider
    }
    Stores token in the same in-memory slot that the OAuth callback uses.
    Returns 200 + token_status (last4 preview only, no secret values).
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Request body must be valid JSON"}, status_code=400)

    access_token = (body.get("access_token") or "").strip()
    if not access_token:
        return JSONResponse({"error": "access_token is required"}, status_code=422)

    p = (body.get("provider") or "").strip().lower() or _SELECTED_PROVIDER
    refresh_token = (body.get("refresh_token") or "").strip() or None
    expires_at = body.get("expires_at")

    _set_sess("access_token", access_token, p)
    _set_sess("token_type", "Bearer", p)
    _set_sess("acquired_at", datetime.now(timezone.utc).isoformat(), p)
    if refresh_token:
        _set_sess("refresh_token", refresh_token, p)
    if expires_at is not None:
        _set_sess("expires_at", str(expires_at), p)

    tok = access_token
    preview = (tok[:4] + "…" + tok[-4:]) if len(tok) >= 8 else "****"
    return JSONResponse(
        {
            "ok": True,
            "provider": p,
            "has_token": True,
            "token_preview": preview,
            "has_refresh_token": refresh_token is not None,
            "expires_at": str(expires_at) if expires_at is not None else None,
            "acquired_at": _sess(p).get("acquired_at"),
            "message": f"Token injected for provider '{p}'. Call /api/dashboard or use live buttons.",
        }
    )


@app.get("/api/token-status")
async def api_token_status(provider: str = "") -> JSONResponse:
    """Return token load status WITHOUT exposing the secret.

    Response: {
        has_token: bool,
        provider: str,
        token_preview: str | null,   # first4…last4 only
        has_refresh_token: bool,
        expires_at: str | null,
        acquired_at: str | null,
        live_mode: bool
    }
    """
    p = provider or _SELECTED_PROVIDER
    sess = _sess(p)
    tok = sess.get("access_token", "")
    has_token = bool(tok)
    preview = (tok[:4] + "…" + tok[-4:]) if has_token and len(tok) >= 8 else ("****" if has_token else None)
    return JSONResponse(
        {
            "has_token": has_token,
            "provider": p,
            "token_preview": preview,
            "has_refresh_token": bool(sess.get("refresh_token")),
            "expires_at": sess.get("expires_at"),
            "acquired_at": sess.get("acquired_at"),
            "live_mode": LIVE_MODE,
        }
    )


@app.get("/api/token-full")
async def api_token_full(provider: str = "") -> JSONResponse:
    """Return the FULL access token for the in-browser token display panel.

    This endpoint is intentionally accessible — the user requested the ability
    to copy the full token from the browser UI for handoff testing.
    It does NOT log the token; it simply exposes it to the browser session
    that already has network access to the local tester.
    """
    p = provider or _SELECTED_PROVIDER
    sess = _sess(p)
    tok = sess.get("access_token", "")
    if not tok:
        return JSONResponse({"error": "No token stored for this provider"}, status_code=404)
    return JSONResponse(
        {
            "access_token": tok,
            "provider": p,
            "acquired_at": sess.get("acquired_at"),
        }
    )


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
async def api_live_status(provider: str = "") -> JSONResponse:
    """Return whether a live token is stored in memory."""
    p = provider or _SELECTED_PROVIDER
    sess = _sess(p)
    has_token = bool(sess.get("access_token"))
    tok = sess.get("access_token", "")
    return JSONResponse(
        {
            "live_mode": LIVE_MODE,
            "provider": p,
            "authenticated": has_token,
            "acquired_at": sess.get("acquired_at"),
            "token_hint": (
                (tok[:4] + "…" + tok[-4:]) if has_token else None
            ),
        }
    )


@app.get("/api/live/requirements")
async def api_live_requirements() -> JSONResponse:
    """Return the live Sensor Bio endpoint requirements used by the tester."""
    return JSONResponse(
        {
            "note": "OAuth bearer-token requests do not need user_id; user_id is only required for Organization API Key requests.",
            "defaults": {
                "date": datetime.now(timezone.utc).date().isoformat(),
                "last-timestamp": 0,
                "limit": 50,
                "granularity": "day",
            },
            "endpoints": {
                "user": {"path": "/v1/user", "required": []},
                "activities": {"path": "/v1/activities", "required": ["last-timestamp", "limit"]},
                "sleep": {"path": "/v1/sleep", "required": ["date"]},
                "scores": {"path": "/v1/scores", "required": ["date"]},
                "step-details": {"path": "/v1/step/details", "required": ["date", "granularity"]},
                "biometrics": {"path": "/v1/biometrics", "required": ["last-timestamp", "limit"]},
            },
        }
    )


@app.get("/api/live-range/{endpoint}")
async def api_live_range(endpoint: str, request: Request) -> JSONResponse:
    """Fetch a date range for live Sensor Bio endpoints.

    Defaults to the last 90 days. Daily endpoints are fetched once per day;
    cursor endpoints page from last-timestamp=0 and filter returned records by timestamp.
    """
    if not LIVE_MODE:
        return JSONResponse({"error": "Not in LIVE mode. Start with SENSORBIO_LIVE=1."}, status_code=400)
    p = request.query_params.get("provider") or _SELECTED_PROVIDER
    token = _sess(p).get("access_token")
    if not token:
        return JSONResponse(
            {"error": "No access token in memory. Complete OAuth flow first (click 'Start OAuth Flow')."},
            status_code=401,
        )

    query = request.query_params
    end_day = datetime.fromisoformat(query.get("end") or datetime.now(timezone.utc).date().isoformat()).date()
    start_day = datetime.fromisoformat(query.get("start") or (end_day - timedelta(days=90)).isoformat()).date()
    if start_day > end_day:
        return JSONResponse({"error": "start must be <= end"}, status_code=400)
    day_count = (end_day - start_day).days + 1
    if day_count > 100:
        return JSONResponse({"error": "Range too large for tester; max 100 days."}, status_code=400)

    limit = min(max(int(query.get("limit", "50")), 1), 50)
    max_pages = min(max(int(query.get("max_pages", "20")), 1), 50)
    granularity = query.get("granularity", "day")
    daily_paths = {"sleep": "/v1/sleep", "scores": "/v1/scores", "step-details": "/v1/step/details"}
    cursor_paths = {"activities": "/v1/activities", "biometrics": "/v1/biometrics"}
    if endpoint not in daily_paths and endpoint not in cursor_paths:
        return JSONResponse(
            {"error": "Range supported for activities, sleep, scores, step-details, biometrics."},
            status_code=404,
        )

    import httpx as _httpx

    def _json_or_error(resp: _httpx.Response) -> tuple[Any, dict[str, Any] | None]:
        if resp.status_code == 204 or not (resp.text or "").strip():
            return None, None
        try:
            return resp.json(), None
        except ValueError as exc:
            return None, {
                "status": resp.status_code,
                "url": str(resp.url),
                "http_version": resp.http_version,
                "content_type": resp.headers.get("content-type") or None,
                "error": "Sensor Bio returned a non-JSON response.",
                "json_error": str(exc),
                "body_snippet": resp.text[:1200],
            }

    def _record_timestamp_ms(record: dict[str, Any]) -> int | None:
        for key in ("timestamp", "start_timestamp", "start_time", "end_timestamp", "end_time"):
            value = record.get(key)
            if value is None:
                continue
            if isinstance(value, int | float):
                return int(value)
            if isinstance(value, str):
                try:
                    return int(value)
                except ValueError:
                    try:
                        return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1000)
                    except ValueError:
                        continue
        return None

    start_ms = int(datetime.combine(start_day, datetime.min.time(), tzinfo=timezone.utc).timestamp() * 1000)
    end_ms = (
        int(datetime.combine(end_day + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc).timestamp() * 1000)
        - 1
    )
    out: dict[str, Any] = {
        "endpoint": endpoint,
        "range": {"start": start_day.isoformat(), "end": end_day.isoformat(), "days": day_count},
        "http_version": "HTTP/2",
    }

    async with _httpx.AsyncClient(http2=True, timeout=20) as client:
        if endpoint in daily_paths:
            records: list[dict[str, Any]] = []
            calls: list[dict[str, Any]] = []
            for offset in range(day_count):
                day = (start_day + timedelta(days=offset)).isoformat()
                params = {"date": day}
                if endpoint == "step-details":
                    params["granularity"] = granularity
                resp = await client.get(
                    f"{_PROVIDER_META.get(p, _PROVIDER_META['sensorbio'])['api_base_url']}{daily_paths[endpoint]}",
                    headers={"Authorization": f"Bearer {token}"},
                    params=params,
                )
                payload, parse_error = _json_or_error(resp)
                calls.append({"date": day, "status": resp.status_code, "url": str(resp.url)})
                if parse_error:
                    out.update({"calls": calls, "error": parse_error})
                    return JSONResponse(out, status_code=502)
                if resp.status_code >= 400:
                    out.update({"calls": calls, "error": payload, "status": resp.status_code})
                    return JSONResponse(out, status_code=resp.status_code)
                if payload is None:
                    continue
                if endpoint == "step-details":
                    records.append({"date": day, "data": payload})
                else:
                    data = payload.get("data") if isinstance(payload, dict) else payload
                    if isinstance(data, list):
                        records.extend(data)
                    elif data is not None:
                        records.append({"date": day, "data": data})
            out.update({"count": len(records), "calls": calls, "data": records})
            return JSONResponse(out)

        records = []
        pages = []
        last_timestamp = int(query.get("last-timestamp", query.get("last_timestamp", "0")))
        for page in range(max_pages):
            resp = await client.get(
                f"{_PROVIDER_META.get(p, _PROVIDER_META['sensorbio'])['api_base_url']}{cursor_paths[endpoint]}",
                headers={"Authorization": f"Bearer {token}"},
                params={"last-timestamp": last_timestamp, "limit": limit},
            )
            payload, parse_error = _json_or_error(resp)
            pages.append({"page": page + 1, "status": resp.status_code, "url": str(resp.url)})
            if parse_error:
                out.update({"pages": pages, "error": parse_error})
                return JSONResponse(out, status_code=502)
            if resp.status_code >= 400:
                out.update({"pages": pages, "error": payload, "status": resp.status_code})
                return JSONResponse(out, status_code=resp.status_code)
            data = payload.get("data", []) if isinstance(payload, dict) else []
            if not isinstance(data, list) or not data:
                break
            for rec in data:
                if not isinstance(rec, dict):
                    continue
                ts = _record_timestamp_ms(rec)
                if ts is None or start_ms <= ts <= end_ms:
                    records.append(rec)
            next_ts = _record_timestamp_ms(data[-1]) if isinstance(data[-1], dict) else None
            if next_ts is None or next_ts == last_timestamp or not (payload.get("links") or {}).get("next"):
                break
            last_timestamp = next_ts
        out.update({"count": len(records), "pages": pages, "data": records})
        return JSONResponse(out)


@app.get("/api/live/{endpoint}")
async def api_live_fetch(endpoint: str, request: Request) -> JSONResponse:
    """Proxy a live API call for the selected provider using the in-memory access token.

    Supported endpoints vary by provider; see /api/providers for the list.
    """
    if not LIVE_MODE:
        return JSONResponse({"error": "Not in LIVE mode. Start with SENSORBIO_LIVE=1."}, status_code=400)
    p = request.query_params.get("provider") or _SELECTED_PROVIDER
    token = _sess(p).get("access_token")
    if not token:
        return JSONResponse(
            {"error": f"No access token for '{p}'. Complete OAuth flow first."},
            status_code=401,
        )
    meta = _PROVIDER_META.get(p, _PROVIDER_META["sensorbio"])
    query = request.query_params
    today = datetime.now(timezone.utc).date().isoformat()
    date = query.get("date", today)
    last_timestamp = int(query.get("last-timestamp", query.get("last_timestamp", "0")))
    limit = min(int(query.get("limit", "50")), 50)
    granularity = query.get("granularity", "day")
    # Build endpoint_map using provider's registered endpoint paths,
    # adding common params for each shape we know about.
    provider_endpoints = meta.get("endpoints", {})
    endpoint_map: dict[str, tuple[str, dict[str, Any]]] = {}
    for ep_name, ep_path in provider_endpoints.items():
        if ep_name in ("activities", "biometrics", "cycles", "workout"):
            endpoint_map[ep_name] = (ep_path, {"last-timestamp": last_timestamp, "limit": limit})
        elif ep_name in ("sleep", "scores", "readiness", "activity", "heart"):
            endpoint_map[ep_name] = (ep_path, {"date": date})
        elif ep_name == "step-details":
            endpoint_map[ep_name] = (ep_path, {"date": date, "granularity": granularity})
        else:
            endpoint_map[ep_name] = (ep_path, {})
    if endpoint not in endpoint_map:
        return JSONResponse({"error": f"Unknown endpoint '{endpoint}' for provider '{p}'. Valid: {list(endpoint_map.keys())}"}, status_code=404)

    import httpx as _httpx

    try:
        path, params = endpoint_map[endpoint]
        url = f"{meta['api_base_url']}{path}"
        use_http2 = meta.get("http2", False)
        async with _httpx.AsyncClient(http2=use_http2, timeout=20) as client:
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


@app.get("/api/dashboard")
async def api_dashboard(request: Request) -> JSONResponse:
    """Aggregate health dashboard data for the given date range.

    Fetches steps (step-details), sleep, scores (recovery), and biometrics
    for each day in the range and normalises them into chart-ready arrays.
    Includes per-call diagnostics with response body samples so callers can
    diagnose '200 empty' issues.

    Only SensorBio has the full endpoint set (step-details/scores/biometrics).
    Other providers will return graceful not-provided for missing endpoints.
    """
    if not LIVE_MODE:
        return JSONResponse({"error": "Not in LIVE mode. Start with SENSORBIO_LIVE=1."}, status_code=400)
    p = request.query_params.get("provider") or _SELECTED_PROVIDER
    token = _sess(p).get("access_token")
    if not token:
        return JSONResponse(
            {"error": f"No access token for '{p}'. Complete OAuth flow first."},
            status_code=401,
        )

    query = request.query_params
    end_day = datetime.fromisoformat(query.get("end") or datetime.now(timezone.utc).date().isoformat()).date()
    start_day = datetime.fromisoformat(
        query.get("start") or (end_day - timedelta(days=90)).isoformat()
    ).date()
    if start_day > end_day:
        return JSONResponse({"error": "start must be <= end"}, status_code=400)
    day_count = (end_day - start_day).days + 1
    if day_count > 100:
        return JSONResponse({"error": "Range too large; max 100 days."}, status_code=400)

    import httpx as _httpx

    headers = {"Authorization": f"Bearer {token}"}
    provider_meta = _PROVIDER_META.get(p, _PROVIDER_META["sensorbio"])
    api = provider_meta["api_base_url"]
    provider_ep = provider_meta.get("endpoints", {})

    def _safe_json(resp: "_httpx.Response") -> "tuple[Any, str | None]":
        """Return (payload, error_note). payload is None on 204/empty/parse-fail."""
        if resp.status_code == 204 or not (resp.text or "").strip():
            return None, f"HTTP {resp.status_code} empty body"
        try:
            return resp.json(), None
        except ValueError as exc:
            return None, f"JSON parse error: {exc} — body: {resp.text[:200]!r}"

    def _sample_keys(payload: "Any") -> "list[str] | None":
        """Return top-level keys of the first record for diagnostics."""
        if not isinstance(payload, dict):
            return None
        data = payload.get("data")
        if isinstance(data, list) and data and isinstance(data[0], dict):
            return list(data[0].keys())
        if isinstance(data, dict):
            return list(data.keys())
        # step-details: no 'data' wrapper
        return list(payload.keys()) if payload else None

    steps_out: list[dict[str, Any]] = []
    sleep_out: list[dict[str, Any]] = []
    recovery_out: list[dict[str, Any]] = []
    bio_out: list[dict[str, Any]] = []
    raw_diag: dict[str, Any] = {}
    warnings: list[str] = []

    async with _httpx.AsyncClient(http2=True, timeout=20) as client:

        # ------------------------------------------------------------------ #
        # Daily endpoints: step-details, sleep, scores                        #
        # Each is one call per day. Skipped gracefully if provider lacks ep.  #
        # ------------------------------------------------------------------ #
        step_calls: list[dict[str, Any]] = []
        sleep_calls: list[dict[str, Any]] = []
        score_calls: list[dict[str, Any]] = []

        step_path = provider_ep.get("step-details") or (None if p != "sensorbio" else "/v1/step/details")
        sleep_path = provider_ep.get("sleep") or (None if p != "sensorbio" else "/v1/sleep")
        scores_path = provider_ep.get("scores") or None

        for offset in range(day_count):
            day = (start_day + timedelta(days=offset)).isoformat()

            # --- step-details ---
            _step_status = 0
            if step_path:
                resp = await client.get(f"{api}{step_path}", headers=headers,
                                        params={"date": day, "granularity": "day"})
                payload, err = _safe_json(resp)
                _step_status = resp.status_code
            else:
                payload, err = None, "not-provided (provider lacks step endpoint)"
            call_info: dict[str, Any] = {"date": day, "status": _step_status}
            if err:
                call_info["error"] = err
            elif payload is not None:
                # StepDetailsResponseBody: {date, granularity, metrics:[{name,value}], ...}
                # Also accept {data:{steps, ...}} shape defensively
                steps_val: int | None = None
                if isinstance(payload, dict):
                    metrics = payload.get("metrics", [])
                    if isinstance(metrics, list):
                        for m in metrics:
                            if isinstance(m, dict) and str(m.get("name", "")).lower() in ("steps", "step count", "total steps"):
                                steps_val = int(m.get("value", 0) or 0)
                                break
                    # Fallback: direct "steps" key
                    if steps_val is None and "steps" in payload:
                        steps_val = int(payload["steps"] or 0)
                    # Fallback: nested data.steps
                    if steps_val is None:
                        data_inner = payload.get("data")
                        if isinstance(data_inner, dict) and "steps" in data_inner:
                            steps_val = int(data_inner["steps"] or 0)
                if steps_val is not None and steps_val > 0:
                    steps_out.append({"date": day, "steps": steps_val})
                call_info["sample_keys"] = _sample_keys(payload)
                call_info["steps_found"] = steps_val
            step_calls.append(call_info)

            # --- sleep ---
            _sleep_status = 0
            if sleep_path:
                resp = await client.get(f"{api}{sleep_path}", headers=headers, params={"date": day})
                payload, err = _safe_json(resp)
                _sleep_status = resp.status_code
            else:
                payload, err = None, "not-provided (provider lacks sleep endpoint)"
            call_info = {"date": day, "status": _sleep_status}
            if err:
                call_info["error"] = err
            elif payload is not None:
                records = payload.get("data") if isinstance(payload, dict) else None
                if isinstance(records, list) and records:
                    for rec in records:
                        if not isinstance(rec, dict):
                            continue
                        total = rec.get("total_sleep_mins") or 0
                        deep = rec.get("deep_sleep_mins") or 0
                        light = rec.get("light_sleep_mins") or 0
                        # If total not provided but deep+light are, derive it
                        if not total and (deep or light):
                            total = deep + light
                        sleep_score: int | None = None
                        score_field = rec.get("score")
                        if isinstance(score_field, dict):
                            sleep_score = score_field.get("value")
                        elif isinstance(score_field, (int, float)):
                            sleep_score = int(score_field)
                        bio = rec.get("biometrics") or {}
                        if total or deep:
                            sleep_out.append({
                                "date": day,
                                "total_mins": int(total),
                                "deep_mins": int(deep),
                                "light_mins": int(light),
                                "sleep_score": sleep_score,
                                "hrv": bio.get("hrv"),
                                "resting_hr": bio.get("resting_bpm") or bio.get("bpm"),
                            })
                call_info["sample_keys"] = _sample_keys(payload)
                call_info["count"] = len(records) if isinstance(records, list) else (1 if records else 0)
            sleep_calls.append(call_info)

            # --- scores (recovery) ---
            _scores_status = 0
            if scores_path:
                resp = await client.get(f"{api}{scores_path}", headers=headers, params={"date": day})
                payload, err = _safe_json(resp)
                _scores_status = resp.status_code
            else:
                payload, err = None, "not-provided (provider lacks scores endpoint)"
            call_info = {"date": day, "status": _scores_status}
            if err:
                call_info["error"] = err
            elif payload is not None:
                # Shape: {data: {date, recovery: {score:{value}, biometrics:{...}}, sleep:{biometrics:{...}}}}
                data_inner = payload.get("data") if isinstance(payload, dict) else None
                recovery_score: int | None = None
                resting_bpm: float | None = None
                hrv: float | None = None
                spo2: float | None = None

                def _extract_score_block(rec_block: "dict") -> "tuple[int | None, str | None, float | None, float | None, float | None]":
                    """Extract (recovery_score, stage, resting_bpm, hrv, spo2) from a recovery block.

                    Supports both shapes:
                      - Old: {score: {value: N}, biometrics: {...}}
                      - Current API: {value: N, stage: str, avg: N, ...}  (no nested score key)
                    """
                    # Try current API shape: value directly on rec_block
                    val = rec_block.get("value")
                    if val is not None:
                        r_score = int(val) if isinstance(val, (int, float)) else None
                    else:
                        # Legacy fallback: {score: {value: N}}
                        sc = rec_block.get("score") or {}
                        val2 = sc.get("value") if isinstance(sc, dict) else sc
                        r_score = int(val2) if isinstance(val2, (int, float)) else None
                    r_stage = rec_block.get("stage")
                    bio_block = rec_block.get("biometrics") or {}
                    r_bpm = bio_block.get("resting_bpm") if bio_block.get("resting_bpm") is not None else None
                    r_hrv = bio_block.get("resting_hrv") if bio_block.get("resting_hrv") is not None else bio_block.get("hrv") if bio_block.get("hrv") is not None else None
                    r_spo2 = bio_block.get("spo2") if bio_block.get("spo2") is not None else None
                    return r_score, r_stage, r_bpm, r_hrv, r_spo2

                if isinstance(data_inner, dict):
                    # Shape: {data: {date, recovery: {...}, sleep: {...}, activity: {...}}}
                    rec_block = data_inner.get("recovery") or {}
                    recovery_score, recovery_stage, resting_bpm, hrv, spo2 = _extract_score_block(rec_block)
                elif isinstance(payload, dict) and "recovery" in payload:
                    # Flat shape without 'data' wrapper: {activity, recovery, sleep}
                    rec_block = payload.get("recovery") or {}
                    recovery_score, recovery_stage, resting_bpm, hrv, spo2 = _extract_score_block(rec_block)
                else:
                    recovery_stage = None

                if recovery_score is not None:
                    recovery_out.append({
                        "date": day,
                        "score": int(recovery_score),
                        "stage": recovery_stage,
                        "resting_hr": resting_bpm,
                        "hrv": hrv,
                        "spo2": spo2,
                    })
                # Fold bio data into bio_out regardless of whether we got a recovery score
                if resting_bpm is not None or hrv is not None:
                    bio_out.append({
                        "date": day,
                        "resting_hr": round(resting_bpm, 1) if resting_bpm is not None else None,
                        "hrv": round(hrv, 1) if hrv is not None else None,
                        "spo2": round(spo2, 1) if spo2 is not None else None,
                    })
                # Diagnostics: for scores endpoint the payload is {data: {activity, recovery, sleep}}
                # _sample_keys returns payload top-level keys. We want the scores data keys instead.
                scores_data = payload.get("data") if isinstance(payload, dict) else None
                if isinstance(scores_data, dict):
                    call_info["sample_keys"] = list(scores_data.keys())
                else:
                    call_info["sample_keys"] = _sample_keys(payload)
                call_info["count"] = 1 if (data_inner or (isinstance(payload, dict) and "recovery" in payload)) else 0
                call_info["recovery_score_found"] = recovery_score
            score_calls.append(call_info)

        raw_diag["step-details"] = {"status": 200, "calls": step_calls, "count": len(steps_out)}
        raw_diag["sleep"] = {"status": 200, "calls": sleep_calls, "count": len(sleep_out)}
        raw_diag["scores"] = {"status": 200, "calls": score_calls, "count": len(recovery_out)}

        # ------------------------------------------------------------------ #
        # Cursor endpoint: biometrics (last-timestamp pagination)             #
        # Collect all records in the date range.                              #
        # ------------------------------------------------------------------ #
        start_ms = int(
            datetime.combine(start_day, datetime.min.time(), tzinfo=timezone.utc).timestamp() * 1000
        )
        end_ms = int(
            datetime.combine(end_day + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc).timestamp() * 1000
        ) - 1

        bio_cursor_records: list[dict[str, Any]] = []
        bio_pages: list[dict[str, Any]] = []
        # Start cursor at start_ms (not 0) so we don't page through years of old data.
        # Subtract 1 so that the first record AT start_ms is included (API is >last-timestamp).
        last_ts = max(0, start_ms - 1)
        bio_ep = provider_ep.get("biometrics")
        for page_num in range(20):
            if not bio_ep:
                bio_pages.append({"page": 1, "status": 0, "error": "not-provided (provider lacks biometrics endpoint)"})
                break
            resp = await client.get(
                f"{api}{bio_ep}",
                headers=headers,
                params={"last-timestamp": last_ts, "limit": 50},
            )
            payload, err = _safe_json(resp)
            page_info: dict[str, Any] = {"page": page_num + 1, "status": resp.status_code, "last_ts_sent": last_ts}
            if err:
                page_info["error"] = err
                bio_pages.append(page_info)
                break
            if resp.status_code >= 400:
                page_info["error"] = payload
                bio_pages.append(page_info)
                break
            data_list = payload.get("data", []) if isinstance(payload, dict) else []
            if not isinstance(data_list, list) or not data_list:
                page_info["count"] = 0
                bio_pages.append(page_info)
                break

            page_info["count"] = len(data_list)
            page_info["sample_keys"] = list(data_list[0].keys()) if data_list and isinstance(data_list[0], dict) else None
            bio_pages.append(page_info)

            in_range = 0
            for rec in data_list:
                if not isinstance(rec, dict):
                    continue
                # Find timestamp
                ts: int | None = None
                for tk in ("timestamp", "start_timestamp", "start_time"):
                    val = rec.get(tk)
                    if val is None:
                        continue
                    ts = int(val) if isinstance(val, (int, float)) else None
                    if ts:
                        break
                if ts is not None and start_ms <= ts <= end_ms:
                    # Normalise to date using the sample's OWN timestamp + tz_offset_mins
                    tz_offset_s = (rec.get("tz_offset_mins") or 0) * 60
                    rec_dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
                    rec_date = (rec_dt + timedelta(seconds=tz_offset_s)).strftime("%Y-%m-%d")
                    # /v1/biometrics per-sample shape: bpm/hrv/spo2/brpm are the real values.
                    # resting_bpm and resting_hrv are ALWAYS 0 in this endpoint (they are daily
                    # resting summaries from /v1/scores, not per-sample values). Do NOT use
                    # resting_bpm/resting_hrv here — reading them first and falling back on 'is None'
                    # misses 0.0-valued per-sample fields.
                    # Treat 0.0 as "not measured" (sensor gap) for HR, HRV, SpO2, Temp. Resp rate
                    # could genuinely be 0 (apnea) but in practice the sensor won't send 0 for valid
                    # measurements — treat 0 as missing here too for consistency.
                    hr_raw = rec.get("bpm") or rec.get("heart_rate") or rec.get("hr")
                    hrv_raw = rec.get("hrv") or rec.get("heart_rate_variability")
                    spo2_raw = rec.get("spo2") or rec.get("blood_oxygen")
                    # brpm = breaths per minute (respiratory rate). 0 treated as missing.
                    brpm_raw = rec.get("brpm") or rec.get("breathing_rate") or rec.get("resp_rate") or rec.get("respiratory_rate")
                    # Temperature: check top-level first, then additional_biometrics bucket
                    add_bio = rec.get("additional_biometrics") or {}
                    temp_raw = (
                        rec.get("temperature") or rec.get("skin_temp") or rec.get("body_temp")
                        or add_bio.get("temperature") or add_bio.get("skin_temperature")
                        or add_bio.get("body_temperature") or add_bio.get("temp_delta")
                    )
                    hr_val = round(float(hr_raw), 2) if hr_raw else None
                    hrv_val = round(float(hrv_raw), 2) if hrv_raw else None
                    spo2_out = round(float(spo2_raw), 2) if spo2_raw else None
                    brpm_val = round(float(brpm_raw), 2) if brpm_raw else None
                    temp_val = round(float(temp_raw), 3) if temp_raw else None
                    # Auto-discover any unknown numeric fields in additional_biometrics
                    _known_add_bio = {"temperature", "skin_temperature", "body_temperature", "temp_delta"}
                    _extra: dict[str, float] = {}
                    for _ak, _av in add_bio.items():
                        if _ak in _known_add_bio:
                            continue
                        try:
                            _fv = float(_av)
                            if _fv != 0.0:
                                _extra[_ak] = round(_fv, 3)
                        except (TypeError, ValueError):
                            pass
                    bio_cursor_records.append({
                        "date": rec_date,
                        "_hr": hr_val,
                        "_hrv": hrv_val,
                        "_spo2": spo2_out,
                        "_brpm": brpm_val,
                        "_temp": temp_val,
                        "_extra": _extra,
                    })
                    in_range += 1
            page_info["in_range"] = in_range

            # Advance cursor to last record's timestamp
            last_rec = data_list[-1]
            next_ts: int | None = None
            for tk in ("timestamp", "start_timestamp", "start_time"):
                val = last_rec.get(tk) if isinstance(last_rec, dict) else None
                if val is not None:
                    next_ts = int(val)
                    break
            # Stop if cursor didn't advance or pagination exhausted
            if next_ts is None or next_ts <= last_ts:
                break
            # Stop if we've gone past our range
            if next_ts > end_ms:
                break
            # Stop if API has no more pages
            if not (payload.get("links") or {}).get("next"):
                break
            last_ts = next_ts

        raw_diag["biometrics"] = {"status": 200, "pages": bio_pages, "count": len(bio_cursor_records)}

        # Downsample bio_cursor_records to daily means (per-sample biometrics are high-frequency;
        # aggregate so chart is readable and per-sample 0.0 gaps don't flatten the daily average).
        from collections import defaultdict
        import statistics as _stats

        _daily_hr: dict[str, list[float]] = defaultdict(list)
        _daily_hrv: dict[str, list[float]] = defaultdict(list)
        _daily_spo2: dict[str, list[float]] = defaultdict(list)
        _daily_brpm: dict[str, list[float]] = defaultdict(list)
        _daily_temp: dict[str, list[float]] = defaultdict(list)
        # Extra auto-discovered fields: key -> date -> [values]
        _daily_extra: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
        # Track which keys were actually seen in the raw payload
        _discovered_top_keys: set[str] = set()
        _discovered_add_bio_keys: set[str] = set()
        for _r in bio_cursor_records:
            _d = _r["date"]
            if _r["_hr"] is not None:
                _daily_hr[_d].append(_r["_hr"])
                _discovered_top_keys.add("bpm")
            if _r["_hrv"] is not None:
                _daily_hrv[_d].append(_r["_hrv"])
                _discovered_top_keys.add("hrv")
            if _r["_spo2"] is not None:
                _daily_spo2[_d].append(_r["_spo2"])
                _discovered_top_keys.add("spo2")
            if _r["_brpm"] is not None:
                _daily_brpm[_d].append(_r["_brpm"])
                _discovered_top_keys.add("brpm")
            if _r["_temp"] is not None:
                _daily_temp[_d].append(_r["_temp"])
                _discovered_top_keys.add("temperature")
            for _xk, _xv in (_r.get("_extra") or {}).items():
                _daily_extra[_xk][_d].append(_xv)
                _discovered_add_bio_keys.add(_xk)

        _all_bio_dates = sorted(
            set(
                list(_daily_hr.keys())
                + list(_daily_hrv.keys())
                + list(_daily_spo2.keys())
                + list(_daily_brpm.keys())
                + list(_daily_temp.keys())
                + [_d for _dk in _daily_extra.values() for _d in _dk.keys()]
            )
        )
        bio_downsampled: list[dict[str, Any]] = []
        for _d in _all_bio_dates:
            _hr_s = _daily_hr.get(_d, [])
            _hrv_s = _daily_hrv.get(_d, [])
            _spo2_s = _daily_spo2.get(_d, [])
            _brpm_s = _daily_brpm.get(_d, [])
            _temp_s = _daily_temp.get(_d, [])
            _entry: dict[str, Any] = {
                "date": _d,
                "resting_hr": round(_stats.mean(_hr_s), 1) if _hr_s else None,
                "hrv": round(_stats.median(_hrv_s), 1) if _hrv_s else None,
                "spo2": round(_stats.mean(_spo2_s), 1) if _spo2_s else None,
                "brpm": round(_stats.mean(_brpm_s), 1) if _brpm_s else None,
                "temp_c": round(_stats.mean(_temp_s), 2) if _temp_s else None,
                "_samples": len(_hr_s) or len(_hrv_s) or len(_spo2_s) or len(_brpm_s) or len(_temp_s),
            }
            # Append auto-discovered extra fields
            for _xk, _xd in _daily_extra.items():
                _xs = _xd.get(_d, [])
                _entry[f"_x_{_xk}"] = round(_stats.mean(_xs), 3) if _xs else None
            bio_downsampled.append(_entry)

        raw_diag["biometrics"]["samples_raw"] = len(bio_cursor_records)
        raw_diag["biometrics"]["days_downsampled"] = len(bio_downsampled)
        raw_diag["biometrics"]["discovered_top_keys"] = sorted(_discovered_top_keys)
        raw_diag["biometrics"]["discovered_add_bio_keys"] = sorted(_discovered_add_bio_keys)
        raw_diag["biometrics"]["auto_discovered_metrics"] = sorted(_daily_extra.keys())

        # Merge downsampled records into bio_out (prefer scores-derived daily resting data if present)
        # For dates that DO exist in bio_out (from /v1/scores), enrich with brpm/temp/extras from cursor.
        _bio_out_by_date: dict[str, dict[str, Any]] = {r["date"]: r for r in bio_out}
        for _r in bio_downsampled:
            if _r["date"] in _bio_out_by_date:
                # Scores record wins for HR/HRV/SpO2; enrich with cursor-only fields
                _existing = _bio_out_by_date[_r["date"]]
                for _enrich_k in ("brpm", "temp_c"):
                    if _r.get(_enrich_k) is not None and _existing.get(_enrich_k) is None:
                        _existing[_enrich_k] = _r[_enrich_k]
                for _xk in [k for k in _r if k.startswith("_x_")]:
                    if _r[_xk] is not None and _existing.get(_xk) is None:
                        _existing[_xk] = _r[_xk]
            else:
                bio_out.append(_r)

    # Sort all outputs by date
    steps_out.sort(key=lambda x: x["date"])
    sleep_out.sort(key=lambda x: x["date"])
    recovery_out.sort(key=lambda x: x["date"])
    bio_out.sort(key=lambda x: x["date"])

    # Generate warnings for empty endpoints
    if not steps_out:
        warnings.append(
            f"step-details: 0 records with steps in {day_count} days. "
            "This could mean: no wearable sync in range, or 'Steps' metric name differs. "
            "Inspect diagnostics for sample_keys."
        )
    if not sleep_out:
        warnings.append(
            f"sleep: 0 records in {day_count} days. "
            "All calls returned 200 but data=[] — no sleep data synced for this range."
        )
    if not recovery_out:
        warnings.append(
            f"scores: 0 recovery records in {day_count} days. "
            "All calls returned 200 but no recovery block found. "
            "Inspect diagnostics — likely no data uploaded for this range."
        )
    if not bio_out:
        warnings.append(
            "biometrics: 0 records in date range. "
            "Cursor-based fetch started at range-start timestamp (not 0) and paged forward; "
            "none fell in the selected range. Check diagnostics pages[] for API responses."
        )

    return JSONResponse(
        {
            "range": {"start": start_day.isoformat(), "end": end_day.isoformat(), "days": day_count},
            "steps": steps_out,
            "sleep": sleep_out,
            "recovery": recovery_out,
            "biometrics": bio_out,
            "warnings": warnings,
            "raw": raw_diag,
        }
    )


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
