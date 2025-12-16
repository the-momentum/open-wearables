"""
Tests for vendor workouts endpoints.

Tests the following endpoints:
- GET /api/v1/providers/{provider}/users/{user_id}/workouts
- GET /api/v1/providers/{provider}/users/{user_id}/workouts/{workout_id}
"""

import pytest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.tests.utils import (
    api_key_headers,
    create_api_key,
    create_user,
    create_user_connection,
)
from app.schemas.oauth import ConnectionStatus


class TestVendorWorkoutsEndpoints:
    """Test suite for vendor workout endpoints."""

    @pytest.fixture
    def mock_provider_factory(self):
        """Mock the ProviderFactory to avoid external API calls."""
        with patch("app.api.routes.v1.vendor_workouts.factory") as mock_factory:
            mock_strategy = MagicMock()
            mock_strategy.workouts.get_workouts_from_api.return_value = [
                {"id": "123", "type": "running", "duration": 3600},
                {"id": "456", "type": "cycling", "duration": 1800},
            ]
            mock_strategy.workouts.get_workout_detail_from_api.return_value = {
                "id": "123",
                "type": "running",
                "duration": 3600,
                "details": {"distance": 5000, "calories": 350},
            }
            mock_factory.get_provider.return_value = mock_strategy
            yield mock_factory

    def test_get_garmin_workouts_success(
        self, client: TestClient, db: Session, mock_provider_factory
    ):
        """Test successfully retrieving Garmin workouts with valid API key."""
        # Arrange
        user = create_user(db)
        api_key = create_api_key(db)
        create_user_connection(db, user=user, provider="garmin", status=ConnectionStatus.ACTIVE)

        # Act
        response = client.get(
            f"/api/v1/providers/garmin/users/{user.id}/workouts",
            headers={"X-Open-Wearables-API-Key": api_key.id},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["id"] == "123"
        assert data[0]["type"] == "running"
        mock_provider_factory.get_provider.assert_called_once_with("garmin")

    def test_get_garmin_workouts_unauthorized(self, client: TestClient, db: Session):
        """Test that missing API key returns 401."""
        # Arrange
        user = create_user(db)

        # Act
        response = client.get(f"/api/v1/providers/garmin/users/{user.id}/workouts")

        # Assert
        assert response.status_code == 401

    def test_get_garmin_workouts_no_connection(
        self, client: TestClient, db: Session, mock_provider_factory
    ):
        """Test retrieving workouts when user has no connection to provider."""
        # Arrange
        user = create_user(db)
        api_key = create_api_key(db)
        # No connection created for this user

        # Configure mock to raise HTTPException for no connection
        from fastapi import HTTPException
        mock_provider_factory.get_provider.return_value.workouts.get_workouts_from_api.side_effect = HTTPException(
            status_code=404, detail="No active connection found for user"
        )

        # Act
        response = client.get(
            f"/api/v1/providers/garmin/users/{user.id}/workouts",
            headers={"X-Open-Wearables-API-Key": api_key.id},
        )

        # Assert
        assert response.status_code == 404

    def test_get_polar_workouts_success(
        self, client: TestClient, db: Session, mock_provider_factory
    ):
        """Test successfully retrieving Polar workouts."""
        # Arrange
        user = create_user(db)
        api_key = create_api_key(db)
        create_user_connection(db, user=user, provider="polar", status=ConnectionStatus.ACTIVE)

        # Act
        response = client.get(
            f"/api/v1/providers/polar/users/{user.id}/workouts",
            headers={"X-Open-Wearables-API-Key": api_key.id},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        mock_provider_factory.get_provider.assert_called_once_with("polar")

    def test_get_polar_workouts_with_params(
        self, client: TestClient, db: Session, mock_provider_factory
    ):
        """Test Polar workouts with samples, zones, and route parameters."""
        # Arrange
        user = create_user(db)
        api_key = create_api_key(db)
        create_user_connection(db, user=user, provider="polar", status=ConnectionStatus.ACTIVE)

        # Act
        response = client.get(
            f"/api/v1/providers/polar/users/{user.id}/workouts",
            headers={"X-Open-Wearables-API-Key": api_key.id},
            params={"samples": True, "zones": True, "route": True},
        )

        # Assert
        assert response.status_code == 200
        # Verify the parameters were passed to the provider
        call_kwargs = mock_provider_factory.get_provider.return_value.workouts.get_workouts_from_api.call_args[1]
        assert call_kwargs["samples"] is True
        assert call_kwargs["zones"] is True
        assert call_kwargs["route"] is True

    def test_get_suunto_workouts_success(
        self, client: TestClient, db: Session, mock_provider_factory
    ):
        """Test successfully retrieving Suunto workouts."""
        # Arrange
        user = create_user(db)
        api_key = create_api_key(db)
        create_user_connection(db, user=user, provider="suunto", status=ConnectionStatus.ACTIVE)

        # Act
        response = client.get(
            f"/api/v1/providers/suunto/users/{user.id}/workouts",
            headers={"X-Open-Wearables-API-Key": api_key.id},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        mock_provider_factory.get_provider.assert_called_once_with("suunto")

    def test_get_suunto_workouts_pagination(
        self, client: TestClient, db: Session, mock_provider_factory
    ):
        """Test Suunto workouts with since, limit, and offset pagination parameters."""
        # Arrange
        user = create_user(db)
        api_key = create_api_key(db)
        create_user_connection(db, user=user, provider="suunto", status=ConnectionStatus.ACTIVE)

        # Act
        response = client.get(
            f"/api/v1/providers/suunto/users/{user.id}/workouts",
            headers={"X-Open-Wearables-API-Key": api_key.id},
            params={"since": 1609459200, "limit": 25, "offset": 10},
        )

        # Assert
        assert response.status_code == 200
        # Verify the pagination parameters were passed
        call_kwargs = mock_provider_factory.get_provider.return_value.workouts.get_workouts_from_api.call_args[1]
        assert call_kwargs["since"] == 1609459200
        assert call_kwargs["limit"] == 25
        assert call_kwargs["offset"] == 10

    def test_get_workout_detail_success(
        self, client: TestClient, db: Session, mock_provider_factory
    ):
        """Test successfully retrieving workout detail."""
        # Arrange
        user = create_user(db)
        api_key = create_api_key(db)
        workout_id = "123"
        create_user_connection(db, user=user, provider="garmin", status=ConnectionStatus.ACTIVE)

        # Act
        response = client.get(
            f"/api/v1/providers/garmin/users/{user.id}/workouts/{workout_id}",
            headers={"X-Open-Wearables-API-Key": api_key.id},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "123"
        assert data["type"] == "running"
        assert "details" in data
        mock_provider_factory.get_provider.return_value.workouts.get_workout_detail_from_api.assert_called_once()

    def test_get_workout_detail_not_found(
        self, client: TestClient, db: Session, mock_provider_factory
    ):
        """Test workout detail endpoint with nonexistent workout ID."""
        # Arrange
        user = create_user(db)
        api_key = create_api_key(db)
        workout_id = "nonexistent"
        create_user_connection(db, user=user, provider="garmin", status=ConnectionStatus.ACTIVE)

        # Configure mock to raise HTTPException for not found
        from fastapi import HTTPException
        mock_provider_factory.get_provider.return_value.workouts.get_workout_detail_from_api.side_effect = HTTPException(
            status_code=404, detail="Workout not found"
        )

        # Act
        response = client.get(
            f"/api/v1/providers/garmin/users/{user.id}/workouts/{workout_id}",
            headers={"X-Open-Wearables-API-Key": api_key.id},
        )

        # Assert
        assert response.status_code == 404

    def test_invalid_provider_returns_422(self, client: TestClient, db: Session):
        """Test that invalid provider enum value returns 422."""
        # Arrange
        user = create_user(db)
        api_key = create_api_key(db)

        # Act
        response = client.get(
            f"/api/v1/providers/invalid_provider/users/{user.id}/workouts",
            headers={"X-Open-Wearables-API-Key": api_key.id},
        )

        # Assert
        assert response.status_code == 422

    def test_provider_not_supporting_workouts(
        self, client: TestClient, db: Session
    ):
        """Test provider that doesn't support workouts returns 501."""
        # Arrange
        user = create_user(db)
        api_key = create_api_key(db)
        create_user_connection(db, user=user, provider="apple", status=ConnectionStatus.ACTIVE)

        # Mock factory to return a strategy without workouts
        with patch("app.api.routes.v1.vendor_workouts.factory") as mock_factory:
            mock_strategy = MagicMock()
            mock_strategy.workouts = None  # Apple has no cloud API
            mock_factory.get_provider.return_value = mock_strategy

            # Act
            response = client.get(
                f"/api/v1/providers/apple/users/{user.id}/workouts",
                headers={"X-Open-Wearables-API-Key": api_key.id},
            )

            # Assert
            assert response.status_code == 501
            assert "does not support workouts" in response.json()["detail"]
