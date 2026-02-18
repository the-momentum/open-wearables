"""
Tests for workout endpoints.

Tests the /api/v1/users/{user_id}/workouts endpoint including:
- List workouts with filtering, sorting, and pagination
- Authentication and authorization
- Error cases
"""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from _tests.factories import ApiKeyFactory, DataSourceFactory, EventRecordFactory, UserFactory
from _tests.utils import api_key_headers


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
        headers = api_key_headers(api_key.id)

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
        headers = api_key_headers(api_key.id)

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
        headers = api_key_headers(api_key.id)

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
        headers = api_key_headers(api_key.id)

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
        headers = api_key_headers(api_key.id)

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
        headers = api_key_headers(api_key.id)

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
        headers = api_key_headers(api_key.id)

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
        headers = api_key_headers(api_key.id)

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
        headers = api_key_headers(api_key.id)

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
        headers = api_key_headers(api_key.id)
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
        """Test that response contains all expected fields."""
        # Arrange
        user = UserFactory()
        mapping = DataSourceFactory(user=user)
        EventRecordFactory(
            mapping=mapping,
            category="workout",
            type_="running",
            duration_seconds=3600,
        )
        api_key = ApiKeyFactory()
        headers = api_key_headers(api_key.id)

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
        assert len(data) == 1
        workout_data = data[0]

        # Verify essential fields are present
        assert "id" in workout_data
        # category is not in the response model
        assert "type" in workout_data
        assert "start_time" in workout_data
        assert "end_time" in workout_data
        assert "duration_seconds" in workout_data
