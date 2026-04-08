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
def sample_oura_workout() -> dict:
    """Sample Oura workout JSON data."""
    return {
        "id": "oura-workout-abc123",
        "activity": "running",
        "calories": 350.5,
        "day": "2024-01-15",
        "distance": 5000.0,
        "end_datetime": "2024-01-15T09:00:00+00:00",
        "intensity": "moderate",
        "start_datetime": "2024-01-15T08:00:00+00:00",
    }


@pytest.fixture
def sample_oura_sleep() -> dict:
    """Sample Oura sleep JSON data."""
    return {
        "id": "sleep-abc123",
        "average_breath": 15.5,
        "average_heart_rate": 55.0,
        "average_hrv": 45,
        "awake_time": 1800,
        "bedtime_end": "2024-01-15T07:00:00+00:00",
        "bedtime_start": "2024-01-15T23:00:00+00:00",
        "day": "2024-01-15",
        "deep_sleep_duration": 5400,
        "efficiency": 88,
        "latency": 300,
        "light_sleep_duration": 14400,
        "low_battery_alert": False,
        "lowest_heart_rate": 48,
        "period": 0,
        "rem_sleep_duration": 7200,
        "restless_periods": 5,
        "time_in_bed": 28800,
        "total_sleep_duration": 27000,
        "type": "long_sleep",
    }


@pytest.fixture
def sample_oura_readiness() -> dict:
    """Sample Oura daily readiness JSON data."""
    return {
        "id": "readiness-abc123",
        "day": "2024-01-15",
        "score": 82,
        "temperature_deviation": 0.15,
        "temperature_trend_deviation": 0.05,
        "timestamp": "2024-01-15T07:00:00+00:00",
    }


