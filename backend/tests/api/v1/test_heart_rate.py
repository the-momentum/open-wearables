"""
Tests for heart rate endpoints.

Tests the /api/v1/users/{user_id}/heart-rate endpoint including:
- Get heart rate data with filtering
- Pagination and sorting
- Authentication and authorization
- Error cases
"""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.factories import (
    ApiKeyFactory,
    DataPointSeriesFactory,
    ExternalDeviceMappingFactory,
    SeriesTypeDefinitionFactory,
    UserFactory,
)
from tests.utils import api_key_headers


class TestHeartRateEndpoints:
    """Test suite for heart rate endpoints."""

    def test_get_heart_rate_success(self, client: TestClient, db: Session) -> None:
        """Test successfully retrieving heart rate data for a user."""
        # Arrange
        user = UserFactory()
        mapping = ExternalDeviceMappingFactory(user=user, device_id="device1")
        series_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate()
        hr1 = DataPointSeriesFactory(
            mapping=mapping,
            series_type=series_type,
            value=72.0,
        )
        hr2 = DataPointSeriesFactory(
            mapping=mapping,
            series_type=series_type,
            value=85.0,
        )
        api_key = ApiKeyFactory()
        headers = api_key_headers(api_key.id)

        # Act - device_id is required to get non-empty results
        response = client.get(f"/api/v1/users/{user.id}/heart-rate", headers=headers, params={"device_id": "device1"})

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert any(d["id"] == str(hr1.id) for d in data)
        assert any(d["id"] == str(hr2.id) for d in data)

    def test_get_heart_rate_empty_list(self, client: TestClient, db: Session) -> None:
        """Test retrieving heart rate data for a user with no data."""
        # Arrange
        user = UserFactory()
        api_key = ApiKeyFactory()
        headers = api_key_headers(api_key.id)

        # Act
        response = client.get(f"/api/v1/users/{user.id}/heart-rate", headers=headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0

    def test_get_heart_rate_filters_by_timestamp(self, client: TestClient, db: Session) -> None:
        """Test filtering heart rate data by timestamp."""
        # Arrange
        user = UserFactory()
        mapping = ExternalDeviceMappingFactory(user=user, device_id="device1")
        now = datetime.now(timezone.utc)
        DataPointSeriesFactory(
            mapping=mapping,
            value=70.0,
            recorded_at=now - timedelta(days=10),
        )
        recent_hr = DataPointSeriesFactory(
            mapping=mapping,
            value=75.0,
            recorded_at=now - timedelta(days=2),
        )
        api_key = ApiKeyFactory()
        headers = api_key_headers(api_key.id)

        # Act - filter for last 5 days (device_id required)
        start_time = (now - timedelta(days=5)).isoformat()
        response = client.get(
            f"/api/v1/users/{user.id}/heart-rate",
            headers=headers,
            params={"start_datetime": start_time, "device_id": "device1"},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == str(recent_hr.id)

    def test_get_heart_rate_filters_by_date_range(self, client: TestClient, db: Session) -> None:
        """Test filtering heart rate data with both start and end datetime."""
        # Arrange
        user = UserFactory()
        mapping = ExternalDeviceMappingFactory(user=user, device_id="device1")
        now = datetime.now(timezone.utc)
        DataPointSeriesFactory(
            mapping=mapping,
            value=70.0,
            recorded_at=now - timedelta(days=10),
        )
        in_range = DataPointSeriesFactory(
            mapping=mapping,
            value=75.0,
            recorded_at=now - timedelta(days=5),
        )
        DataPointSeriesFactory(
            mapping=mapping,
            value=80.0,
            recorded_at=now,
        )
        api_key = ApiKeyFactory()
        headers = api_key_headers(api_key.id)

        # Act - filter for 7-3 days ago
        start_time = (now - timedelta(days=7)).isoformat()
        end_time = (now - timedelta(days=3)).isoformat()
        response = client.get(
            f"/api/v1/users/{user.id}/heart-rate",
            headers=headers,
            params={"start_datetime": start_time, "end_datetime": end_time, "device_id": "device1"},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == str(in_range.id)

    def test_get_heart_rate_pagination(self, client: TestClient, db: Session) -> None:
        """Test that API returns all records (no pagination support)."""
        # Arrange
        user = UserFactory()
        mapping = ExternalDeviceMappingFactory(user=user, device_id="device1")
        # Create 10 heart rate samples
        [
            DataPointSeriesFactory(
                mapping=mapping,
                value=70.0 + i,
            )
            for i in range(10)
        ]
        api_key = ApiKeyFactory()
        headers = api_key_headers(api_key.id)

        # Act - API doesn't support skip/limit, returns all records
        response = client.get(
            f"/api/v1/users/{user.id}/heart-rate",
            headers=headers,
            params={"device_id": "device1"},
        )

        # Assert - returns all 10 records
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 10

    def test_get_heart_rate_sorting(self, client: TestClient, db: Session) -> None:
        """Test sorting heart rate data by timestamp."""
        # Arrange
        user = UserFactory()
        mapping = ExternalDeviceMappingFactory(user=user, device_id="device1")
        now = datetime.now(timezone.utc)
        hr1 = DataPointSeriesFactory(
            mapping=mapping,
            value=70.0,
            recorded_at=now - timedelta(hours=2),
        )
        hr2 = DataPointSeriesFactory(
            mapping=mapping,
            value=75.0,
            recorded_at=now - timedelta(hours=1),
        )
        hr3 = DataPointSeriesFactory(
            mapping=mapping,
            value=80.0,
            recorded_at=now,
        )
        api_key = ApiKeyFactory()
        headers = api_key_headers(api_key.id)

        # Act - API returns data sorted by timestamp descending (most recent first)
        response = client.get(
            f"/api/v1/users/{user.id}/heart-rate",
            headers=headers,
            params={"device_id": "device1"},
        )

        # Assert - data should be sorted descending by default (hr3, hr2, hr1)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        assert data[0]["id"] == str(hr3.id)
        assert data[1]["id"] == str(hr2.id)
        assert data[2]["id"] == str(hr1.id)

    def test_get_heart_rate_user_isolation(self, client: TestClient, db: Session) -> None:
        """Test that users can only see their own heart rate data."""
        # Arrange
        user1 = UserFactory()
        user2 = UserFactory()
        mapping1 = ExternalDeviceMappingFactory(user=user1, device_id="device1")
        mapping2 = ExternalDeviceMappingFactory(user=user2, device_id="device2")
        series_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate()
        hr1 = DataPointSeriesFactory(mapping=mapping1, series_type=series_type, value=70.0)
        DataPointSeriesFactory(mapping=mapping2, series_type=series_type, value=75.0)
        api_key = ApiKeyFactory()
        headers = api_key_headers(api_key.id)

        # Act - get user1's heart rate data
        response = client.get(f"/api/v1/users/{user1.id}/heart-rate", headers=headers, params={"device_id": "device1"})

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == str(hr1.id)

    def test_get_heart_rate_filters_by_provider(self, client: TestClient, db: Session) -> None:
        """Test filtering heart rate data by provider."""
        # Arrange
        user = UserFactory()
        apple_mapping = ExternalDeviceMappingFactory(user=user, provider_id="apple", device_id="apple_device")
        garmin_mapping = ExternalDeviceMappingFactory(user=user, provider_id="garmin", device_id="garmin_device")
        series_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate()
        apple_hr = DataPointSeriesFactory(mapping=apple_mapping, series_type=series_type, value=70.0)
        DataPointSeriesFactory(mapping=garmin_mapping, series_type=series_type, value=75.0)
        api_key = ApiKeyFactory()
        headers = api_key_headers(api_key.id)

        # Act
        response = client.get(
            f"/api/v1/users/{user.id}/heart-rate",
            headers=headers,
            params={"provider_id": "apple", "device_id": "apple_device"},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == str(apple_hr.id)

    def test_get_heart_rate_response_structure(self, client: TestClient, db: Session) -> None:
        """Test that response contains all expected fields."""
        # Arrange
        user = UserFactory()
        mapping = ExternalDeviceMappingFactory(user=user, device_id="device1")
        DataPointSeriesFactory(
            mapping=mapping,
            value=72.0,
            recorded_at=datetime.now(timezone.utc),
        )
        api_key = ApiKeyFactory()
        headers = api_key_headers(api_key.id)

        # Act
        response = client.get(f"/api/v1/users/{user.id}/heart-rate", headers=headers, params={"device_id": "device1"})

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        hr_data = data[0]

        # Verify essential fields are present
        assert "id" in hr_data
        assert "series_type" in hr_data
        assert "value" in hr_data
        assert "recorded_at" in hr_data
        assert hr_data["series_type"] == "heart_rate"
        assert float(hr_data["value"]) == 72.0

    def test_get_heart_rate_missing_api_key(self, client: TestClient, db: Session) -> None:
        """Test that request without API key is rejected."""
        # Arrange
        user = UserFactory()

        # Act
        response = client.get(f"/api/v1/users/{user.id}/heart-rate")

        # Assert
        assert response.status_code == 401

    def test_get_heart_rate_invalid_api_key(self, client: TestClient, db: Session) -> None:
        """Test that request with invalid API key is rejected."""
        # Arrange
        user = UserFactory()
        headers = api_key_headers("invalid-api-key")

        # Act
        response = client.get(f"/api/v1/users/{user.id}/heart-rate", headers=headers)

        # Assert
        assert response.status_code == 401

    def test_get_heart_rate_invalid_user_id(self, client: TestClient, db: Session) -> None:
        """Test handling of invalid user ID format raises ValueError."""
        # Arrange
        import pytest

        api_key = ApiKeyFactory()
        headers = api_key_headers(api_key.id)

        # Act & Assert - Invalid UUID causes ValueError with message from UUID parsing
        with pytest.raises(ValueError, match="badly formed hexadecimal UUID string"):
            client.get("/api/v1/users/not-a-uuid/heart-rate", headers=headers)

    def test_get_heart_rate_nonexistent_user(self, client: TestClient, db: Session) -> None:
        """Test retrieving heart rate data for a user that doesn't exist."""
        # Arrange
        from uuid import uuid4

        api_key = ApiKeyFactory()
        headers = api_key_headers(api_key.id)
        nonexistent_user_id = uuid4()

        # Act
        response = client.get(f"/api/v1/users/{nonexistent_user_id}/heart-rate", headers=headers)

        # Assert - should return empty list, not 404
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0

    def test_get_heart_rate_with_different_values(self, client: TestClient, db: Session) -> None:
        """Test retrieving heart rate data with various realistic values."""
        # Arrange
        user = UserFactory()
        mapping = ExternalDeviceMappingFactory(user=user, device_id="device1")
        values = [60.0, 72.5, 85.0, 95.5, 120.0, 145.0, 180.0]
        [
            DataPointSeriesFactory(
                mapping=mapping,
                value=value,
            )
            for value in values
        ]
        api_key = ApiKeyFactory()
        headers = api_key_headers(api_key.id)

        # Act
        response = client.get(f"/api/v1/users/{user.id}/heart-rate", headers=headers, params={"device_id": "device1"})

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == len(values)
        returned_values = {float(d["value"]) for d in data}
        assert returned_values == set(values)
