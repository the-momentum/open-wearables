"""
Tests for sync_vendor_data Celery task.

Tests synchronization of workout data from external providers (Garmin, Polar, Suunto).
"""

from unittest.mock import MagicMock, create_autospec, patch

from pytest_mock import MockerFixture
from sqlalchemy.orm import Session

from app.integrations.celery.tasks.sync_vendor_data_task import sync_vendor_data
from app.repositories.data_point_series_repository import WriteCounts
from app.schemas.auth import ConnectionStatus
from app.schemas.sync_status import SyncStatus
from app.services.providers.base_strategy import BaseProviderStrategy, ProviderCapabilities
from app.services.providers.sync_247_result import Sync247Result
from app.services.providers.templates.base_247_data import Base247DataTemplate
from app.services.providers.templates.base_workouts import BaseWorkoutsTemplate
from app.services.sync_coordination import try_become_primary
from app.utils.sync_params import build_sync_params
from tests.factories import UserConnectionFactory, UserFactory


class TestSyncVendorDataTask:
    """Test suite for sync_vendor_data task."""

    def test_sync_vendor_data_success(self, mocker: MockerFixture, db: Session) -> None:
        """Test successful sync of vendor data."""
        mock_get_provider = mocker.patch("app.services.providers.factory.ProviderFactory.get_provider", autospec=True)
        mock_session_local = mocker.patch(
            "app.integrations.celery.tasks.sync_vendor_data_task.SessionLocal", autospec=True
        )
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
        mock_workouts = create_autospec(BaseWorkoutsTemplate, instance=True)
        mock_workouts.load_data.return_value = True

        mock_strategy = create_autospec(BaseProviderStrategy, instance=True)
        mock_strategy.capabilities = ProviderCapabilities(rest_pull=True)
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

    def test_sync_vendor_data_saves_247_data(self, mocker: MockerFixture, db: Session) -> None:
        mock_get_provider = mocker.patch("app.services.providers.factory.ProviderFactory.get_provider", autospec=True)
        mock_session_local = mocker.patch(
            "app.integrations.celery.tasks.sync_vendor_data_task.SessionLocal", autospec=True
        )
        user = UserFactory()
        UserConnectionFactory(user=user, provider="garmin", status=ConnectionStatus.ACTIVE)
        mock_session_local.return_value.__enter__.return_value = db

        mock_strategy = create_autospec(BaseProviderStrategy, instance=True)
        mock_strategy.capabilities = ProviderCapabilities(rest_pull=True)
        mock_strategy.workouts = None
        mock_strategy.data_247 = create_autospec(Base247DataTemplate, instance=True)
        results_247 = Sync247Result(provider="garmin")
        results_247.record("sleep", WriteCounts(2, 1))
        mock_strategy.data_247.load_and_save_all.return_value = results_247
        mock_get_provider.return_value = mock_strategy

        result = sync_vendor_data(str(user.id))

        garmin = result["providers_synced"]["garmin"]
        assert garmin["params"]["data_247"]["status"] == SyncStatus.SUCCESS
        assert garmin["params"]["data_247"]["items_inserted"] == 2
        assert garmin["params"]["data_247"]["items_updated"] == 1
        mock_strategy.data_247.load_and_save_all.assert_called_once()
        assert mock_strategy.data_247.load_and_save_all.call_args.kwargs["is_first_sync"] is True

    def test_sync_vendor_data_with_date_range(self, mocker: MockerFixture, db: Session) -> None:
        """Test sync with specific date range."""
        mock_get_provider = mocker.patch("app.services.providers.factory.ProviderFactory.get_provider", autospec=True)
        mock_session_local = mocker.patch(
            "app.integrations.celery.tasks.sync_vendor_data_task.SessionLocal", autospec=True
        )
        # Arrange
        user = UserFactory()
        UserConnectionFactory(
            user=user,
            provider="polar",
            status=ConnectionStatus.ACTIVE,
        )

        mock_session_local.return_value.__enter__.return_value = db
        mock_session_local.return_value.__exit__.return_value = None

        mock_workouts = create_autospec(BaseWorkoutsTemplate, instance=True)
        mock_workouts.load_data.return_value = True

        mock_strategy = create_autospec(BaseProviderStrategy, instance=True)
        mock_strategy.capabilities = ProviderCapabilities(rest_pull=True)
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

    def test_sync_vendor_data_multiple_providers(self, mocker: MockerFixture, db: Session) -> None:
        """Test sync with multiple provider connections."""
        mock_get_provider = mocker.patch("app.services.providers.factory.ProviderFactory.get_provider", autospec=True)
        mock_session_local = mocker.patch(
            "app.integrations.celery.tasks.sync_vendor_data_task.SessionLocal", autospec=True
        )
        # Arrange
        user = UserFactory()
        UserConnectionFactory(user=user, provider="garmin", status=ConnectionStatus.ACTIVE)
        UserConnectionFactory(user=user, provider="polar", status=ConnectionStatus.ACTIVE)
        UserConnectionFactory(user=user, provider="suunto", status=ConnectionStatus.ACTIVE)

        mock_session_local.return_value.__enter__.return_value = db
        mock_session_local.return_value.__exit__.return_value = None

        mock_workouts = create_autospec(BaseWorkoutsTemplate, instance=True)
        mock_workouts.load_data.return_value = True

        mock_strategy = create_autospec(BaseProviderStrategy, instance=True)
        mock_strategy.capabilities = ProviderCapabilities(rest_pull=True)
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

    def test_sync_vendor_data_specific_providers_only(self, mocker: MockerFixture, db: Session) -> None:
        """Test sync with specific provider filter."""
        mock_get_provider = mocker.patch("app.services.providers.factory.ProviderFactory.get_provider", autospec=True)
        mock_session_local = mocker.patch(
            "app.integrations.celery.tasks.sync_vendor_data_task.SessionLocal", autospec=True
        )
        # Arrange
        user = UserFactory()
        UserConnectionFactory(user=user, provider="garmin", status=ConnectionStatus.ACTIVE)
        UserConnectionFactory(user=user, provider="polar", status=ConnectionStatus.ACTIVE)

        mock_session_local.return_value.__enter__.return_value = db
        mock_session_local.return_value.__exit__.return_value = None

        mock_workouts = create_autospec(BaseWorkoutsTemplate, instance=True)
        mock_workouts.load_data.return_value = True

        mock_strategy = create_autospec(BaseProviderStrategy, instance=True)
        mock_strategy.capabilities = ProviderCapabilities(rest_pull=True)
        mock_strategy.workouts = mock_workouts
        mock_get_provider.return_value = mock_strategy

        # Act - sync only Garmin
        result = sync_vendor_data(str(user.id), providers=["garmin"])

        # Assert
        assert len(result["providers_synced"]) == 1
        assert "garmin" in result["providers_synced"]
        assert "polar" not in result["providers_synced"]
        mock_workouts.load_data.assert_called_once()

    def test_sync_vendor_data_no_active_connections(self, mocker: MockerFixture, db: Session) -> None:
        """Test sync when user has no active connections."""
        mock_session_local = mocker.patch(
            "app.integrations.celery.tasks.sync_vendor_data_task.SessionLocal", autospec=True
        )
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

    def test_sync_vendor_data_provider_error(self, mocker: MockerFixture, db: Session) -> None:
        """Test handling of provider API errors."""
        mock_get_provider = mocker.patch("app.services.providers.factory.ProviderFactory.get_provider", autospec=True)
        mock_session_local = mocker.patch(
            "app.integrations.celery.tasks.sync_vendor_data_task.SessionLocal", autospec=True
        )
        # Arrange
        user = UserFactory()
        UserConnectionFactory(user=user, provider="garmin", status=ConnectionStatus.ACTIVE)

        mock_session_local.return_value.__enter__.return_value = db
        mock_session_local.return_value.__exit__.return_value = None

        # Mock provider that fails during sync
        mock_workouts = create_autospec(BaseWorkoutsTemplate, instance=True)
        mock_workouts.load_data.side_effect = Exception("Provider API unavailable")

        mock_strategy = create_autospec(BaseProviderStrategy, instance=True)
        mock_strategy.capabilities = ProviderCapabilities(rest_pull=True)
        mock_strategy.workouts = mock_workouts
        mock_get_provider.return_value = mock_strategy

        # Act
        result = sync_vendor_data(str(user.id))

        # Assert
        assert str(result["user_id"]) == str(user.id)
        assert "garmin" in result["providers_synced"]
        assert result["providers_synced"]["garmin"]["params"]["workouts"]["success"] is False
        # The error's type only: its text could carry the rows a write failed on.
        assert result["providers_synced"]["garmin"]["params"]["workouts"]["error_code"] == "Exception"

    def test_a_run_where_everything_failed_still_records_its_data_types(
        self, mocker: MockerFixture, db: Session
    ) -> None:
        mock_get_provider = mocker.patch("app.services.providers.factory.ProviderFactory.get_provider", autospec=True)
        mock_session_local = mocker.patch(
            "app.integrations.celery.tasks.sync_vendor_data_task.SessionLocal", autospec=True
        )
        mock_record = mocker.patch(
            "app.integrations.celery.tasks.sync_vendor_data_task.try_record_data_types", autospec=True
        )
        user = UserFactory()
        UserConnectionFactory(user=user, provider="garmin", status=ConnectionStatus.ACTIVE)
        mock_session_local.return_value.__enter__.return_value = db
        mock_session_local.return_value.__exit__.return_value = None
        mock_strategy = create_autospec(BaseProviderStrategy, instance=True)
        mock_strategy.capabilities = ProviderCapabilities(rest_pull=True)
        mock_strategy.workouts = create_autospec(BaseWorkoutsTemplate, instance=True)
        mock_strategy.workouts.load_data.side_effect = Exception("Provider API unavailable")
        mock_strategy.data_247 = None
        mock_get_provider.return_value = mock_strategy

        sync_vendor_data(str(user.id))

        outcomes = mock_record.call_args.args[1]
        assert [(o.data_type, o.status) for o in outcomes] == [("workouts", SyncStatus.FAILED)]

    def test_records_data_types_before_the_runs_terminal_event(self, mocker: MockerFixture, db: Session) -> None:
        """A consumer acting on sync.completed reads the per-type outcomes from the history."""
        mock_get_provider = mocker.patch("app.services.providers.factory.ProviderFactory.get_provider", autospec=True)
        mock_session_local = mocker.patch(
            "app.integrations.celery.tasks.sync_vendor_data_task.SessionLocal", autospec=True
        )
        user = UserFactory()
        UserConnectionFactory(user=user, provider="garmin", status=ConnectionStatus.ACTIVE)
        mock_session_local.return_value.__enter__.return_value = db
        mock_session_local.return_value.__exit__.return_value = None
        mock_strategy = create_autospec(BaseProviderStrategy, instance=True)
        mock_strategy.capabilities = ProviderCapabilities(rest_pull=True)
        mock_strategy.workouts = create_autospec(BaseWorkoutsTemplate, instance=True)
        mock_strategy.workouts.load_data.return_value = 3
        mock_strategy.data_247 = None
        mock_get_provider.return_value = mock_strategy
        calls = MagicMock()
        task = "app.integrations.celery.tasks.sync_vendor_data_task"

        with (
            patch(f"{task}.try_record_data_types", calls.record),
            patch(f"{task}.emit_sync_completed", calls.completed),
        ):
            sync_vendor_data(str(user.id))

        assert [name for name, *_ in calls.mock_calls] == ["record", "completed"]

    def test_sync_vendor_data_sync_returns_false(self, mocker: MockerFixture, db: Session) -> None:
        """Test handling when provider sync returns False."""
        mock_get_provider = mocker.patch("app.services.providers.factory.ProviderFactory.get_provider", autospec=True)
        mock_session_local = mocker.patch(
            "app.integrations.celery.tasks.sync_vendor_data_task.SessionLocal", autospec=True
        )
        # Arrange
        user = UserFactory()
        UserConnectionFactory(user=user, provider="polar", status=ConnectionStatus.ACTIVE)

        mock_session_local.return_value.__enter__.return_value = db
        mock_session_local.return_value.__exit__.return_value = None

        mock_workouts = create_autospec(BaseWorkoutsTemplate, instance=True)
        mock_workouts.load_data.return_value = False

        mock_strategy = create_autospec(BaseProviderStrategy, instance=True)
        mock_strategy.capabilities = ProviderCapabilities(rest_pull=True)
        mock_strategy.workouts = mock_workouts
        mock_get_provider.return_value = mock_strategy

        # Act
        result = sync_vendor_data(str(user.id))

        # Assert - provider is added to providers_synced with workouts success=False
        assert "polar" in result["providers_synced"]
        assert result["providers_synced"]["polar"]["params"]["workouts"]["success"] is False
        assert result["errors"] == {}

    def test_sync_vendor_data_workouts_not_supported(self, mocker: MockerFixture, db: Session) -> None:
        """Test handling when provider doesn't support workouts."""
        mock_get_provider = mocker.patch("app.services.providers.factory.ProviderFactory.get_provider", autospec=True)
        mock_session_local = mocker.patch(
            "app.integrations.celery.tasks.sync_vendor_data_task.SessionLocal", autospec=True
        )
        # Arrange
        user = UserFactory()
        UserConnectionFactory(user=user, provider="garmin", status=ConnectionStatus.ACTIVE)

        mock_session_local.return_value.__enter__.return_value = db
        mock_session_local.return_value.__exit__.return_value = None

        # Mock provider without workout support
        mock_strategy = create_autospec(BaseProviderStrategy, instance=True)
        mock_strategy.capabilities = ProviderCapabilities(rest_pull=True)
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

    def test_sync_vendor_data_skips_push_based_provider(self, mocker: MockerFixture, db: Session) -> None:
        """Test that push-based providers (no cloud API) are filtered out entirely."""
        mock_get_provider = mocker.patch("app.services.providers.factory.ProviderFactory.get_provider", autospec=True)
        mock_session_local = mocker.patch(
            "app.integrations.celery.tasks.sync_vendor_data_task.SessionLocal", autospec=True
        )
        # Arrange
        user = UserFactory()
        UserConnectionFactory(user=user, provider="apple", status=ConnectionStatus.ACTIVE)

        mock_session_local.return_value.__enter__.return_value = db
        mock_session_local.return_value.__exit__.return_value = None

        mock_strategy = create_autospec(BaseProviderStrategy, instance=True)
        mock_strategy.capabilities = ProviderCapabilities(rest_pull=False)
        mock_get_provider.return_value = mock_strategy

        # Act
        result = sync_vendor_data(str(user.id))

        # Assert - SDK provider is filtered out, never enters sync loop
        assert "apple" not in result["providers_synced"]
        assert result["errors"] == {}
        assert result["message"] == "No active provider connections found"

    def test_sync_vendor_data_invalid_user_id(self) -> None:
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


