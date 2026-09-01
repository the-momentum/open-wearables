"""Tests verifying SensorBio provider matches the official API spec.

Covers:
1. /v1/activities  – nested WorkoutStats → Activity response shape
2.                  – cursor uses WorkoutStats.timestamp (ms) directly
3.                  – Activity.likely_name used for workout type (no raw type field)
4. /v1/step/details – StepDetailsResponseBody with metrics[] (no data wrapper)
5. HTTP/2           – make_authenticated_request called with http2=True
"""

from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.schemas.enums import WorkoutType
from app.services.providers.api_client import make_authenticated_request
from app.services.providers.sensorbio.data_247 import SensorBio247Data
from app.services.providers.sensorbio.workouts import SensorBioWorkouts

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_oauth() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_connection_repo() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_workout_repo() -> MagicMock:
    return MagicMock()


@pytest.fixture
def workouts(mock_workout_repo: MagicMock, mock_connection_repo: MagicMock, mock_oauth: MagicMock) -> SensorBioWorkouts:
    return SensorBioWorkouts(
        workout_repo=mock_workout_repo,
        connection_repo=mock_connection_repo,
        provider_name="sensorbio",
        api_base_url="https://api.sensorbio.com",
        oauth=mock_oauth,
    )


@pytest.fixture
def data_247(mock_connection_repo: MagicMock, mock_oauth: MagicMock) -> SensorBio247Data:
    return SensorBio247Data(
        provider_name="sensorbio",
        api_base_url="https://api.sensorbio.com",
        oauth=mock_oauth,
    )


USER_ID = uuid4()
DB = MagicMock()


# ---------------------------------------------------------------------------
# 1 + 2.  /v1/activities – nested response + cursor
# ---------------------------------------------------------------------------

# Timestamps in ms (spec)
_TS_WS1_MS = 1_700_000_000_000  # WorkoutStats.timestamp
_TS_ACT_START_MS = 1_699_999_800_000
_TS_ACT_END_MS = 1_700_000_000_000

_ACTIVITIES_SINGLE_PAGE: dict[str, Any] = {
    "data": [
        {
            "timestamp": _TS_WS1_MS,
            "name": "Run",
            "activities": [
                {
                    "start_time": _TS_ACT_START_MS,
                    "end_time": _TS_ACT_END_MS,
                    "likely_name": "running",
                    "calories": 320,
                    "distance": 5000,
                    "active_time": 1800,
                    "duration": 1800,
                    "cardio_metrics": None,
                }
            ],
        }
    ],
    "links": {},  # no next → stop pagination
}


def test_get_workouts_iterates_nested_activities(workouts: SensorBioWorkouts) -> None:
    """get_workouts must yield Activity objects from WorkoutStats.activities."""
    start = datetime(2023, 11, 14, tzinfo=timezone.utc)
    end = datetime(2023, 11, 16, tzinfo=timezone.utc)

    with patch.object(workouts, "_make_api_request", return_value=_ACTIVITIES_SINGLE_PAGE):
        result = workouts.get_workouts(DB, USER_ID, start, end)

    assert len(result) == 1
    activity = result[0]
    # Should be the nested Activity, not the WorkoutStats wrapper
    assert activity["start_time"] == _TS_ACT_START_MS
    assert activity["calories"] == 320


def test_get_workouts_cursor_uses_ms_timestamp_directly(workouts: SensorBioWorkouts) -> None:
    """Pagination cursor must use WorkoutStats.timestamp (already ms) unchanged.

    The old code multiplied by 1000 if the value looked like seconds; the new
    code must NOT do that — WorkoutStats.timestamp is already milliseconds per spec.
    """
    # Two pages: first has a WorkoutStats with timestamp=1_700_000_000_000 (ms),
    # second returns empty data to stop.
    page1: dict[str, Any] = {
        "data": [
            {
                "timestamp": _TS_WS1_MS,
                "name": "Run",
                "activities": [
                    {
                        "start_time": _TS_ACT_START_MS,
                        "end_time": _TS_ACT_END_MS,
                        "likely_name": "running",
                    }
                ],
            }
        ],
        "links": {"next": "https://api.sensorbio.com/v1/activities?last-timestamp=..."},
    }
    page2: dict[str, Any] = {"data": [], "links": {}}

    mock_req = MagicMock(side_effect=[page1, page2])
    with patch.object(workouts, "_make_api_request", mock_req):
        start = datetime(2023, 11, 14, tzinfo=timezone.utc)
        end = datetime(2023, 11, 16, tzinfo=timezone.utc)
        workouts.get_workouts(DB, USER_ID, start, end)

    assert mock_req.call_count == 2
    # Second call should send last-timestamp = _TS_WS1_MS (ms, not *1000)
    second_call_params = mock_req.call_args_list[1].kwargs.get("params") or mock_req.call_args_list[1].args[3]
    assert second_call_params["last-timestamp"] == _TS_WS1_MS


