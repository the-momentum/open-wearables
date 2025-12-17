"""
Tests for sync data endpoint.

Tests the following endpoint:
- POST /api/v1/providers/{provider}/users/{user_id}/sync
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.schemas.oauth import ConnectionStatus
from app.tests.utils import (
    create_api_key,
    create_user,
    create_user_connection,
)


class TestSyncDataEndpoint:
    """Test suite for sync data endpoint."""

    @pytest.fixture
    def mock_provider_factory(self) -> MagicMock:
        """Mock the ProviderFactory to avoid external API calls."""
        with patch("app.api.routes.v1.sync_data.factory") as mock_factory:
            mock_strategy = MagicMock()
            mock_strategy.workouts.load_data.return_value = True
            mock_factory.get_provider.return_value = mock_strategy
            yield mock_factory

    def test_sync_garmin_success(self, client: TestClient, db: Session, mock_provider_factory: MagicMock) -> None:
        """Test successfully syncing Garmin data."""
        # Arrange
        user = create_user(db)
        api_key = create_api_key(db)
        create_user_connection(db, user=user, provider="garmin", status=ConnectionStatus.ACTIVE)

        # Act
        response = client.post(
            f"/api/v1/providers/garmin/users/{user.id}/sync",
            headers={"X-Open-Wearables-API-Key": api_key.id},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data == {"success": True}
        mock_provider_factory.get_provider.assert_called_once_with("garmin")
        mock_provider_factory.get_provider.return_value.workouts.load_data.assert_called_once()

    def test_sync_garmin_unauthorized(self, client: TestClient, db: Session) -> None:
        """Test that missing API key returns 401."""
        # Arrange
        user = create_user(db)

        # Act
        response = client.post(f"/api/v1/providers/garmin/users/{user.id}/sync")

        # Assert
        assert response.status_code == 401

    def test_sync_garmin_no_connection(self, client: TestClient, db: Session, mock_provider_factory: MagicMock) -> None:
        """Test syncing when user has no connection to provider."""
        # Arrange
        user = create_user(db)
        api_key = create_api_key(db)
        # No connection created for this user

        # Configure mock to raise HTTPException for no connection
        from fastapi import HTTPException

        mock_provider_factory.get_provider.return_value.workouts.load_data.side_effect = HTTPException(
            status_code=404,
            detail="No active connection found for user",
        )

        # Act
        response = client.post(
            f"/api/v1/providers/garmin/users/{user.id}/sync",
            headers={"X-Open-Wearables-API-Key": api_key.id},
        )

        # Assert
        assert response.status_code == 404

    def test_sync_polar_success(self, client: TestClient, db: Session, mock_provider_factory: MagicMock) -> None:
        """Test successfully syncing Polar data."""
        # Arrange
        user = create_user(db)
        api_key = create_api_key(db)
        create_user_connection(db, user=user, provider="polar", status=ConnectionStatus.ACTIVE)

        # Act
        response = client.post(
            f"/api/v1/providers/polar/users/{user.id}/sync",
            headers={"X-Open-Wearables-API-Key": api_key.id},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data == {"success": True}
        mock_provider_factory.get_provider.assert_called_once_with("polar")

    def test_sync_suunto_with_params(self, client: TestClient, db: Session, mock_provider_factory: MagicMock) -> None:
        """Test Suunto sync with since, limit, and offset parameters."""
        # Arrange
        user = create_user(db)
        api_key = create_api_key(db)
        create_user_connection(db, user=user, provider="suunto", status=ConnectionStatus.ACTIVE)

        # Act
        response = client.post(
            f"/api/v1/providers/suunto/users/{user.id}/sync",
            headers={"X-Open-Wearables-API-Key": api_key.id},
            params={"since": 1609459200, "limit": 25, "offset": 10},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data == {"success": True}

        # Verify the pagination parameters were passed
        call_kwargs = mock_provider_factory.get_provider.return_value.workouts.load_data.call_args[1]
        assert call_kwargs["since"] == 1609459200
        assert call_kwargs["limit"] == 25
        assert call_kwargs["offset"] == 10

    def test_sync_invalid_provider(self, client: TestClient, db: Session) -> None:
        """Test that invalid provider enum value returns 400."""
        # Arrange
        user = create_user(db)
        api_key = create_api_key(db)

        # Act
        response = client.post(
            f"/api/v1/providers/invalid_provider/users/{user.id}/sync",
            headers={"X-Open-Wearables-API-Key": api_key.id},
        )

        # Assert
        assert response.status_code == 400

    def test_sync_provider_not_supporting_workouts(self, client: TestClient, db: Session) -> None:
        """Test provider that doesn't support workouts returns 501."""
        # Arrange
        user = create_user(db)
        api_key = create_api_key(db)
        create_user_connection(db, user=user, provider="apple", status=ConnectionStatus.ACTIVE)

        # Mock factory to return a strategy without workouts
        with patch("app.api.routes.v1.sync_data.factory") as mock_factory:
            mock_strategy = MagicMock()
            mock_strategy.workouts = None  # Apple has no cloud API
            mock_factory.get_provider.return_value = mock_strategy

            # Act
            response = client.post(
                f"/api/v1/providers/apple/users/{user.id}/sync",
                headers={"X-Open-Wearables-API-Key": api_key.id},
            )

            # Assert
            assert response.status_code == 501
            assert "does not support workouts" in response.json()["detail"]
