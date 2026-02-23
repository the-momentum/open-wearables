"""
Tests for sync data endpoint.

Tests the following endpoint:
- POST /api/v1/providers/{provider}/users/{user_id}/sync
"""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.schemas.oauth import ConnectionStatus
from _tests.factories import ApiKeyFactory, UserConnectionFactory, UserFactory


class TestSyncDataEndpoint:
    """Test suite for sync data endpoint."""

    @pytest.fixture
    def mock_provider_factory(self) -> Generator[MagicMock, None, None]:
        """Mock the ProviderFactory to avoid external API calls."""
        with patch("app.api.routes.v1.sync_data.factory") as mock_factory:
            mock_strategy = MagicMock()
            mock_strategy.workouts.load_data.return_value = True
            mock_factory.get_provider.return_value = mock_strategy
            yield mock_factory

    def test_sync_garmin_success(self, client: TestClient, db: Session, mock_provider_factory: MagicMock) -> None:
        """Test successfully syncing Garmin data (synchronous mode)."""
        # Arrange
        user = UserFactory()
        api_key = ApiKeyFactory()
        UserConnectionFactory(user=user, provider="garmin", status=ConnectionStatus.ACTIVE)

        # Act - use async=false to test synchronous path
        response = client.post(
            f"/api/v1/providers/garmin/users/{user.id}/sync",
            headers={"X-Open-Wearables-API-Key": api_key.id},
            params={"async": "false"},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        mock_provider_factory.get_provider.assert_called_once_with("garmin")
        mock_provider_factory.get_provider.return_value.workouts.load_data.assert_called_once()

    @patch("app.api.routes.v1.sync_data.sync_vendor_data")
    def test_sync_garmin_async_mode(
        self,
        mock_celery_task: MagicMock,
        client: TestClient,
        db: Session,
    ) -> None:
        """Test async sync dispatches to Celery task."""
        # Arrange
        user = UserFactory()
        api_key = ApiKeyFactory()
        UserConnectionFactory(user=user, provider="garmin", status=ConnectionStatus.ACTIVE)

        # Configure mock task
        mock_task = MagicMock()
        mock_task.id = "test-task-id-123"
        mock_celery_task.delay.return_value = mock_task

        # Act - async=true is default
        response = client.post(
            f"/api/v1/providers/garmin/users/{user.id}/sync",
            headers={"X-Open-Wearables-API-Key": api_key.id},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["async"] is True
        assert data["task_id"] == "test-task-id-123"

        # Verify Celery task was dispatched
        mock_celery_task.delay.assert_called_once()
        call_kwargs = mock_celery_task.delay.call_args[1]
        assert call_kwargs["providers"] == ["garmin"]
        assert call_kwargs["user_id"] == str(user.id)

    def test_sync_garmin_unauthorized(self, client: TestClient, db: Session) -> None:
        """Test that missing API key returns 401."""
        # Arrange
        user = UserFactory()

        # Act
        response = client.post(f"/api/v1/providers/garmin/users/{user.id}/sync")

        # Assert
        assert response.status_code == 401

    def test_sync_garmin_no_connection(self, client: TestClient, db: Session, mock_provider_factory: MagicMock) -> None:
        """Test syncing when user has no connection to provider (synchronous mode)."""
        # Arrange
        user = UserFactory()
        api_key = ApiKeyFactory()
        # No connection created for this user

        # Configure mock to raise HTTPException for no connection
        from fastapi import HTTPException

        mock_provider_factory.get_provider.return_value.workouts.load_data.side_effect = HTTPException(
            status_code=404,
            detail="No active connection found for user",
        )

        # Act - use async=false to test synchronous path
        response = client.post(
            f"/api/v1/providers/garmin/users/{user.id}/sync",
            headers={"X-Open-Wearables-API-Key": api_key.id},
            params={"async": "false"},
        )

        # Assert
        assert response.status_code == 404

    def test_sync_polar_success(self, client: TestClient, db: Session, mock_provider_factory: MagicMock) -> None:
        """Test successfully syncing Polar data (synchronous mode)."""
        # Arrange
        user = UserFactory()
        api_key = ApiKeyFactory()
        UserConnectionFactory(user=user, provider="polar", status=ConnectionStatus.ACTIVE)

        # Act - use async=false to test synchronous path
        response = client.post(
            f"/api/v1/providers/polar/users/{user.id}/sync",
            headers={"X-Open-Wearables-API-Key": api_key.id},
            params={"async": "false"},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        mock_provider_factory.get_provider.assert_called_once_with("polar")

    def test_sync_suunto_with_params(self, client: TestClient, db: Session, mock_provider_factory: MagicMock) -> None:
        """Test Suunto sync with since, limit, and offset parameters (synchronous mode)."""
        # Arrange
        user = UserFactory()
        api_key = ApiKeyFactory()
        UserConnectionFactory(user=user, provider="suunto", status=ConnectionStatus.ACTIVE)

        # Act - use async=false to test synchronous path with params
        response = client.post(
            f"/api/v1/providers/suunto/users/{user.id}/sync",
            headers={"X-Open-Wearables-API-Key": api_key.id},
            params={"since": 1609459200, "limit": 25, "offset": 10, "async": "false"},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Verify the pagination parameters were passed
        call_kwargs = mock_provider_factory.get_provider.return_value.workouts.load_data.call_args[1]
        assert call_kwargs["since"] == 1609459200
        assert call_kwargs["limit"] == 25
        assert call_kwargs["offset"] == 10

    def test_sync_invalid_provider(self, client: TestClient, db: Session) -> None:
        """Test that invalid provider enum value returns 400."""
        # Arrange
        user = UserFactory()
        api_key = ApiKeyFactory()

        # Act
        response = client.post(
            f"/api/v1/providers/invalid_provider/users/{user.id}/sync",
            headers={"X-Open-Wearables-API-Key": api_key.id},
        )

        # Assert
        assert response.status_code == 400

    def test_sync_provider_not_supporting_workouts(
        self,
        client: TestClient,
        db: Session,
        mock_provider_factory: MagicMock,
    ) -> None:
        """Test provider that doesn't support workouts returns 501 (synchronous mode)."""
        # Arrange
        user = UserFactory()
        api_key = ApiKeyFactory()
        UserConnectionFactory(user=user, provider="apple", status=ConnectionStatus.ACTIVE)

        # Configure mock to return a strategy without workouts
        mock_strategy = MagicMock()
        mock_strategy.workouts = None
        mock_provider_factory.get_provider.return_value = mock_strategy

        # Act - explicitly request only workouts to trigger 501 (use async=false)
        response = client.post(
            f"/api/v1/providers/apple/users/{user.id}/sync",
            headers={"X-Open-Wearables-API-Key": api_key.id},
            params={"data_type": "workouts", "async": "false"},
        )

        # Assert
        assert response.status_code == 501
        assert "does not support workouts" in response.json()["detail"]