def test_get_workouts_empty_activities_list_skipped(workouts: SensorBioWorkouts) -> None:
    """WorkoutStats with an empty activities array should produce zero results."""
    response: dict[str, Any] = {
        "data": [{"timestamp": _TS_WS1_MS, "name": "Walk", "activities": []}],
        "links": {},
    }
    with patch.object(workouts, "_make_api_request", return_value=response):
        start = datetime(2023, 11, 14, tzinfo=timezone.utc)
        end = datetime(2023, 11, 16, tzinfo=timezone.utc)
        result = workouts.get_workouts(DB, USER_ID, start, end)
    assert result == []


# ---------------------------------------------------------------------------
# 3.  Activity.likely_name used for workout type
# ---------------------------------------------------------------------------


def test_normalize_workout_uses_likely_name(workouts: SensorBioWorkouts) -> None:
    """_normalize_workout must map Activity.likely_name to workout type."""
    raw: dict[str, Any] = {
        "start_time": _TS_ACT_START_MS,
        "end_time": _TS_ACT_END_MS,
        "likely_name": "running",
        "calories": 300,
        "distance": 4000,
        "active_time": 1500,
        "duration": 1500,
        "cardio_metrics": None,
    }
    record, _ = workouts._normalize_workout(raw, USER_ID)
    assert record.type == WorkoutType.RUNNING.value


def test_normalize_workout_falls_back_to_workout_name(workouts: SensorBioWorkouts) -> None:
    """When likely_name is absent, fall back to _workout_name (WorkoutStats.name)."""
    raw: dict[str, Any] = {
        "start_time": _TS_ACT_START_MS,
        "end_time": _TS_ACT_END_MS,
        "likely_name": None,
        "_workout_name": "cycling",
    }
    record, _ = workouts._normalize_workout(raw, USER_ID)
    assert record.type == WorkoutType.CYCLING.value


# ---------------------------------------------------------------------------
# 4.  /v1/step/details – StepDetailsResponseBody with metrics[]
# ---------------------------------------------------------------------------

_STEP_DETAILS_RESPONSE: dict[str, Any] = {
    "date": "2024-01-15",
    "granularity": "day",
    "daily_steps_goal": 10000,
    "steps_goal_achieved_percentage": 82,
    "metrics": [
        {"name": "Steps", "value": 8200, "unit": "", "value_is_an_avg": False},
        {"name": "Distance", "value": 6.1, "unit": "km", "value_is_an_avg": False},
        {"name": "Calories", "value": 312.0, "unit": "kcal", "value_is_an_avg": False},
        {"name": "Duration", "value": 74, "unit": "min", "value_is_an_avg": False},
    ],
}


def test_normalize_daily_activity_reads_metrics_by_name(data_247: SensorBio247Data) -> None:
    """normalize_daily_activity must parse steps/distance/energy from metrics[]."""
    normalized = data_247.normalize_daily_activity(_STEP_DETAILS_RESPONSE, USER_ID)

    assert normalized["steps"] == 8200
    assert normalized["distance"] == pytest.approx(6.1)
    assert normalized["energy"] == pytest.approx(312.0)


def test_normalize_daily_activity_timestamp_from_date(data_247: SensorBio247Data) -> None:
    """Timestamp should be midnight UTC of the date field."""
    normalized = data_247.normalize_daily_activity(_STEP_DETAILS_RESPONSE, USER_ID)
    assert normalized["timestamp"] == datetime(2024, 1, 15, tzinfo=timezone.utc)