class TestSyncVendorDataLinkedSkip:
    """A profile that loses the linked-account lock must not look like it synced."""

    def test_skip_reports_skipped_and_leaves_the_cursor_alone(self, mocker: MockerFixture, db: Session) -> None:
        mock_get_provider = mocker.patch("app.services.providers.factory.ProviderFactory.get_provider", autospec=True)
        mock_session_local = mocker.patch(
            "app.integrations.celery.tasks.sync_vendor_data_task.SessionLocal", autospec=True
        )
        user = UserFactory()
        holder = UserFactory()
        provider_user_id = "shared-account-1"
        connection = UserConnectionFactory(
            user=user,
            provider="garmin",
            status=ConnectionStatus.ACTIVE,
            provider_user_id=provider_user_id,
        )
        # The holder keeps an active connection, so the stale-lock steal path must not fire.
        UserConnectionFactory(
            user=holder,
            provider="garmin",
            status=ConnectionStatus.ACTIVE,
            provider_user_id=provider_user_id,
        )
        try_become_primary("garmin", provider_user_id, holder.id, scope="pull")

        mock_session_local.return_value.__enter__.return_value = db
        mock_session_local.return_value.__exit__.return_value = None
        mock_strategy = create_autospec(BaseProviderStrategy, instance=True)
        mock_strategy.capabilities = ProviderCapabilities(rest_pull=True)
        mock_strategy.workouts = create_autospec(BaseWorkoutsTemplate, instance=True)
        mock_get_provider.return_value = mock_strategy

        before = connection.last_synced_at
        with patch(
            "app.integrations.celery.tasks.sync_vendor_data_task.emit_sync_completed", autospec=True
        ) as emit_completed:
            result = sync_vendor_data(str(user.id))

        assert result["providers_synced"]["garmin"]["params"]["skipped"] is True
        assert result["errors"] == {}
        mock_strategy.workouts.load_data.assert_not_called()

        emit_completed.assert_called_once()
        assert emit_completed.call_args.kwargs["status"] == SyncStatus.SKIPPED
        assert emit_completed.call_args.kwargs["items_processed"] == 0

        db.refresh(connection)
        assert connection.last_synced_at == before
