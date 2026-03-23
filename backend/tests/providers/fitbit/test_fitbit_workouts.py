from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.services.providers.fitbit.workouts import FitbitWorkouts

RAW_ACTIVITY = {
    "logId": 12345678,
    "activityName": "Run",
    "activityTypeId": 90009,
    "startTime": "2024-01-15T07:30:00.000+00:00",
    "duration": 3600000,  # 1 hour in ms
    "calories": 500,
    "distance": 10.0,
    "steps": 8000,
    "averageHeartRate": 155,
    "source": {"name": "Fitbit Charge 6"},
}


@pytest.fixture
def fitbit_workouts() -> FitbitWorkouts:
    workout_repo = MagicMock()
    connection_repo = MagicMock()
    oauth = MagicMock()
    return FitbitWorkouts(
        workout_repo=workout_repo,
        connection_repo=connection_repo,
        provider_name="fitbit",
        api_base_url="https://api.fitbit.com",
        oauth=oauth,
    )


def test_normalize_workout_record_fields(fitbit_workouts: FitbitWorkouts) -> None:
    user_id = uuid4()
    record, detail = fitbit_workouts._normalize_workout(RAW_ACTIVITY, user_id)

    assert record.user_id == user_id
    assert record.source == "fitbit"
    assert record.type == "running"
    assert record.external_id == "12345678"
    assert record.duration_seconds == 3600
    assert record.start_datetime == datetime(2024, 1, 15, 7, 30, 0, tzinfo=timezone.utc)


def test_normalize_workout_detail_metrics(fitbit_workouts: FitbitWorkouts) -> None:
    user_id = uuid4()
    record, detail = fitbit_workouts._normalize_workout(RAW_ACTIVITY, user_id)

    assert detail.heart_rate_avg == Decimal("155")
    assert detail.energy_burned == Decimal("500")
    assert detail.distance == Decimal("10.0")


def test_normalize_workout_missing_heart_rate(fitbit_workouts: FitbitWorkouts) -> None:
    activity = {**RAW_ACTIVITY, "averageHeartRate": None}
    user_id = uuid4()
    record, detail = fitbit_workouts._normalize_workout(activity, user_id)
    assert detail.heart_rate_avg is None


def test_normalize_workout_missing_source(fitbit_workouts: FitbitWorkouts) -> None:
    activity = {**RAW_ACTIVITY}
    del activity["source"]
    user_id = uuid4()
    record, detail = fitbit_workouts._normalize_workout(activity, user_id)
    assert record.source_name == "Fitbit"


def test_extract_dates(fitbit_workouts: FitbitWorkouts) -> None:
    start, end = fitbit_workouts._parse_fitbit_dates(
        "2024-01-15T07:30:00.000+00:00",
        3600000,
    )
    assert (end - start).total_seconds() == 3600
