"""
Tests for heart rate endpoints.

Tests the /api/v1/users/{user_id}/heart-rate endpoint including:
- Get heart rate data with filtering
- Pagination and sorting
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
    create_data_point_series,
    create_external_device_mapping,
    create_user,
)


class TestHeartRateEndpoints:
    """Test suite for heart rate endpoints."""

    def test_get_heart_rate_success(self, client: TestClient, db: Session):
        """Test successfully retrieving heart rate data for a user."""
        # Arrange
        user = create_user(db)
        mapping = create_external_device_mapping(db, user=user)
        hr1 = create_data_point_series(
            db,
            mapping=mapping,
            category="heart_rate",
            value=72.0,
        )
        hr2 = create_data_point_series(
            db,
            mapping=mapping,
            category="heart_rate",
            value=85.0,
        )
        api_key = create_api_key(db)
        headers = api_key_headers(api_key.id)

        # Act
        response = client.get(f"/api/v1/users/{user.id}/heart-rate", headers=headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert any(d["id"] == str(hr1.id) for d in data)
        assert any(d["id"] == str(hr2.id) for d in data)

    def test_get_heart_rate_empty_list(self, client: TestClient, db: Session):
        """Test retrieving heart rate data for a user with no data."""
        # Arrange
        user = create_user(db)
        api_key = create_api_key(db)
        headers = api_key_headers(api_key.id)

        # Act
        response = client.get(f"/api/v1/users/{user.id}/heart-rate", headers=headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0

    def test_get_heart_rate_filters_by_timestamp(self, client: TestClient, db: Session):
        """Test filtering heart rate data by timestamp."""
        # Arrange
        user = create_user(db)
        mapping = create_external_device_mapping(db, user=user)
        now = datetime.now(timezone.utc)
        old_hr = create_data_point_series(
            db,
            mapping=mapping,
            category="heart_rate",
            value=70.0,
            timestamp=now - timedelta(days=10),
        )
        recent_hr = create_data_point_series(
            db,
            mapping=mapping,
            category="heart_rate",
            value=75.0,
            timestamp=now - timedelta(days=2),
        )
        api_key = create_api_key(db)
        headers = api_key_headers(api_key.id)

        # Act - filter for last 5 days
        start_time = (now - timedelta(days=5)).isoformat()
        response = client.get(
            f"/api/v1/users/{user.id}/heart-rate",
            headers=headers,
            params={"start_datetime": start_time},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == str(recent_hr.id)

    def test_get_heart_rate_filters_by_date_range(self, client: TestClient, db: Session):
        """Test filtering heart rate data with both start and end datetime."""
        # Arrange
        user = create_user(db)
        mapping = create_external_device_mapping(db, user=user)
        now = datetime.now(timezone.utc)
        before_range = create_data_point_series(
            db,
            mapping=mapping,
            category="heart_rate",
            value=70.0,
            timestamp=now - timedelta(days=10),
        )
        in_range = create_data_point_series(
            db,
            mapping=mapping,
            category="heart_rate",
            value=75.0,
            timestamp=now - timedelta(days=5),
        )
        after_range = create_data_point_series(
            db,
            mapping=mapping,
            category="heart_rate",
            value=80.0,
            timestamp=now,
        )
        api_key = create_api_key(db)
        headers = api_key_headers(api_key.id)

        # Act - filter for 7-3 days ago
        start_time = (now - timedelta(days=7)).isoformat()
        end_time = (now - timedelta(days=3)).isoformat()
        response = client.get(
            f"/api/v1/users/{user.id}/heart-rate",
            headers=headers,
            params={"start_datetime": start_time, "end_datetime": end_time},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == str(in_range.id)

    def test_get_heart_rate_pagination(self, client: TestClient, db: Session):
        """Test pagination with skip and limit parameters."""
        # Arrange
        user = create_user(db)
        mapping = create_external_device_mapping(db, user=user)
        # Create 10 heart rate samples
        samples = [
            create_data_point_series(
                db,
                mapping=mapping,
                category="heart_rate",
                value=70.0 + i,
            )
            for i in range(10)
        ]
        api_key = create_api_key(db)
        headers = api_key_headers(api_key.id)

        # Act - get page 2 with 3 items per page
        response = client.get(
            f"/api/v1/users/{user.id}/heart-rate",
            headers=headers,
            params={"skip": 3, "limit": 3},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

    def test_get_heart_rate_sorting(self, client: TestClient, db: Session):
        """Test sorting heart rate data by timestamp."""
        # Arrange
        user = create_user(db)
        mapping = create_external_device_mapping(db, user=user)
        now = datetime.now(timezone.utc)
        hr1 = create_data_point_series(
            db,
            mapping=mapping,
            category="heart_rate",
            value=70.0,
            timestamp=now - timedelta(hours=2),
        )
        hr2 = create_data_point_series(
            db,
            mapping=mapping,
            category="heart_rate",
            value=75.0,
            timestamp=now - timedelta(hours=1),
        )
        hr3 = create_data_point_series(
            db,
            mapping=mapping,
            category="heart_rate",
            value=80.0,
            timestamp=now,
        )
        api_key = create_api_key(db)
        headers = api_key_headers(api_key.id)

        # Act - sort by timestamp ascending
        response = client.get(
            f"/api/v1/users/{user.id}/heart-rate",
            headers=headers,
            params={"sort_by": "timestamp", "sort_order": "asc"},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        assert data[0]["id"] == str(hr1.id)
        assert data[1]["id"] == str(hr2.id)
        assert data[2]["id"] == str(hr3.id)

    def test_get_heart_rate_user_isolation(self, client: TestClient, db: Session):
        """Test that users can only see their own heart rate data."""
        # Arrange
        user1 = create_user(db)
        user2 = create_user(db)
        mapping1 = create_external_device_mapping(db, user=user1)
        mapping2 = create_external_device_mapping(db, user=user2)
        hr1 = create_data_point_series(db, mapping=mapping1, category="heart_rate", value=70.0)
        hr2 = create_data_point_series(db, mapping=mapping2, category="heart_rate", value=75.0)
        api_key = create_api_key(db)
        headers = api_key_headers(api_key.id)

        # Act - get user1's heart rate data
        response = client.get(f"/api/v1/users/{user1.id}/heart-rate", headers=headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == str(hr1.id)

    def test_get_heart_rate_filters_by_provider(self, client: TestClient, db: Session):
        """Test filtering heart rate data by provider."""
        # Arrange
        user = create_user(db)
        apple_mapping = create_external_device_mapping(db, user=user, provider_id="apple")
        garmin_mapping = create_external_device_mapping(db, user=user, provider_id="garmin")
        apple_hr = create_data_point_series(
            db, mapping=apple_mapping, category="heart_rate", value=70.0
        )
        garmin_hr = create_data_point_series(
            db, mapping=garmin_mapping, category="heart_rate", value=75.0
        )
        api_key = create_api_key(db)
        headers = api_key_headers(api_key.id)

        # Act
        response = client.get(
            f"/api/v1/users/{user.id}/heart-rate",
            headers=headers,
            params={"provider_id": "apple"},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == str(apple_hr.id)

    def test_get_heart_rate_response_structure(self, client: TestClient, db: Session):
        """Test that response contains all expected fields."""
        # Arrange
        user = create_user(db)
        mapping = create_external_device_mapping(db, user=user)
        hr = create_data_point_series(
            db,
            mapping=mapping,
            category="heart_rate",
            value=72.0,
            timestamp=datetime.now(timezone.utc),
        )
        api_key = create_api_key(db)
        headers = api_key_headers(api_key.id)

        # Act
        response = client.get(f"/api/v1/users/{user.id}/heart-rate", headers=headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        hr_data = data[0]

        # Verify essential fields are present
        assert "id" in hr_data
        assert "category" in hr_data
        assert "value" in hr_data
        assert "timestamp" in hr_data
        assert hr_data["category"] == "heart_rate"
        assert hr_data["value"] == 72.0

    def test_get_heart_rate_missing_api_key(self, client: TestClient, db: Session):
        """Test that request without API key is rejected."""
        # Arrange
        user = create_user(db)

        # Act
        response = client.get(f"/api/v1/users/{user.id}/heart-rate")

        # Assert
        assert response.status_code == 401

    def test_get_heart_rate_invalid_api_key(self, client: TestClient, db: Session):
        """Test that request with invalid API key is rejected."""
        # Arrange
        user = create_user(db)
        headers = api_key_headers("invalid-api-key")

        # Act
        response = client.get(f"/api/v1/users/{user.id}/heart-rate", headers=headers)

        # Assert
        assert response.status_code == 401

    def test_get_heart_rate_invalid_user_id(self, client: TestClient, db: Session):
        """Test handling of invalid user ID format."""
        # Arrange
        api_key = create_api_key(db)
        headers = api_key_headers(api_key.id)

        # Act
        response = client.get("/api/v1/users/not-a-uuid/heart-rate", headers=headers)

        # Assert
        assert response.status_code == 422

    def test_get_heart_rate_nonexistent_user(self, client: TestClient, db: Session):
        """Test retrieving heart rate data for a user that doesn't exist."""
        # Arrange
        from uuid import uuid4

        api_key = create_api_key(db)
        headers = api_key_headers(api_key.id)
        nonexistent_user_id = uuid4()

        # Act
        response = client.get(
            f"/api/v1/users/{nonexistent_user_id}/heart-rate", headers=headers
        )

        # Assert - should return empty list, not 404
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0

    def test_get_heart_rate_with_different_values(self, client: TestClient, db: Session):
        """Test retrieving heart rate data with various realistic values."""
        # Arrange
        user = create_user(db)
        mapping = create_external_device_mapping(db, user=user)
        values = [60.0, 72.5, 85.0, 95.5, 120.0, 145.0, 180.0]
        samples = [
            create_data_point_series(
                db,
                mapping=mapping,
                category="heart_rate",
                value=value,
            )
            for value in values
        ]
        api_key = create_api_key(db)
        headers = api_key_headers(api_key.id)

        # Act
        response = client.get(f"/api/v1/users/{user.id}/heart-rate", headers=headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == len(values)
        returned_values = {d["value"] for d in data}
        assert returned_values == set(values)
