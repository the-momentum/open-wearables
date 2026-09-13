"""FIT-derived workout detail is available through the public workout API."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.factories import ApiKeyFactory, DataSourceFactory, EventRecordFactory, UserFactory, WorkoutDetailsFactory
from tests.utils import api_key_headers


@pytest.mark.parametrize("provider", ["polar", "garmin"])
def test_workouts_expose_fit_segments_and_zones(client: TestClient, db: Session, provider: str) -> None:
    user = UserFactory()
    source = DataSourceFactory(user=user, provider=provider)
    workout = EventRecordFactory(mapping=source, category="workout", type_="swimming")
    WorkoutDetailsFactory(
        event_record=workout,
        segments=[{"kind": "length", "index": 0, "elapsed_seconds": 30.0, "distance_meters": 25.0}],
        hr_zones={"zones": [{"zone": 1, "seconds": 30.0, "max_bpm": 120}], "max_hr": 190},
        power_zones={"zones": [{"zone": 1, "seconds": 10.0, "max_watts": 100}], "ftp_watts": 250},
    )
    now = datetime.now(timezone.utc)
    response = client.get(
        f"/api/v1/users/{user.id}/events/workouts",
        headers=api_key_headers(ApiKeyFactory().plain_key),
        params={
            "start_date": (now - timedelta(days=30)).isoformat(),
            "end_date": (now + timedelta(days=1)).isoformat(),
        },
    )
    assert response.status_code == 200
    result = response.json()["data"][0]
    assert result["segments"] == [{"kind": "length", "index": 0, "elapsed_seconds": 30.0, "distance_meters": 25.0}]
    assert result["hr_zones"]["zones"] == [{"zone": 1, "seconds": 30.0, "max_bpm": 120}]
    assert result["power_zones"]["ftp_watts"] == 250


@pytest.mark.parametrize("with_details", [False, True])
def test_workouts_without_fit_data_return_null(client: TestClient, db: Session, with_details: bool) -> None:
    user = UserFactory()
    workout = EventRecordFactory(mapping=DataSourceFactory(user=user), category="workout")
    if with_details:
        WorkoutDetailsFactory(event_record=workout)
    now = datetime.now(timezone.utc)
    response = client.get(
        f"/api/v1/users/{user.id}/events/workouts",
        headers=api_key_headers(ApiKeyFactory().plain_key),
        params={
            "start_date": (now - timedelta(days=30)).isoformat(),
            "end_date": (now + timedelta(days=1)).isoformat(),
        },
    )
    assert response.status_code == 200
    workout_data = response.json()["data"][0]
    assert workout_data["segments"] is None
    assert workout_data["hr_zones"] is None
    assert workout_data["power_zones"] is None
