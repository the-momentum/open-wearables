"""
Tests for sync_vendor_data Celery task.

Tests synchronization of workout data from external providers (Garmin, Polar, Suunto).
"""

from unittest.mock import MagicMock, patch

from sqlalchemy.orm import Session

from app.integrations.celery.tasks.sync_vendor_data_task import (
    _build_sync_params,
    sync_vendor_data,
)
from app.schemas import ConnectionStatus
from app.tests.utils.factories import (
    create_user,
    create_user_connection,
)


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
        user = create_user(db)
        connection = create_user_connection(
            db,
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
        user = create_user(db)
        create_user_connection(
            db,
            user=user,
            provider="polar",
            status=ConnectionStatus.ACTIVE,
        )

        mock_session_local.return_value.__enter__.return_value = db
        mock_session_local.return_value.__exit__.return_value = None

        mock_workouts = MagicMock()
        mock_workouts.load_data.return_value = True

        mock_strategy = MagicMock()
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
        user = create_user(db)
        create_user_connection(db, user=user, provider="garmin", status=ConnectionStatus.ACTIVE)
        create_user_connection(db, user=user, provider="polar", status=ConnectionStatus.ACTIVE)
        create_user_connection(db, user=user, provider="suunto", status=ConnectionStatus.ACTIVE)

        mock_session_local.return_value.__enter__.return_value = db
        mock_session_local.return_value.__exit__.return_value = None

        mock_workouts = MagicMock()
        mock_workouts.load_data.return_value = True

        mock_strategy = MagicMock()
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
        user = create_user(db)
        create_user_connection(db, user=user, provider="garmin", status=ConnectionStatus.ACTIVE)
        create_user_connection(db, user=user, provider="polar", status=ConnectionStatus.ACTIVE)

        mock_session_local.return_value.__enter__.return_value = db
        mock_session_local.return_value.__exit__.return_value = None

        mock_workouts = MagicMock()
        mock_workouts.load_data.return_value = True

        mock_strategy = MagicMock()
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
        user = create_user(db)
        # Create a disconnected connection
        create_user_connection(
            db,
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
        user = create_user(db)
        create_user_connection(db, user=user, provider="garmin", status=ConnectionStatus.ACTIVE)

        mock_session_local.return_value.__enter__.return_value = db
        mock_session_local.return_value.__exit__.return_value = None

        # Mock provider to raise an error
        mock_get_provider.side_effect = Exception("Provider API unavailable")

        # Act
        result = sync_vendor_data(str(user.id))

        # Assert
        assert str(result["user_id"]) == str(user.id)
        assert "garmin" in result["errors"]
        assert "Provider API unavailable" in result["errors"]["garmin"]
        assert result["providers_synced"] == {}

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
        user = create_user(db)
        create_user_connection(db, user=user, provider="polar", status=ConnectionStatus.ACTIVE)

        mock_session_local.return_value.__enter__.return_value = db
        mock_session_local.return_value.__exit__.return_value = None

        mock_workouts = MagicMock()
        mock_workouts.load_data.return_value = False

        mock_strategy = MagicMock()
        mock_strategy.workouts = mock_workouts
        mock_get_provider.return_value = mock_strategy

        # Act
        result = sync_vendor_data(str(user.id))

        # Assert
        assert "polar" in result["errors"]
        assert result["errors"]["polar"] == "Sync returned False"
        assert result["providers_synced"] == {}

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
        user = create_user(db)
        create_user_connection(db, user=user, provider="garmin", status=ConnectionStatus.ACTIVE)

        mock_session_local.return_value.__enter__.return_value = db
        mock_session_local.return_value.__exit__.return_value = None

        # Mock provider without workout support
        mock_strategy = MagicMock()
        mock_strategy.workouts = None
        mock_get_provider.return_value = mock_strategy

        # Act
        result = sync_vendor_data(str(user.id))

        # Assert
        assert "garmin" in result["errors"]
        assert result["errors"]["garmin"] == "Workouts not supported"
        assert result["providers_synced"] == {}

    def test_sync_vendor_data_invalid_user_id(self, mock_celery_app: MagicMock) -> None:
        """Test handling of invalid user ID format."""
        # Act
        result = sync_vendor_data("not-a-valid-uuid")

        # Assert
        assert result["user_id"] == "not-a-valid-uuid"
        assert "user_id" in result["errors"]
        assert "Invalid UUID format" in result["errors"]["user_id"]


class TestBuildSyncParams:
    """Test suite for _build_sync_params helper function."""

    def test_build_sync_params_suunto(self) -> None:
        """Test building Suunto-specific parameters."""
        # Arrange
        start_date = "2025-01-01T00:00:00Z"
        end_date = "2025-12-31T23:59:59Z"

        # Act
        params = _build_sync_params("suunto", start_date, end_date)

        # Assert - Suunto uses generic params (since/until timestamps)
        assert "since" in params
        assert "until" in params
        assert isinstance(params["since"], int)
        assert isinstance(params["until"], int)
        assert params["start_date"] == start_date
        assert params["end_date"] == end_date

    def test_build_sync_params_polar(self) -> None:
        """Test building Polar-specific parameters."""
        # Arrange
        start_date = "2025-01-01T00:00:00Z"
        end_date = "2025-12-31T23:59:59Z"

        # Act
        params = _build_sync_params("polar", start_date, end_date)

        # Assert
        assert params["samples"] is False
        assert params["zones"] is False
        assert params["route"] is False

    def test_build_sync_params_garmin(self) -> None:
        """Test building Garmin-specific parameters."""
        # Arrange
        start_date = "2025-01-01T00:00:00Z"
        end_date = "2025-12-31T23:59:59Z"

        # Act
        params = _build_sync_params("garmin", start_date, end_date)

        # Assert
        assert params["summary_start_time"] == start_date
        assert params["summary_end_time"] == end_date

    def test_build_sync_params_no_dates(self) -> None:
        """Test building parameters without date range."""
        # Act
        params = _build_sync_params("garmin", None, None)

        # Assert
        assert "summary_start_time" not in params
        assert "summary_end_time" not in params

    def test_build_sync_params_suunto_no_start_date(self) -> None:
        """Test Suunto parameters without start date has no since/until."""
        # Act
        params = _build_sync_params("suunto", None, None)

        # Assert - when no dates provided, since/until are not set
        assert "since" not in params
        assert "until" not in params
        assert params["start_date"] is None
        assert params["end_date"] is None

    def test_build_sync_params_invalid_date_format(self) -> None:
        """Test handling of invalid date formats."""
        # Act
        params = _build_sync_params("garmin", "invalid-date", "2025-12-31T23:59:59Z")

        # Assert - should not raise error, just skip invalid date
        assert "summary_end_time" in params
        # Invalid start date should be skipped
        assert params.get("summary_start_time") is None or params["summary_start_time"] == "invalid-date"
