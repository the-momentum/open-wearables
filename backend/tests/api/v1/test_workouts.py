"""
Tests for workout endpoints.

Tests the /api/v1/users/{user_id}/workouts endpoint including:
- List workouts with filtering, sorting, and pagination
- Authentication and authorization
- Error cases
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.schemas.enums import ProviderName
from tests.factories import (
    ApiKeyFactory,
    DataSourceFactory,
    EventRecordFactory,
    UserFactory,
    WorkoutDetailsFactory,
)
from tests.utils import api_key_headers

_METRICS = {
    "heart_rate_min": 95,
    "steps_count": 8500,
    "average_speed": 5.61,
    "max_speed": 13.32,
    "average_cadence": 82.5,
    "average_watts": 211.0,
    "max_watts": 604.0,
    "moving_time_seconds": 2100,
    "elev_high": 312.5,
    "elev_low": 118.25,
}

_FIT_HR = {
    "zones": [{"zone": 0, "seconds": 812.0, "max_bpm": 130}, {"zone": 1, "seconds": 240.5, "max_bpm": 150}],
    "max_hr": 189,
    "threshold_hr": 165,
}
_FIT_POWER = {"zones": [{"zone": 0, "seconds": 900.0, "max_watts": 150}], "ftp_watts": 250}
_WHOOP_HR = {"zones": [{"zone": 0, "seconds": 812.0}, {"zone": 1, "seconds": 120.5}]}
_WHOOP_HR_OUT = {
    "zones": [{"zone": 0, "seconds": 812.0, "max_bpm": None}, {"zone": 1, "seconds": 120.5, "max_bpm": None}],
    "max_hr": None,
    "threshold_hr": None,
}


def _fetch_all(client: TestClient, user_id: object, **extra: object) -> list[dict]:
    """GET the workout list over a wide window, returning every row."""
    now = datetime.now(timezone.utc)
    response = client.get(
        f"/api/v1/users/{user_id}/events/workouts",
        headers=api_key_headers(ApiKeyFactory().plain_key),
        params={
            "start_date": (now - timedelta(days=30)).isoformat(),
            "end_date": (now + timedelta(days=1)).isoformat(),
            **extra,
        },
    )
    assert response.status_code == 200
    return response.json()["data"]


def _fetch_one(client: TestClient, user_id: object, **extra: object) -> dict:
    """GET the workout list over a window wide enough to catch the factory defaults."""
    data = _fetch_all(client, user_id, **extra)
    assert len(data) == 1
    return data[0]


class TestWorkoutsEndpoints:
    """Test suite for workout endpoints."""

    def test_get_workouts_success(self, client: TestClient, db: Session) -> None:
        """Test successfully retrieving workouts for a user."""
        # Arrange
        user = UserFactory()
        mapping = DataSourceFactory(user=user)
        workout1 = EventRecordFactory(
            mapping=mapping,
            category="workout",
            type_="running",
            duration_seconds=3600,
        )
        workout2 = EventRecordFactory(
            mapping=mapping,
            category="workout",
            type_="cycling",
            duration_seconds=1800,
        )
        api_key = ApiKeyFactory()
        headers = api_key_headers(api_key.plain_key)

        # Act
        # Provide required start_date and end_date
        now = datetime.now(timezone.utc)
        start_date = (now - timedelta(days=30)).isoformat()
        end_date = (now + timedelta(days=1)).isoformat()

        response = client.get(
            f"/api/v1/users/{user.id}/events/workouts",
            headers=headers,
            params={"start_date": start_date, "end_date": end_date},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data) == 2
        assert any(w["id"] == str(workout1.id) for w in data)
        assert any(w["id"] == str(workout2.id) for w in data)

    def test_get_workouts_empty_list(self, client: TestClient, db: Session) -> None:
        """Test retrieving workouts for a user with no workouts."""
        # Arrange
        user = UserFactory()
        api_key = ApiKeyFactory()
        headers = api_key_headers(api_key.plain_key)

        # Act
        now = datetime.now(timezone.utc)
        start_date = (now - timedelta(days=30)).isoformat()
        end_date = (now + timedelta(days=1)).isoformat()

        response = client.get(
            f"/api/v1/users/{user.id}/events/workouts",
            headers=headers,
            params={"start_date": start_date, "end_date": end_date},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data) == 0

    def test_get_workouts_filters_by_category(self, client: TestClient, db: Session) -> None:
        """Test filtering workouts by category."""
        # Arrange
        user = UserFactory()
        mapping = DataSourceFactory(user=user)
        workout = EventRecordFactory(mapping=mapping, category="workout")
        EventRecordFactory(mapping=mapping, category="sleep", type="sleep")
        api_key = ApiKeyFactory()
        headers = api_key_headers(api_key.plain_key)

        # Act
        now = datetime.now(timezone.utc)
        start_date = (now - timedelta(days=30)).isoformat()
        end_date = (now + timedelta(days=1)).isoformat()

        response = client.get(
            f"/api/v1/users/{user.id}/events/workouts",
            headers=headers,
            params={"category": "workout", "start_date": start_date, "end_date": end_date},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data) == 1
        assert data[0]["id"] == str(workout.id)
        # category is not in the response model

    def test_get_workouts_filters_by_type(self, client: TestClient, db: Session) -> None:
        """Test filtering workouts by type."""
        # Arrange
        user = UserFactory()
        mapping = DataSourceFactory(user=user)
        running = EventRecordFactory(mapping=mapping, category="workout", type_="running")
        EventRecordFactory(mapping=mapping, category="workout", type_="cycling")
        api_key = ApiKeyFactory()
        headers = api_key_headers(api_key.plain_key)

        # Act - note: API uses 'record_type' parameter (not 'type') and does ILIKE substring matching
        now = datetime.now(timezone.utc)
        start_date = (now - timedelta(days=30)).isoformat()
        end_date = (now + timedelta(days=1)).isoformat()

        response = client.get(
            f"/api/v1/users/{user.id}/events/workouts",
            headers=headers,
            params={"record_type": "running", "start_date": start_date, "end_date": end_date},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data) == 1
        assert data[0]["id"] == str(running.id)
        assert data[0]["type"] == "running"

    def test_get_workouts_filters_by_date_range(self, client: TestClient, db: Session) -> None:
        """Test filtering workouts by start and end datetime."""
        # Arrange
        user = UserFactory()
        mapping = DataSourceFactory(user=user)
        now = datetime.now(timezone.utc)
        EventRecordFactory(
            mapping=mapping,
            category="workout",
            start_datetime=now - timedelta(days=10),
            end_datetime=now - timedelta(days=10, hours=-1),
        )
        recent_workout = EventRecordFactory(
            mapping=mapping,
            category="workout",
            start_datetime=now - timedelta(days=2),
            end_datetime=now - timedelta(days=2, hours=-1),
        )
        api_key = ApiKeyFactory()
        headers = api_key_headers(api_key.plain_key)

        # Act - filter for last 5 days (note: API uses 'start_date' parameter, not 'start_datetime')
        start_date = (now - timedelta(days=5)).isoformat()
        response = client.get(
            f"/api/v1/users/{user.id}/events/workouts",
            headers=headers,
            params={"start_date": start_date, "end_date": now.isoformat()},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data) == 1
        assert data[0]["id"] == str(recent_workout.id)

    def test_get_workouts_pagination(self, client: TestClient, db: Session) -> None:
        """Test pagination with skip and limit parameters."""
        # Arrange
        user = UserFactory()
        mapping = DataSourceFactory(user=user)
        # Create 5 workouts
        [EventRecordFactory(mapping=mapping, category="workout") for _ in range(5)]
        api_key = ApiKeyFactory()
        headers = api_key_headers(api_key.plain_key)

        # Act - get page 2 with 2 items per page
        now = datetime.now(timezone.utc)
        start_date = (now - timedelta(days=30)).isoformat()
        end_date = (now + timedelta(days=1)).isoformat()

        response = client.get(
            f"/api/v1/users/{user.id}/events/workouts",
            headers=headers,
            params={"skip": 2, "limit": 2, "start_date": start_date, "end_date": end_date},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data) == 2

    def test_get_workouts_sorting(self, client: TestClient, db: Session) -> None:
        """Test sorting workouts by start_datetime."""
        # Arrange
        user = UserFactory()
        mapping = DataSourceFactory(user=user)
        now = datetime.now(timezone.utc)
        workout1 = EventRecordFactory(
            mapping=mapping,
            category="workout",
            start_datetime=now - timedelta(hours=2),
        )
        workout2 = EventRecordFactory(
            mapping=mapping,
            category="workout",
            start_datetime=now - timedelta(hours=1),
        )
        workout3 = EventRecordFactory(
            mapping=mapping,
            category="workout",
            start_datetime=now,
        )
        api_key = ApiKeyFactory()
        headers = api_key_headers(api_key.plain_key)

        # Act - sort by start_datetime ascending
        now = datetime.now(timezone.utc)
        start_date = (now - timedelta(days=30)).isoformat()
        end_date = (now + timedelta(days=1)).isoformat()

        # Note: API does not currently expose sort_by/sort_order params, defaults to desc
        response = client.get(
            f"/api/v1/users/{user.id}/events/workouts",
            headers=headers,
            params={"start_date": start_date, "end_date": end_date},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data) == 3
        # Default sort is descending (newest first)
        assert data[0]["id"] == str(workout3.id)
        assert data[1]["id"] == str(workout2.id)
        assert data[2]["id"] == str(workout1.id)

    def test_get_workouts_multiple_users_isolation(self, client: TestClient, db: Session) -> None:
        """Test that users can only see their own workouts."""
        # Arrange
        user1 = UserFactory()
        user2 = UserFactory()
        mapping1 = DataSourceFactory(user=user1)
        mapping2 = DataSourceFactory(user=user2)
        workout1 = EventRecordFactory(mapping=mapping1, category="workout")
        EventRecordFactory(mapping=mapping2, category="workout")
        api_key = ApiKeyFactory()
        headers = api_key_headers(api_key.plain_key)

        # Act - get user1's workouts
        now = datetime.now(timezone.utc)
        start_date = (now - timedelta(days=30)).isoformat()
        end_date = (now + timedelta(days=1)).isoformat()

        response = client.get(
            f"/api/v1/users/{user1.id}/events/workouts",
            headers=headers,
            params={"start_date": start_date, "end_date": end_date},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data) == 1
        assert data[0]["id"] == str(workout1.id)

    def test_get_workouts_missing_api_key(self, client: TestClient, db: Session) -> None:
        """Test that request without API key is rejected."""
        # Arrange
        user = UserFactory()

        # Act
        now = datetime.now(timezone.utc)
        start_date = (now - timedelta(days=30)).isoformat()
        end_date = (now + timedelta(days=1)).isoformat()

        response = client.get(
            f"/api/v1/users/{user.id}/events/workouts", params={"start_date": start_date, "end_date": end_date}
        )

        # Assert
        assert response.status_code == 401

    def test_get_workouts_invalid_api_key(self, client: TestClient, db: Session) -> None:
        """Test that request with invalid API key is rejected."""
        # Arrange
        user = UserFactory()
        headers = api_key_headers("invalid-api-key")

        # Act
        now = datetime.now(timezone.utc)
        start_date = (now - timedelta(days=30)).isoformat()
        end_date = (now + timedelta(days=1)).isoformat()

        response = client.get(
            f"/api/v1/users/{user.id}/events/workouts",
            headers=headers,
            params={"start_date": start_date, "end_date": end_date},
        )

        # Assert
        assert response.status_code == 401

    def test_get_workouts_invalid_user_id(self, client: TestClient, db: Session) -> None:
        """Test handling of invalid user ID format."""
        # Arrange
        api_key = ApiKeyFactory()
        headers = api_key_headers(api_key.plain_key)

        # Act & Assert - Invalid UUID causes 400 Bad Request (or 422 depending on config, but here 400)
        now = datetime.now(timezone.utc)
        start_date = (now - timedelta(days=30)).isoformat()
        end_date = (now + timedelta(days=1)).isoformat()

        response = client.get(
            "/api/v1/users/not-a-uuid/events/workouts",
            headers=headers,
            params={"start_date": start_date, "end_date": end_date},
        )
        assert response.status_code == 400

    def test_get_workouts_nonexistent_user(self, client: TestClient, db: Session) -> None:
        """Test retrieving workouts for a user that doesn't exist."""
        # Arrange
        from uuid import uuid4

        api_key = ApiKeyFactory()
        headers = api_key_headers(api_key.plain_key)
        nonexistent_user_id = uuid4()

        # Act
        now = datetime.now(timezone.utc)
        start_date = (now - timedelta(days=30)).isoformat()
        end_date = (now + timedelta(days=1)).isoformat()

        response = client.get(
            f"/api/v1/users/{nonexistent_user_id}/events/workouts",
            headers=headers,
            params={"start_date": start_date, "end_date": end_date},
        )

        # Assert - should return empty list, not 404
        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data) == 0

    # test_get_workouts_filters_by_provider removed as provider filtering is not exposed in API
    def test_get_workouts_response_structure(self, client: TestClient, db: Session) -> None:
        """Every field the schema promises is present, and detail metrics carry their stored value."""
        # Arrange
        user = UserFactory()
        record = EventRecordFactory(
            mapping=DataSourceFactory(user=user),
            category="workout",
            type_="running",
            duration_seconds=3600,
        )
        WorkoutDetailsFactory(event_record=record, **_METRICS)

        # Act
        workout = _fetch_one(client, user.id)

        # Assert
        for field in ("id", "type", "start_time", "end_time", "duration_seconds", "source"):
            assert field in workout
        assert {k: workout[k] for k in _METRICS} == _METRICS
        assert workout["hr_zones"] is None
        assert workout["power_zones"] is None

    def test_zero_metrics_are_not_reported_as_missing(self, client: TestClient, db: Session) -> None:
        """0 W or 0 m is a reading, not an absence - only NULL becomes null."""
        # Arrange
        user = UserFactory()
        record = EventRecordFactory(mapping=DataSourceFactory(user=user), category="workout", type_="cycling")
        WorkoutDetailsFactory(event_record=record, **dict.fromkeys(_METRICS, 0))

        # Act
        workout = _fetch_one(client, user.id)

        # Assert
        assert {k: workout[k] for k in _METRICS} == dict.fromkeys(_METRICS, 0)

    def test_workout_without_details_serializes_with_nulls(self, client: TestClient, db: Session) -> None:
        """A workout with no details row still renders, metrics and zones alike."""
        # Arrange
        user = UserFactory()
        EventRecordFactory(mapping=DataSourceFactory(user=user), category="workout")

        # Act
        workout = _fetch_one(client, user.id, include="zones")

        # Assert
        assert all(workout[k] is None for k in _METRICS)
        assert workout["hr_zones"] is None
        assert workout["power_zones"] is None

    @pytest.mark.parametrize(
        ("stored_hr", "stored_power", "expected_hr", "expected_power"),
        [
            pytest.param(_FIT_HR, _FIT_POWER, _FIT_HR, _FIT_POWER, id="fit-full-boundaries"),
            pytest.param(_WHOOP_HR, None, _WHOOP_HR_OUT, None, id="whoop-durations-only"),
            pytest.param(None, None, None, None, id="details-without-zones"),
            pytest.param({"garbage": True}, {"zones": "not-a-list"}, None, None, id="malformed-blob"),
        ],
    )
    def test_zones_surface_as_stored(
        self,
        client: TestClient,
        db: Session,
        stored_hr: dict | None,
        stored_power: dict | None,
        expected_hr: dict | None,
        expected_power: dict | None,
    ) -> None:
        """Boundaries missing at the source stay null - never zero-filled or derived from max_hr."""
        # Arrange
        user = UserFactory()
        record = EventRecordFactory(mapping=DataSourceFactory(user=user), category="workout", type_="cycling")
        WorkoutDetailsFactory(event_record=record, hr_zones=stored_hr, power_zones=stored_power)

        # Act
        workout = _fetch_one(client, user.id, include="zones")

        # Assert
        assert workout["hr_zones"] == expected_hr
        assert workout["power_zones"] == expected_power

    def test_expansions_are_opt_in_and_validated(self, client: TestClient, db: Session) -> None:
        """Zones and segments inflate the payload, so they ship only on request; typos are rejected."""
        # Arrange
        user = UserFactory()
        record = EventRecordFactory(mapping=DataSourceFactory(user=user), category="workout", type_="cycling")
        segments = [{"lap": 1, "seconds": 300.0}, {"lap": 2, "seconds": 280.0}]
        WorkoutDetailsFactory(event_record=record, hr_zones=_FIT_HR, power_zones=_FIT_POWER, segments=segments)
        now = datetime.now(timezone.utc)

        # Act & Assert
        default = _fetch_one(client, user.id)
        assert default["hr_zones"] is None
        assert default["segments"] is None
        assert _fetch_one(client, user.id, include="zones")["hr_zones"] == _FIT_HR
        assert _fetch_one(client, user.id, include="segments")["segments"] == segments

        response = client.get(
            f"/api/v1/users/{user.id}/events/workouts",
            headers=api_key_headers(ApiKeyFactory().plain_key),
            params={
                "start_date": (now - timedelta(days=30)).isoformat(),
                "end_date": (now + timedelta(days=1)).isoformat(),
                "include": "zonez",
            },
        )
        assert response.status_code == 400

    def test_source_filters_narrow_the_list(self, client: TestClient, db: Session) -> None:
        """Every source filter is wired through to the query, not just accepted and dropped."""
        # Arrange
        user = UserFactory()
        garmin = DataSourceFactory(
            user=user, provider=ProviderName.GARMIN, device_model="Forerunner 965", source="garmin_connect"
        )
        whoop = DataSourceFactory(user=user, provider=ProviderName.WHOOP, device_model="Whoop 4.0", source="whoop_api")
        now = datetime.now(timezone.utc)
        EventRecordFactory(mapping=garmin, category="workout", type_="running", start_datetime=now)
        EventRecordFactory(mapping=whoop, category="workout", type_="running", start_datetime=now - timedelta(hours=3))

        # Act & Assert
        assert len(_fetch_all(client, user.id)) == 2
        assert len(_fetch_all(client, user.id, provider="garmin")) == 1
        assert len(_fetch_all(client, user.id, device_model="Whoop 4.0")) == 1
        assert len(_fetch_all(client, user.id, source="garmin_connect")) == 1
        assert len(_fetch_all(client, user.id, data_source_id=str(whoop.id))) == 1
        assert _fetch_all(client, user.id, provider="garmin")[0]["source"]["provider"] == "garmin"

    def test_type_matches_exactly_where_record_type_matches_a_substring(self, client: TestClient, db: Session) -> None:
        """`record_type=running` also catches trail_running; `type=running` must not."""
        # Arrange
        user = UserFactory()
        source = DataSourceFactory(user=user)
        now = datetime.now(timezone.utc)
        EventRecordFactory(mapping=source, category="workout", type_="running", start_datetime=now)
        EventRecordFactory(
            mapping=source, category="workout", type_="trail_running", start_datetime=now - timedelta(hours=3)
        )

        # Act & Assert
        assert len(_fetch_all(client, user.id, record_type="running")) == 2
        exact = _fetch_all(client, user.id, type="running")
        assert [w["type"] for w in exact] == ["running"]

    def test_workout_types_lists_only_what_the_user_has(self, client: TestClient, db: Session) -> None:
        """The dropdown source: the user's own types, not the whole 100+ member enum."""
        # Arrange
        user = UserFactory()
        other_user = UserFactory()
        source = DataSourceFactory(user=user)
        now = datetime.now(timezone.utc)
        EventRecordFactory(mapping=source, category="workout", type_="cycling", start_datetime=now)
        EventRecordFactory(mapping=source, category="workout", type_="running", start_datetime=now - timedelta(hours=3))
        EventRecordFactory(mapping=source, category="workout", type_="running", start_datetime=now - timedelta(hours=6))
        EventRecordFactory(mapping=source, category="sleep", type_="sleep", start_datetime=now - timedelta(hours=9))
        EventRecordFactory(mapping=DataSourceFactory(user=other_user), category="workout", type_="swimming")

        # Act
        response = client.get(
            f"/api/v1/users/{user.id}/events/workouts/types",
            headers=api_key_headers(ApiKeyFactory().plain_key),
        )

        # Assert
        assert response.status_code == 200
        assert response.json() == ["cycling", "running"]

    def test_pace_is_derived_from_distance_and_time(self, client: TestClient, db: Session) -> None:
        """Pace comes from distance and moving time, never from average_speed (unit varies per provider)."""
        # Arrange
        user = UserFactory()
        record = EventRecordFactory(mapping=DataSourceFactory(user=user), category="workout", type_="running")
        WorkoutDetailsFactory(
            event_record=record, distance=Decimal("10000"), moving_time_seconds=3000, average_speed=Decimal("12.00")
        )

        # Act
        workout = _fetch_one(client, user.id)

        # Assert
        assert workout["avg_pace_sec_per_km"] == 300.0

    @pytest.mark.parametrize(
        ("distance", "moving_time"),
        [
            pytest.param(None, 1800, id="no-distance"),
            pytest.param(Decimal("10000.0"), 0, id="zero-moving-time"),
        ],
    )
    def test_pace_is_null_when_it_cannot_be_derived(
        self, client: TestClient, db: Session, distance: Decimal | None, moving_time: int
    ) -> None:
        """A reported zero moving time is a value, not a gap - it must not fall back to elapsed duration."""
        # Arrange
        user = UserFactory()
        record = EventRecordFactory(mapping=DataSourceFactory(user=user), category="workout", type_="strength_training")
        WorkoutDetailsFactory(event_record=record, distance=distance, moving_time_seconds=moving_time)

        # Act & Assert
        assert _fetch_one(client, user.id)["avg_pace_sec_per_km"] is None