def test_normalize_daily_activity_missing_metric_is_none(data_247: SensorBio247Data) -> None:
    """When a metric is absent from the array, the field should be None."""
    response_no_calories = {
        "date": "2024-01-15",
        "granularity": "day",
        "metrics": [
            {"name": "Steps", "value": 5000},
            {"name": "Distance", "value": 3.5, "unit": "km"},
            # No Calories entry
        ],
    }
    normalized = data_247.normalize_daily_activity(response_no_calories, USER_ID)
    assert normalized["steps"] == 5000
    assert normalized["energy"] is None


def test_get_daily_activity_statistics_no_data_wrapper(data_247: SensorBio247Data) -> None:
    """get_daily_activity_statistics must handle the response as a direct
    StepDetailsResponseBody (no 'data' key wrapping it)."""
    with patch.object(data_247, "_make_api_request", return_value=_STEP_DETAILS_RESPONSE):
        result = data_247.get_daily_activity_statistics(
            DB,
            USER_ID,
            start_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
            end_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
        )

    assert len(result) == 1
    assert result[0] is _STEP_DETAILS_RESPONSE


def test_get_daily_activity_statistics_ignores_non_metrics_response(data_247: SensorBio247Data) -> None:
    """A response without a 'metrics' key (e.g. old data wrapper shape) is ignored."""
    old_shape = {"data": {"steps": 100, "distance": 1.0}}
    with patch.object(data_247, "_make_api_request", return_value=old_shape):
        result = data_247.get_daily_activity_statistics(
            DB,
            USER_ID,
            start_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
            end_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
        )
    assert result == []


# ---------------------------------------------------------------------------
# 5.  HTTP/2 – make_authenticated_request called with http2=True
# ---------------------------------------------------------------------------


def test_workouts_make_api_request_uses_http2(workouts: SensorBioWorkouts) -> None:
    """SensorBioWorkouts._make_api_request must pass http2=True."""
    with patch("app.services.providers.sensorbio.workouts.make_authenticated_request") as mock_req:
        mock_req.return_value = {"data": [], "links": {}}
        workouts._make_api_request(DB, USER_ID, "/v1/activities", params={})
    mock_req.assert_called_once()
    _, kwargs = mock_req.call_args
    assert kwargs.get("http2") is True, "http2=True must be passed for Sensor Bio workouts"


def test_data_247_make_api_request_uses_http2(data_247: SensorBio247Data) -> None:
    """SensorBio247Data._make_api_request must pass http2=True."""
    with patch("app.services.providers.sensorbio.data_247.make_authenticated_request") as mock_req:
        mock_req.return_value = {"metrics": [], "date": "2024-01-15"}
        data_247._make_api_request(DB, USER_ID, "/v1/step/details", params={})
    mock_req.assert_called_once()
    _, kwargs = mock_req.call_args
    assert kwargs.get("http2") is True, "http2=True must be passed for Sensor Bio 247 data"


def test_api_client_http2_flag_forwarded() -> None:
    """make_authenticated_request must forward http2 to the httpx.Client."""
    client_req = make_authenticated_request

    mock_repo = MagicMock()
    mock_conn = MagicMock()
    mock_conn.access_token = "tok"
    mock_conn.token_expires_at = None
    mock_repo.get_by_user_and_provider.return_value = mock_conn

    mock_oauth = MagicMock()

    with patch("httpx.Client") as mock_client_cls:
        mock_client_instance = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"ok": True}
        mock_resp.raise_for_status.return_value = None
        mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = MagicMock(return_value=False)
        mock_client_instance.request.return_value = mock_resp
        mock_client_cls.return_value = mock_client_instance

        client_req(
            db=DB,
            user_id=USER_ID,
            connection_repo=mock_repo,
            oauth=mock_oauth,
            api_base_url="https://api.sensorbio.com",
            provider_name="sensorbio",
            endpoint="/v1/activities",
            http2=True,
        )

    mock_client_cls.assert_called_once_with(http2=True)
