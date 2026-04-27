"""
Tests for sync data endpoints.

Tests the following endpoints:
- POST /api/v1/providers/{provider}/users/{user_id}/sync
- POST /api/v1/providers/{provider}/users/{user_id}/sync/historical
"""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.schemas.auth import ConnectionStatus
from app.services.providers.base_strategy import HistoricalSyncResult
from app.utils.exceptions import UnsupportedProviderError
from tests.factories import ApiKeyFactory, UserConnectionFactory, UserFactory


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


class TestSyncHistoricalEndpoint:
    """Test suite for POST /api/v1/providers/{provider}/users/{user_id}/sync/historical."""

    @pytest.fixture
    def mock_provider_factory(self) -> Generator[MagicMock, None, None]:
        """Mock the ProviderFactory used by the sync_data router."""
        with patch("app.api.routes.v1.sync_data.factory") as mock_factory:
            yield mock_factory

    def test_historical_sync_delegates_to_strategy(
        self, client: TestClient, db: Session, mock_provider_factory: MagicMock
    ) -> None:
        """Endpoint should delegate to strategy.start_historical_sync()."""
        user = UserFactory()
        api_key = ApiKeyFactory()

        mock_strategy = MagicMock()
        mock_strategy.start_historical_sync.return_value = HistoricalSyncResult(
            task_id="task-abc",
            method="pull_api",
            message="Historical sync queued for 90 days of oura data.",
            days=90,
            start_date="2026-01-09T00:00:00+00:00",
            end_date="2026-04-09T00:00:00+00:00",
        )
        mock_provider_factory.get_provider.return_value = mock_strategy

        response = client.post(
            f"/api/v1/providers/oura/users/{user.id}/sync/historical",
            headers={"X-Open-Wearables-API-Key": api_key.id},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["provider"] == "oura"
        assert data["task_id"] == "task-abc"
        assert data["method"] == "pull_api"
        mock_strategy.start_historical_sync.assert_called_once_with(user.id, 90)

    def test_historical_sync_passes_days_param(
        self, client: TestClient, db: Session, mock_provider_factory: MagicMock
    ) -> None:
        """Custom days parameter should be forwarded to strategy."""
        user = UserFactory()
        api_key = ApiKeyFactory()

        mock_strategy = MagicMock()
        mock_strategy.start_historical_sync.return_value = HistoricalSyncResult(
            task_id="task-xyz",
            method="pull_api",
            message="Queued",
            days=30,
        )
        mock_provider_factory.get_provider.return_value = mock_strategy

        response = client.post(
            f"/api/v1/providers/oura/users/{user.id}/sync/historical",
            headers={"X-Open-Wearables-API-Key": api_key.id},
            params={"days": 30},
        )

        assert response.status_code == 200
        mock_strategy.start_historical_sync.assert_called_once_with(user.id, 30)

    def test_historical_sync_not_implemented_returns_400(
        self, client: TestClient, db: Session, mock_provider_factory: MagicMock
    ) -> None:
        """Provider that doesn't support historical sync should return 400."""
        user = UserFactory()
        api_key = ApiKeyFactory()

        mock_strategy = MagicMock()
        mock_strategy.start_historical_sync.side_effect = UnsupportedProviderError("apple", "historical sync")
        mock_provider_factory.get_provider.return_value = mock_strategy

        response = client.post(
            f"/api/v1/providers/apple/users/{user.id}/sync/historical",
            headers={"X-Open-Wearables-API-Key": api_key.id},
        )

        assert response.status_code == 400
        assert "does not support" in response.json()["detail"]

    def test_historical_sync_unauthorized(self, client: TestClient, db: Session) -> None:
        """Missing API key should return 401."""
        user = UserFactory()

        response = client.post(f"/api/v1/providers/oura/users/{user.id}/sync/historical")

        assert response.status_code == 401
