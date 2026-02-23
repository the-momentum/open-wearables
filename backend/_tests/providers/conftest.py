"""
Provider-specific test fixtures.

These fixtures provide mock data and utilities for testing provider integrations.
"""

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_httpx_response() -> MagicMock:
    """Mock httpx response for provider API calls."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {}
    mock_response.raise_for_status.return_value = None
    return mock_response


@pytest.fixture
def sample_garmin_activity() -> dict:
    """Sample Garmin activity JSON data."""
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
    """Sample Garmin heart rate time series data."""
    return [
        {"startTimeGMT": "2024-01-15T07:00:00", "heartRate": 120},
        {"startTimeGMT": "2024-01-15T07:01:00", "heartRate": 135},
        {"startTimeGMT": "2024-01-15T07:02:00", "heartRate": 145},
        {"startTimeGMT": "2024-01-15T07:03:00", "heartRate": 150},
        {"startTimeGMT": "2024-01-15T07:04:00", "heartRate": 155},
    ]


@pytest.fixture
def sample_polar_exercise() -> dict:
    """Sample Polar exercise JSON data."""
    return {
        "id": "ABC123",
        "upload_time": "2024-01-15T09:00:00.000Z",
        "polar_user": "https://www.polaraccesslink.com/v3/users/12345",
        "transaction_id": 67890,
        "device": "Polar Vantage V2",
        "device_id": "12345678",
        "start_time": "2024-01-15T08:00:00",
        "start_time_utc_offset": 60,
        "duration": "PT1H0M0S",
        "calories": 650,
        "distance": 10000,
        "heart_rate": {
            "average": 145,
            "maximum": 175,
        },
        "training_load": 150.0,
        "sport": "RUNNING",
        "has_route": True,
        "detailed_sport_info": "RUNNING",
    }


@pytest.fixture
def sample_polar_heart_rate_zones() -> dict:
    """Sample Polar heart rate zones data."""
    return {
        "zone_1": {"lower_limit": 93, "upper_limit": 111, "in_zone": "PT10M"},
        "zone_2": {"lower_limit": 111, "upper_limit": 130, "in_zone": "PT15M"},
        "zone_3": {"lower_limit": 130, "upper_limit": 149, "in_zone": "PT20M"},
        "zone_4": {"lower_limit": 149, "upper_limit": 167, "in_zone": "PT10M"},
        "zone_5": {"lower_limit": 167, "upper_limit": 186, "in_zone": "PT5M"},
    }


@pytest.fixture
def sample_suunto_workout() -> dict:
    """Sample Suunto workout JSON data."""
    return {
        "workoutKey": "suunto-workout-123",
        "activityId": 1,
        "workoutName": "Morning Run",
        "startTime": 1705309200000,  # 2024-01-15T08:00:00 in milliseconds
        "totalTime": 3600000,  # 1 hour in milliseconds
        "totalDistance": 10000.0,
        "totalAscent": 150.0,
        "totalDescent": 140.0,
        "maxSpeed": 15.0,
        "avgSpeed": 10.0,
        "avgHR": 145,
        "maxHR": 175,
        "avgCadence": 85,
        "totalCalories": 650,
    }


@pytest.fixture
def sample_suunto_samples() -> dict:
    """Sample Suunto workout samples data."""
    return {
        "Samples": [
            {"TimeISO8601": "2024-01-15T08:00:00Z", "HR": 120},
            {"TimeISO8601": "2024-01-15T08:01:00Z", "HR": 135},
            {"TimeISO8601": "2024-01-15T08:02:00Z", "HR": 145},
        ],
    }


@pytest.fixture
def sample_apple_auto_export_workout() -> dict:
    """Sample Apple Auto Export workout JSON data."""
    return {
        "id": "apple-workout-123",
        "name": "Running",
        "start": "2024-01-15T08:00:00-05:00",
        "end": "2024-01-15T09:00:00-05:00",
        "duration": 3600.0,
        "distance": {"qty": 10000.0, "units": "m"},
        "activeEnergy": {"qty": 650.0, "units": "kcal"},
        "heartRateData": [
            {"date": "2024-01-15T08:00:00-05:00", "qty": 120.0},
            {"date": "2024-01-15T08:01:00-05:00", "qty": 135.0},
            {"date": "2024-01-15T08:02:00-05:00", "qty": 145.0},
        ],
        "stepCount": [
            {"date": "2024-01-15T08:00:00-05:00", "qty": 100.0},
            {"date": "2024-01-15T08:01:00-05:00", "qty": 95.0},
        ],
    }


@pytest.fixture
def sample_apple_healthkit_workout() -> dict:
    """Sample Apple HealthKit workout JSON data."""
    return {
        "uuid": "12345678-1234-1234-1234-123456789012",
        "workoutActivityType": "HKWorkoutActivityTypeRunning",
        "duration": 3600.0,
        "totalDistance": 10000.0,
        "totalEnergyBurned": 650.0,
        "startDate": "2024-01-15T08:00:00-05:00",
        "endDate": "2024-01-15T09:00:00-05:00",
        "sourceName": "Apple Watch",
        "sourceVersion": "10.0",
        "device": "Apple Watch Series 9",
    }


@pytest.fixture
def mock_oauth_token_response() -> dict:
    """Mock OAuth token exchange response."""
    return {
        "access_token": "test_access_token_abc123",
        "refresh_token": "test_refresh_token_xyz789",
        "expires_in": 3600,
        "token_type": "Bearer",
        "scope": "activity:read profile:read",
    }


@pytest.fixture
def mock_oauth_refresh_response() -> dict:
    """Mock OAuth token refresh response."""
    return {
        "access_token": "new_access_token_def456",
        "refresh_token": "new_refresh_token_uvw123",
        "expires_in": 3600,
        "token_type": "Bearer",
    }


@pytest.fixture
def mock_provider_user_info() -> dict:
    """Mock provider user info response."""
    return {
        "user_id": "provider_user_12345",
        "username": "test_user",
        "email": "test@example.com",
    }
