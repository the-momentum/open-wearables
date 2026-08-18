"""
Tests for sync_vendor_data Celery task.

Tests synchronization of workout data from external providers (Garmin, Polar, Suunto).
"""

from unittest.mock import MagicMock, patch

from sqlalchemy.orm import Session

from app.integrations.celery.tasks.sync_vendor_data_task import sync_vendor_data
from app.schemas.auth import ConnectionStatus
from app.utils.sync_params import build_sync_params
from tests.factories import UserConnectionFactory, UserFactory


class TestSyncVendorDataTask:
    """Test suite for sync_vendor_data task."""

    @patch("app.integrations.celery.tasks.sync_vendor_data_task.SessionLocal")
    @patch("app.services.providers.factory.ProviderFactory.get_provider")
    def test_sync_vendor_data_success(
        self,
        mock_get_provider: MagicMock,
        mock_session_local: MagicMock,
        db: Session,
        mock_celery_app: MagicMock,
    ) -> None:
        """Test successful sync of vendor data."""
        # Arrange
        user = UserFactory()
        connection = UserConnectionFactory(
            user=user,
            provider="garmin",
            status=ConnectionStatus.ACTIVE,
        )

        # Mock the database session
        mock_session_local.return_value.__enter__.return_value = db
        mock_session_local.return_value.__exit__.return_value = None

        # Mock the provider strategy
        mock_workouts = MagicMock()
        mock_workouts.load_data.return_value = True

        mock_strategy = MagicMock()
        mock_strategy.capabilities.rest_pull = True
        mock_strategy.capabilities.webhook_stream = False
        mock_strategy.workouts = mock_workouts
        mock_get_provider.return_value = mock_strategy

        # Act
        result = sync_vendor_data(str(user.id))

        # Assert
        assert str(result["user_id"]) == str(user.id)
        assert "garmin" in result["providers_synced"]
        assert result["providers_synced"]["garmin"]["success"] is True
        assert result["errors"] == {}
        mock_workouts.load_data.assert_called_once()

        # Verify connection was updated
        db.refresh(connection)
        assert connection.last_synced_at is not None

    @patch("app.integrations.celery.tasks.sync_vendor_data_task.SessionLocal")
    @patch("app.services.providers.factory.ProviderFactory.get_provider")
    def test_sync_vendor_data_with_date_range(
        self,
        mock_get_provider: MagicMock,
        mock_session_local: MagicMock,
        db: Session,
        mock_celery_app: MagicMock,
    ) -> None:
        """Test sync with specific date range."""
        # Arrange
        user = UserFactory()
        UserConnectionFactory(
            user=user,
            provider="polar",
            status=ConnectionStatus.ACTIVE,
        )

        mock_session_local.return_value.__enter__.return_value = db
        mock_session_local.return_value.__exit__.return_value = None

        mock_workouts = MagicMock()
        mock_workouts.load_data.return_value = True

        mock_strategy = MagicMock()
        mock_strategy.capabilities.rest_pull = True
        mock_strategy.capabilities.webhook_stream = False
        mock_strategy.workouts = mock_workouts
        mock_get_provider.return_value = mock_strategy

        start_date = "2025-01-01T00:00:00Z"
        end_date = "2025-12-31T23:59:59Z"

        # Act
        result = sync_vendor_data(str(user.id), start_date=start_date, end_date=end_date)

        # Assert
        assert str(result["user_id"]) == str(user.id)
        assert result["start_date"] == start_date
        assert result["end_date"] == end_date
        assert "polar" in result["providers_synced"]
        mock_workouts.load_data.assert_called_once()

    @patch("app.integrations.celery.tasks.sync_vendor_data_task.SessionLocal")
    @patch("app.services.providers.factory.ProviderFactory.get_provider")
    def test_sync_vendor_data_multiple_providers(
        self,
        mock_get_provider: MagicMock,
        mock_session_local: MagicMock,
        db: Session,
        mock_celery_app: MagicMock,
    ) -> None:
        """Test sync with multiple provider connections."""
        # Arrange
        user = UserFactory()
        UserConnectionFactory(user=user, provider="garmin", status=ConnectionStatus.ACTIVE)
        UserConnectionFactory(user=user, provider="polar", status=ConnectionStatus.ACTIVE)
        UserConnectionFactory(user=user, provider="suunto", status=ConnectionStatus.ACTIVE)

        mock_session_local.return_value.__enter__.return_value = db
        mock_session_local.return_value.__exit__.return_value = None

        mock_workouts = MagicMock()
        mock_workouts.load_data.return_value = True

        mock_strategy = MagicMock()
        mock_strategy.capabilities.rest_pull = True
        mock_strategy.capabilities.webhook_stream = False
        mock_strategy.workouts = mock_workouts
        mock_get_provider.return_value = mock_strategy

        # Act
        result = sync_vendor_data(str(user.id))

        # Assert
        assert len(result["providers_synced"]) == 3
        assert "garmin" in result["providers_synced"]
        assert "polar" in result["providers_synced"]
        assert "suunto" in result["providers_synced"]
        assert mock_workouts.load_data.call_count == 3

    @patch("app.integrations.celery.tasks.sync_vendor_data_task.SessionLocal")
    @patch("app.services.providers.factory.ProviderFactory.get_provider")
    def test_sync_vendor_data_specific_providers_only(
        self,
        mock_get_provider: MagicMock,
        mock_session_local: MagicMock,
        db: Session,
        mock_celery_app: MagicMock,
    ) -> None:
        """Test sync with specific provider filter."""
        # Arrange
        user = UserFactory()
        UserConnectionFactory(user=user, provider="garmin", status=ConnectionStatus.ACTIVE)
        UserConnectionFactory(user=user, provider="polar", status=ConnectionStatus.ACTIVE)

        mock_session_local.return_value.__enter__.return_value = db
        mock_session_local.return_value.__exit__.return_value = None

        mock_workouts = MagicMock()
        mock_workouts.load_data.return_value = True

        mock_strategy = MagicMock()
        mock_strategy.capabilities.rest_pull = True
        mock_strategy.capabilities.webhook_stream = False
        mock_strategy.workouts = mock_workouts
        mock_get_provider.return_value = mock_strategy

        # Act - sync only Garmin
        result = sync_vendor_data(str(user.id), providers=["garmin"])

        # Assert
        assert len(result["providers_synced"]) == 1
        assert "garmin" in result["providers_synced"]
        assert "polar" not in result["providers_synced"]
        mock_workouts.load_data.assert_called_once()

    @patch("app.integrations.celery.tasks.sync_vendor_data_task.SessionLocal")
    def test_sync_vendor_data_no_active_connections(
        self,
        mock_session_local: MagicMock,
        db: Session,
        mock_celery_app: MagicMock,
    ) -> None:
        """Test sync when user has no active connections."""
        # Arrange
        user = UserFactory()
        # Create a disconnected connection
        UserConnectionFactory(
            user=user,
            provider="garmin",
            status=ConnectionStatus.REVOKED,
        )

        mock_session_local.return_value.__enter__.return_value = db
        mock_session_local.return_value.__exit__.return_value = None

        # Act
        result = sync_vendor_data(str(user.id))

        # Assert
        assert str(result["user_id"]) == str(user.id)
        assert result["providers_synced"] == {}
        assert result["message"] == "No active provider connections found"

    @patch("app.integrations.celery.tasks.sync_vendor_data_task.SessionLocal")
    @patch("app.services.providers.factory.ProviderFactory.get_provider")
    def test_sync_vendor_data_provider_error(
        self,
        mock_get_provider: MagicMock,
        mock_session_local: MagicMock,
        db: Session,
        mock_celery_app: MagicMock,
    ) -> None:
        """Test handling of provider API errors."""
        # Arrange
        user = UserFactory()
        UserConnectionFactory(user=user, provider="garmin", status=ConnectionStatus.ACTIVE)

        mock_session_local.return_value.__enter__.return_value = db
        mock_session_local.return_value.__exit__.return_value = None

        # Mock provider that fails during sync
        mock_workouts = MagicMock()
        mock_workouts.load_data.side_effect = Exception("Provider API unavailable")

        mock_strategy = MagicMock()
        mock_strategy.capabilities.rest_pull = True
        mock_strategy.capabilities.webhook_stream = False
        mock_strategy.workouts = mock_workouts
        mock_get_provider.return_value = mock_strategy

        # Act
        result = sync_vendor_data(str(user.id))

        # Assert
        assert str(result["user_id"]) == str(user.id)
        assert "garmin" in result["providers_synced"]
        assert result["providers_synced"]["garmin"]["params"]["workouts"]["success"] is False
        assert "Provider API unavailable" in result["providers_synced"]["garmin"]["params"]["workouts"]["error"]

    @patch("app.integrations.celery.tasks.sync_vendor_data_task.SessionLocal")
    @patch("app.services.providers.factory.ProviderFactory.get_provider")
    def test_sync_vendor_data_sync_returns_false(
        self,
        mock_get_provider: MagicMock,
        mock_session_local: MagicMock,
        db: Session,
        mock_celery_app: MagicMock,
    ) -> None:
        """Test handling when provider sync returns False."""
        # Arrange
        user = UserFactory()
        UserConnectionFactory(user=user, provider="polar", status=ConnectionStatus.ACTIVE)

        mock_session_local.return_value.__enter__.return_value = db
        mock_session_local.return_value.__exit__.return_value = None

        mock_workouts = MagicMock()
        mock_workouts.load_data.return_value = False

        mock_strategy = MagicMock()
        mock_strategy.capabilities.rest_pull = True
        mock_strategy.capabilities.webhook_stream = False
        mock_strategy.workouts = mock_workouts
        mock_get_provider.return_value = mock_strategy

        # Act
        result = sync_vendor_data(str(user.id))

        # Assert - provider is added to providers_synced with workouts success=False
        assert "polar" in result["providers_synced"]
        assert result["providers_synced"]["polar"]["params"]["workouts"]["success"] is False
        assert result["errors"] == {}

    @patch("app.integrations.celery.tasks.sync_vendor_data_task.SessionLocal")
    @patch("app.services.providers.factory.ProviderFactory.get_provider")
    def test_sync_vendor_data_workouts_not_supported(
        self,
        mock_get_provider: MagicMock,
        mock_session_local: MagicMock,
        db: Session,
        mock_celery_app: MagicMock,
    ) -> None:
        """Test handling when provider doesn't support workouts."""
        # Arrange
        user = UserFactory()
        UserConnectionFactory(user=user, provider="garmin", status=ConnectionStatus.ACTIVE)

        mock_session_local.return_value.__enter__.return_value = db
        mock_session_local.return_value.__exit__.return_value = None

        # Mock provider without workout support
        mock_strategy = MagicMock()
        mock_strategy.capabilities.rest_pull = True
        mock_strategy.capabilities.webhook_stream = False
        mock_strategy.workouts = None
        # Also ensure data_247 is not set so the strategy is still processed
        del mock_strategy.data_247
        mock_get_provider.return_value = mock_strategy

        # Act
        result = sync_vendor_data(str(user.id))

        # Assert - provider is added to providers_synced without workout params
        assert "garmin" in result["providers_synced"]
        assert "workouts" not in result["providers_synced"]["garmin"]["params"]
        assert result["errors"] == {}

    @patch("app.integrations.celery.tasks.sync_vendor_data_task.SessionLocal")
    @patch("app.services.providers.factory.ProviderFactory.get_provider")
    def test_sync_vendor_data_skips_push_based_provider(
        self,
        mock_get_provider: MagicMock,
        mock_session_local: MagicMock,
        db: Session,
        mock_celery_app: MagicMock,
    ) -> None:
        """Test that push-based providers (no cloud API) are filtered out entirely."""
        # Arrange
        user = UserFactory()
        UserConnectionFactory(user=user, provider="apple", status=ConnectionStatus.ACTIVE)

        mock_session_local.return_value.__enter__.return_value = db
        mock_session_local.return_value.__exit__.return_value = None

        mock_strategy = MagicMock()
        mock_strategy.capabilities.rest_pull = False
        mock_get_provider.return_value = mock_strategy

        # Act
        result = sync_vendor_data(str(user.id))

        # Assert - SDK provider is filtered out, never enters sync loop
        assert "apple" not in result["providers_synced"]
        assert result["errors"] == {}
        assert result["message"] == "No active provider connections found"

    def test_sync_vendor_data_invalid_user_id(self, mock_celery_app: MagicMock) -> None:
        """Test handling of invalid user ID format."""
        # Act
        result = sync_vendor_data("not-a-valid-uuid")

        # Assert
        assert result["user_id"] == "not-a-valid-uuid"
        assert "user_id" in result["errors"]
        assert "Invalid UUID format" in result["errors"]["user_id"]


class TestBuildSyncParams:
    """Test suite for build_sync_params helper function."""

    def test_build_sync_params_with_dates(self) -> None:
        """Both dates are passed through under the canonical keys."""
        start_date = "2025-01-01T00:00:00Z"
        end_date = "2025-12-31T23:59:59Z"

        params = build_sync_params(start_date, end_date)

        assert params == {"start_date": start_date, "end_date": end_date}

    def test_build_sync_params_no_dates(self) -> None:
        """None in, None out - no provider-specific keys are invented."""
        params = build_sync_params(None, None)

        assert params == {"start_date": None, "end_date": None}

    def test_build_sync_params_invalid_date_format(self) -> None:
        """An unparseable date is passed through as-is, not dropped or raised."""
        params = build_sync_params("invalid-date", "2025-12-31T23:59:59Z")

        assert params == {"start_date": "invalid-date", "end_date": "2025-12-31T23:59:59Z"}
