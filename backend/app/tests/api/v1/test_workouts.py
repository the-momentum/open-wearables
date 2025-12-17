"""
Tests for workout endpoints.

Tests the /api/v1/users/{user_id}/workouts endpoint including:
- List workouts with filtering, sorting, and pagination
- Authentication and authorization
- Error cases
"""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.tests.utils import (
    api_key_headers,
    create_api_key,
    create_event_record,
    create_external_device_mapping,
    create_user,
)


class TestWorkoutsEndpoints:
    """Test suite for workout endpoints."""

    def test_get_workouts_success(self, client: TestClient, db: Session) -> None:
        """Test successfully retrieving workouts for a user."""
        # Arrange
        user = create_user(db)
        mapping = create_external_device_mapping(db, user=user)
        workout1 = create_event_record(
            db,
            mapping=mapping,
            category="workout",
            type_="running",
            duration_seconds=3600,
        )
        workout2 = create_event_record(
            db,
            mapping=mapping,
            category="workout",
            type_="cycling",
            duration_seconds=1800,
        )
        api_key = create_api_key(db)
        headers = api_key_headers(api_key.id)

        # Act
        response = client.get(f"/api/v1/users/{user.id}/workouts", headers=headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert any(w["id"] == str(workout1.id) for w in data)
        assert any(w["id"] == str(workout2.id) for w in data)

    def test_get_workouts_empty_list(self, client: TestClient, db: Session) -> None:
        """Test retrieving workouts for a user with no workouts."""
        # Arrange
        user = create_user(db)
        api_key = create_api_key(db)
        headers = api_key_headers(api_key.id)

        # Act
        response = client.get(f"/api/v1/users/{user.id}/workouts", headers=headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0

    def test_get_workouts_filters_by_category(self, client: TestClient, db: Session) -> None:
        """Test filtering workouts by category."""
        # Arrange
        user = create_user(db)
        mapping = create_external_device_mapping(db, user=user)
        workout = create_event_record(db, mapping=mapping, category="workout")
        create_event_record(db, mapping=mapping, category="sleep")
        api_key = create_api_key(db)
        headers = api_key_headers(api_key.id)

        # Act
        response = client.get(
            f"/api/v1/users/{user.id}/workouts",
            headers=headers,
            params={"category": "workout"},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == str(workout.id)
        assert data[0]["category"] == "workout"

    def test_get_workouts_filters_by_type(self, client: TestClient, db: Session) -> None:
        """Test filtering workouts by type."""
        # Arrange
        user = create_user(db)
        mapping = create_external_device_mapping(db, user=user)
        running = create_event_record(db, mapping=mapping, category="workout", type_="running")
        create_event_record(db, mapping=mapping, category="workout", type_="cycling")
        api_key = create_api_key(db)
        headers = api_key_headers(api_key.id)

        # Act - note: API uses 'record_type' parameter (not 'type') and does ILIKE substring matching
        response = client.get(
            f"/api/v1/users/{user.id}/workouts",
            headers=headers,
            params={"record_type": "running"},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == str(running.id)
        assert data[0]["type"] == "running"

    def test_get_workouts_filters_by_date_range(self, client: TestClient, db: Session) -> None:
        """Test filtering workouts by start and end datetime."""
        # Arrange
        user = create_user(db)
        mapping = create_external_device_mapping(db, user=user)
        now = datetime.now(timezone.utc)
        create_event_record(
            db,
            mapping=mapping,
            category="workout",
            start_datetime=now - timedelta(days=10),
            end_datetime=now - timedelta(days=10, hours=-1),
        )
        recent_workout = create_event_record(
            db,
            mapping=mapping,
            category="workout",
            start_datetime=now - timedelta(days=2),
            end_datetime=now - timedelta(days=2, hours=-1),
        )
        api_key = create_api_key(db)
        headers = api_key_headers(api_key.id)

        # Act - filter for last 5 days (note: API uses 'start_date' parameter, not 'start_datetime')
        start_date = (now - timedelta(days=5)).isoformat()
        response = client.get(
            f"/api/v1/users/{user.id}/workouts",
            headers=headers,
            params={"start_date": start_date},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == str(recent_workout.id)

    def test_get_workouts_pagination(self, client: TestClient, db: Session) -> None:
        """Test pagination with skip and limit parameters."""
        # Arrange
        user = create_user(db)
        mapping = create_external_device_mapping(db, user=user)
        # Create 5 workouts
        [create_event_record(db, mapping=mapping, category="workout") for _ in range(5)]
        api_key = create_api_key(db)
        headers = api_key_headers(api_key.id)

        # Act - get page 2 with 2 items per page
        response = client.get(
            f"/api/v1/users/{user.id}/workouts",
            headers=headers,
            params={"skip": 2, "limit": 2},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_get_workouts_sorting(self, client: TestClient, db: Session) -> None:
        """Test sorting workouts by start_datetime."""
        # Arrange
        user = create_user(db)
        mapping = create_external_device_mapping(db, user=user)
        now = datetime.now(timezone.utc)
        workout1 = create_event_record(
            db,
            mapping=mapping,
            category="workout",
            start_datetime=now - timedelta(hours=2),
        )
        workout2 = create_event_record(
            db,
            mapping=mapping,
            category="workout",
            start_datetime=now - timedelta(hours=1),
        )
        workout3 = create_event_record(
            db,
            mapping=mapping,
            category="workout",
            start_datetime=now,
        )
        api_key = create_api_key(db)
        headers = api_key_headers(api_key.id)

        # Act - sort by start_datetime ascending
        response = client.get(
            f"/api/v1/users/{user.id}/workouts",
            headers=headers,
            params={"sort_by": "start_datetime", "sort_order": "asc"},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        assert data[0]["id"] == str(workout1.id)
        assert data[1]["id"] == str(workout2.id)
        assert data[2]["id"] == str(workout3.id)

    def test_get_workouts_multiple_users_isolation(self, client: TestClient, db: Session) -> None:
        """Test that users can only see their own workouts."""
        # Arrange
        user1 = create_user(db)
        user2 = create_user(db)
        mapping1 = create_external_device_mapping(db, user=user1)
        mapping2 = create_external_device_mapping(db, user=user2)
        workout1 = create_event_record(db, mapping=mapping1, category="workout")
        create_event_record(db, mapping=mapping2, category="workout")
        api_key = create_api_key(db)
        headers = api_key_headers(api_key.id)

        # Act - get user1's workouts
        response = client.get(f"/api/v1/users/{user1.id}/workouts", headers=headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == str(workout1.id)

    def test_get_workouts_missing_api_key(self, client: TestClient, db: Session) -> None:
        """Test that request without API key is rejected."""
        # Arrange
        user = create_user(db)

        # Act
        response = client.get(f"/api/v1/users/{user.id}/workouts")

        # Assert
        assert response.status_code == 401

    def test_get_workouts_invalid_api_key(self, client: TestClient, db: Session) -> None:
        """Test that request with invalid API key is rejected."""
        # Arrange
        user = create_user(db)
        headers = api_key_headers("invalid-api-key")

        # Act
        response = client.get(f"/api/v1/users/{user.id}/workouts", headers=headers)

        # Assert
        assert response.status_code == 401

    def test_get_workouts_invalid_user_id(self, client: TestClient, db: Session) -> None:
        """Test handling of invalid user ID format raises ValueError."""
        # Arrange
        api_key = create_api_key(db)
        headers = api_key_headers(api_key.id)

        # Act & Assert - Invalid UUID causes ValueError with message from UUID parsing
        with pytest.raises(ValueError, match="badly formed hexadecimal UUID string"):
            client.get("/api/v1/users/not-a-uuid/workouts", headers=headers)

    def test_get_workouts_nonexistent_user(self, client: TestClient, db: Session) -> None:
        """Test retrieving workouts for a user that doesn't exist."""
        # Arrange
        from uuid import uuid4

        api_key = create_api_key(db)
        headers = api_key_headers(api_key.id)
        nonexistent_user_id = uuid4()

        # Act
        response = client.get(f"/api/v1/users/{nonexistent_user_id}/workouts", headers=headers)

        # Assert - should return empty list, not 404
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0

    def test_get_workouts_filters_by_provider(self, client: TestClient, db: Session) -> None:
        """Test filtering workouts by provider."""
        # Arrange
        user = create_user(db)
        apple_mapping = create_external_device_mapping(db, user=user, provider_id="apple")
        garmin_mapping = create_external_device_mapping(db, user=user, provider_id="garmin")
        apple_workout = create_event_record(db, mapping=apple_mapping, category="workout")
        create_event_record(db, mapping=garmin_mapping, category="workout")
        api_key = create_api_key(db)
        headers = api_key_headers(api_key.id)

        # Act
        response = client.get(
            f"/api/v1/users/{user.id}/workouts",
            headers=headers,
            params={"provider_id": "apple"},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == str(apple_workout.id)

    def test_get_workouts_response_structure(self, client: TestClient, db: Session) -> None:
        """Test that response contains all expected fields."""
        # Arrange
        user = create_user(db)
        mapping = create_external_device_mapping(db, user=user)
        create_event_record(
            db,
            mapping=mapping,
            category="workout",
            type_="running",
            duration_seconds=3600,
        )
        api_key = create_api_key(db)
        headers = api_key_headers(api_key.id)

        # Act
        response = client.get(f"/api/v1/users/{user.id}/workouts", headers=headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        workout_data = data[0]

        # Verify essential fields are present
        assert "id" in workout_data
        assert "category" in workout_data
        assert "type" in workout_data
        assert "start_datetime" in workout_data
        assert "end_datetime" in workout_data
        assert "duration_seconds" in workout_data
        assert workout_data["category"] == "workout"
