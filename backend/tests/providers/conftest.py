"""
Provider-specific test fixtures.

Sample payloads for Garmin, Polar, Suunto, etc., used across provider and
integration tests.
"""

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_httpx_response() -> MagicMock:
    """Generic 200 httpx response stub."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {}
    resp.raise_for_status.return_value = None
    return resp


# ── Garmin ──────────────────────────────────────────────────────────────────


@pytest.fixture
def sample_garmin_activity() -> dict:
    return {
        "activityId": 12345678901,
        "activityName": "Morning Run",
        "activityType": {"typeKey": "running"},
        "startTimeLocal": "2024-01-15T08:00:00",
        "startTimeGMT": "2024-01-15T07:00:00",
        "duration": 3600.0,
        "distance": 10000.0,
        "averageHR": 145.0,
        "maxHR": 175,
        "calories": 650.0,
        "steps": 8500,
    }


@pytest.fixture
def sample_garmin_heart_rate_samples() -> list[dict]:
    return [{"startTimeGMT": "2024-01-15T07:00:00", "heartRate": hr} for hr in (120, 135, 145, 150, 155)]


# ── Polar ───────────────────────────────────────────────────────────────────


@pytest.fixture
def sample_polar_exercise() -> dict:
    return {
        "id": "ABC123",
        "upload_time": "2024-01-15T09:00:00.000Z",
        "polar_user": "https://www.polaraccesslink.com/v3/users/12345",
        "transaction_id": 67890,
        "device": "Polar Vantage V2",
    }