@pytest.fixture
def sample_oura_webhook_notification() -> dict:
    """Sample Oura webhook notification payload."""
    return {
        "event_type": "create",
        "data_type": "daily_sleep",
        "user_id": "oura-user-123",
        "event_timestamp": "2024-01-15T08:00:00+00:00",
        "data_timestamp": "2024-01-15",
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


@pytest.fixture
def sample_ultrahuman_sleep_data() -> dict:
    """Sample Ultrahuman sleep data object from API."""
    return {
        "date": "2024-01-15",
        "bedtime_start": 1705309200,  # 2024-01-15T01:00:00Z
        "bedtime_end": 1705334400,  # 2024-01-15T08:00:00Z
        "quick_metrics": [
            {"type": "time_in_bed", "value": 25200},
            {"type": "sleep_efic", "value": 90.5},
            {"type": "total_sleep", "value": 23400},
        ],
        "sleep_stages": [
            {"type": "deep_sleep", "stage_time": 3600},
            {"type": "light_sleep", "stage_time": 16200},
            {"type": "rem_sleep", "stage_time": 3600},
            {"type": "awake", "stage_time": 1800},
        ],
    }


@pytest.fixture
def sample_ultrahuman_minimal_sleep() -> dict:
    """Sample Ultrahuman sleep data with minimal fields."""
    return {
        "date": "2024-01-15",
    }


@pytest.fixture
def sample_ultrahuman_activity_samples() -> dict:
    """Sample Ultrahuman activity samples from API."""
    return {
        "date": "2024-01-15",
        "hr": {
            "values": [
                {"timestamp": 1705309200, "value": 62},
                {"timestamp": 1705309500, "value": 65},
                {"timestamp": 1705309800, "value": 68},
                {"timestamp": 1705310100, "value": 72},
                {"timestamp": 1705310400, "value": 75},
            ]
        },
        "hrv": {
            "values": [
                {"timestamp": 1705309200, "value": 45},
                {"timestamp": 1705309500, "value": 48},
                {"timestamp": 1705309800, "value": 52},
            ]
        },
        "temp": {
            "values": [
                {"timestamp": 1705309200, "value": 36.5},
                {"timestamp": 1705309500, "value": 36.6},
                {"timestamp": 1705309800, "value": 36.7},
                {"timestamp": 1705310100, "value": 36.8},
            ]
        },
        "steps": {
            "values": [
                {"timestamp": 1705309200, "value": 0},
                {"timestamp": 1705309500, "value": 50},
                {"timestamp": 1705309800, "value": 100},
                {"timestamp": 1705310100, "value": 250},
            ]
        },
    }


@pytest.fixture
def sample_ultrahuman_recovery_data() -> dict:
    """Sample Ultrahuman recovery data."""
    return {
        "date": "2024-01-15",
        "recovery_index": {"value": 85},
        "movement_index": {"value": 72},
        "metabolic_score": {"value": 78},
    }


@pytest.fixture
def sample_ultrahuman_api_response() -> dict:
    """Sample complete Ultrahuman /user_data/metrics API response.

    Based on the real API shape from the partner v1 /user_data/metrics endpoint.
    """
    return {
        "data": {
            "metric_data": [
                {
                    "type": "hr",
                    "object": {
                        "day_start_timestamp": 1705276800,
                        "title": "Heart Rate",
                        "values": [
                            {"value": 58, "timestamp": 1705276815},
                            {"value": 62, "timestamp": 1705277115},
                            {"value": 55, "timestamp": 1705277415},
                            {"value": 71, "timestamp": 1705277715},
                            {"value": 68, "timestamp": 1705278015},
                        ],
                        "last_reading": {"value": 68, "timestamp": 1705278015},
                        "unit": "bpm",
                    },
                },
                {
                    "type": "temp",
                    "object": {
                        "day_start_timestamp": 1705276800,
                        "title": "Skin Temperature",
                        "values": [
                            {"value": 36.2, "timestamp": 1705276815},
                            {"value": 36.4, "timestamp": 1705277115},
                            {"value": 36.3, "timestamp": 1705277415},
                            {"value": 36.5, "timestamp": 1705277715},
                        ],
                        "last_reading": {"value": 36.5, "timestamp": 1705277715},
                        "unit": "°C",
                    },
                },
                {
                    "type": "hrv",
                    "object": {
                        "day_start_timestamp": 1705276800,
                        "title": "HRV",
                        "values": [
                            {"value": 42, "timestamp": 1705276815},
                            {"value": 51, "timestamp": 1705277115},
                            {"value": 47, "timestamp": 1705277415},
                        ],
                        "subtitle": "Average",
                        "avg": 47,
                        "trend_title": "Stable",
                        "trend_direction": "neutral",
                    },
                },
                {
                    "type": "steps",
                    "object": {
                        "day_start_timestamp": 1705276800,
                        "values": [
                            {"value": 0, "timestamp": 1705276815},
                            {"value": 120, "timestamp": 1705277115},
                            {"value": 85, "timestamp": 1705277415},
                            {"value": 200, "timestamp": 1705277715},
                        ],
                        "subtitle": "Average",
                        "total": 8452,
                        "avg": 6200,
                        "trend_title": "Increasing",
                        "trend_direction": "up",
                    },
                },
                {
                    "type": "night_rhr",
                    "object": {
                        "day_start_timestamp": 1705276800,
                        "title": "Resting HR",
                        "values": [
                            {"value": 52, "timestamp": 1705290000},
                            {"value": 50, "timestamp": 1705293600},
                            {"value": 51, "timestamp": 1705297200},
                        ],
                        "subtitle": "Sleep Time Average",
                        "avg": 51,
                        "trend_title": "Stable",
                        "trend_direction": "neutral",
                    },
                },
                {
                    "type": "avg_sleep_hrv",
                    "object": {
                        "value": 48,
                        "day_start_timestamp": 1705276800,
                    },
                },
                {
                    "type": "Sleep",
                    "object": {
                        "bedtime_start": 1705287600,
                        "bedtime_end": 1705314000,
                        "quick_metrics": [
                            {
                                "title": "TIME IN BED",
                                "display_text": "7h 20m",
                                "unit": None,
                                "value": 26400,
                                "type": "time_in_bed",
                            },
                            {
                                "title": "TOTAL SLEEP",
                                "display_text": "6h 48m",
                                "value": 24480,
                                "type": "total_sleep",
                            },
                            {
                                "title": "EFFICIENCY",
                                "display_text": "91%",
                                "value": 91,
                                "type": "sleep_efic",
                            },
                            {
                                "title": "AVG HEART RATE",
                                "display_text": "52",
                                "unit": "bpm",
                                "value": 52,
                                "type": "avg_hr",
                            },
                            {
                                "title": "AVG HRV",
                                "display_text": "48",
                                "value": 48,
                                "type": "avg_hrv",
                            },
                        ],
                        "quick_metrics_tiled": [
                            {
                                "title": "TOTAL SLEEP",
                                "value": "6<b><small>h</small></b> 48<b><small>m</small></b>",
                                "tag": "Optimal",
                                "tag_color": "00B984",
                                "type": "total_sleep",
                            },
                        ],
                        "sleep_stages": [
                            {
                                "title": "Deep Sleep",
                                "type": "deep_sleep",
                                "percentage": 18,
                                "stage_time_text": "1h 18m \u2022 18%",
                                "stage_time": 4680,
                            },
                            {
                                "title": "Light Sleep",
                                "type": "light_sleep",
                                "percentage": 44,
                                "stage_time_text": "3h 12m \u2022 44%",
                                "stage_time": 11520,
                            },
                            {
                                "title": "REM Sleep",
                                "type": "rem_sleep",
                                "percentage": 30,
                                "stage_time_text": "2h 10m \u2022 30%",
                                "stage_time": 7800,
                            },
                            {
                                "title": "Awake",
                                "type": "awake",
                                "percentage": 8,
                                "stage_time_text": "35m \u2022 8%",
                                "stage_time": 2100,
                            },
                        ],
                        "sleep_graph": [],
                        "movement_graph": [],
                        "hr_graph": [],
                        "hrv_graph": [],
                        "temp_graph": [],
                        "respiratory_graph": [],
                        "summary": [
                            {"title": "Sleep Efficiency", "state": "optimal", "state_title": "Optimal", "score": 88},
                            {"title": "Temperature", "state": "optimal", "state_title": "Optimal", "score": 92},
                        ],
                        "spo2": {"title": "Average Oxygen Saturation", "value": 97, "is_beta": True},
                        "toss_turn": {"title": "Toss & Turn", "value": 12},
                        "sleep_cycles": {
                            "title": "Sleep Cycles \u2022 5",
                            "legend": [
                                {"title": "3 Full", "color": "#008A46"},
                                {"title": "2 Partial", "color": "#004223"},
                            ],
                            "cycles": [
                                {"startTime": 1705287600, "endTime": 1705291200, "cycleType": "full"},
                                {"startTime": 1705291200, "endTime": 1705294800, "cycleType": "full"},
                                {"startTime": 1705294800, "endTime": 1705298400, "cycleType": "partial"},
                            ],
                        },
                        "tags_section": {},
                    },
                },
                {
                    "type": "recovery_index",
                    "object": {"value": 78, "title": "Recovery Index", "day_start_timestamp": 1705276800},
                },
                {
                    "type": "movement_index",
                    "object": {"value": 65, "title": "Movement Index", "day_start_timestamp": 1705276800},
                },
                {
                    "type": "active_minutes",
                    "object": {"title": "Active Minutes", "day_start_timestamp": 1705276800, "value": 35},
                },
                {
                    "type": "inactive_time",
                    "object": {"title": "Inactive Time", "day_start_timestamp": 1705276800, "value": 210.0},
                },
                {
                    "type": "weekly_active_minutes",
                    "object": {"title": "Weekly Active Minutes", "day_start_timestamp": 1705276800, "value": 150},
                },
                {
                    "type": "vo2_max",
                    "object": {"value": 42.5, "title": "VO2 Max", "day_start_timestamp": 1705276800},
                },
                {
                    "type": "sleep_rhr",
                    "object": {"value": 51, "day_start_timestamp": 1705276800},
                },
                {
                    "type": "movements",
                    "object": {"title": "Movements", "day_start_timestamp": 1705276800, "value": 3200},
                },
                {
                    "type": "morning_alertness",
                    "object": {
                        "title": "Morning Alertness",
                        "day_start_timestamp": 1705276800,
                        "value": 7,
                        "unit": "/10",
                        "status": "Good",
                    },
                },
                {
                    "type": "metabolic_score",
                    "object": {"day_start_timestamp": 1705276800, "title": "Metabolic Score", "value": None},
                },
            ]
        },
    }
