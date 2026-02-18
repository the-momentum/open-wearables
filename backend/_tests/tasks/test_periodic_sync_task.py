"""
Tests for sync_all_users periodic Celery task.

Tests the periodic task that syncs data for all users with active connections.
"""

from unittest.mock import MagicMock, patch

from sqlalchemy.orm import Session

from app.integrations.celery.tasks.periodic_sync_task import sync_all_users
from app.schemas import ConnectionStatus
from _tests.factories import UserConnectionFactory, UserFactory


class TestSyncAllUsersTask:
    """Test suite for sync_all_users periodic task."""

    @patch("app.integrations.celery.tasks.periodic_sync_task.SessionLocal")
    @patch("app.integrations.celery.tasks.periodic_sync_task.sync_vendor_data")
    def test_sync_all_users_with_active_connections(
        self,
        mock_sync_vendor_data: MagicMock,
        mock_session_local: MagicMock,
        db: Session,
        mock_celery_app: MagicMock,
    ) -> None:
        """Test syncing all users with active connections."""
        # Arrange
        user1 = UserFactory()
        user2 = UserFactory()
        user3 = UserFactory()

        UserConnectionFactory(user=user1, provider="garmin", status=ConnectionStatus.ACTIVE)
        UserConnectionFactory(user=user2, provider="polar", status=ConnectionStatus.ACTIVE)
        UserConnectionFactory(user=user3, provider="suunto", status=ConnectionStatus.ACTIVE)

        mock_session_local.return_value.__enter__ = MagicMock(return_value=db)
        mock_session_local.return_value.__exit__ = MagicMock(return_value=None)

        # Act
        result = sync_all_users()

        # Assert
        assert result["users_for_sync"] == 3
        assert mock_sync_vendor_data.delay.call_count == 3

        # Verify each user was queued for sync
        call_args_list = [call.kwargs["user_id"] for call in mock_sync_vendor_data.delay.call_args_list]
        assert str(user1.id) in call_args_list
        assert str(user2.id) in call_args_list
        assert str(user3.id) in call_args_list

    @patch("app.integrations.celery.tasks.periodic_sync_task.SessionLocal")
    @patch("app.integrations.celery.tasks.periodic_sync_task.sync_vendor_data")
    def test_sync_all_users_with_date_range(
        self,
        mock_sync_vendor_data: MagicMock,
        mock_session_local: MagicMock,
        db: Session,
        mock_celery_app: MagicMock,
    ) -> None:
        """Test syncing all users with specific date range."""
        # Arrange
        user = UserFactory()
        UserConnectionFactory(user=user, provider="garmin", status=ConnectionStatus.ACTIVE)

        mock_session_local.return_value.__enter__ = MagicMock(return_value=db)
        mock_session_local.return_value.__exit__ = MagicMock(return_value=None)

        start_date = "2025-01-01T00:00:00Z"
        end_date = "2025-12-31T23:59:59Z"

        # Act
        result = sync_all_users(start_date=start_date, end_date=end_date)

        # Assert
        assert result["users_for_sync"] == 1
        mock_sync_vendor_data.delay.assert_called_once_with(
            user_id=str(user.id),
            start_date=start_date,
            end_date=end_date,
        )

    @patch("app.integrations.celery.tasks.periodic_sync_task.SessionLocal")
    @patch("app.integrations.celery.tasks.periodic_sync_task.sync_vendor_data")
    def test_sync_all_users_skips_disconnected_users(
        self,
        mock_sync_vendor_data: MagicMock,
        mock_session_local: MagicMock,
        db: Session,
        mock_celery_app: MagicMock,
    ) -> None:
        """Test that users without active connections are not synced."""
        # Arrange
        user1 = UserFactory()
        user2 = UserFactory()

        # User 1 has active connection
        UserConnectionFactory(user=user1, provider="garmin", status=ConnectionStatus.ACTIVE)

        # User 2 has disconnected connection
        UserConnectionFactory(user=user2, provider="polar", status=ConnectionStatus.REVOKED)

        mock_session_local.return_value.__enter__ = MagicMock(return_value=db)
        mock_session_local.return_value.__exit__ = MagicMock(return_value=None)

        # Act
        result = sync_all_users()

        # Assert
        assert result["users_for_sync"] == 1
        mock_sync_vendor_data.delay.assert_called_once()

        # Verify only user1 was queued
        call_kwargs = mock_sync_vendor_data.delay.call_args.kwargs
        assert call_kwargs["user_id"] == str(user1.id)

    @patch("app.integrations.celery.tasks.periodic_sync_task.SessionLocal")
    @patch("app.integrations.celery.tasks.periodic_sync_task.sync_vendor_data")
    def test_sync_all_users_no_users(
        self,
        mock_sync_vendor_data: MagicMock,
        mock_session_local: MagicMock,
        db: Session,
        mock_celery_app: MagicMock,
    ) -> None:
        """Test syncing when no users have active connections."""
        # Arrange - no users with connections
        mock_session_local.return_value.__enter__ = MagicMock(return_value=db)
        mock_session_local.return_value.__exit__ = MagicMock(return_value=None)

        # Act
        result = sync_all_users()

        # Assert
        assert result["users_for_sync"] == 0
        mock_sync_vendor_data.delay.assert_not_called()

    @patch("app.integrations.celery.tasks.periodic_sync_task.SessionLocal")
    @patch("app.integrations.celery.tasks.periodic_sync_task.sync_vendor_data")
    def test_sync_all_users_multiple_connections_per_user(
        self,
        mock_sync_vendor_data: MagicMock,
        mock_session_local: MagicMock,
        db: Session,
        mock_celery_app: MagicMock,
    ) -> None:
        """Test that users with multiple connections are only queued once."""
        # Arrange
        user = UserFactory()

        # User has multiple active connections
        UserConnectionFactory(user=user, provider="garmin", status=ConnectionStatus.ACTIVE)
        UserConnectionFactory(user=user, provider="polar", status=ConnectionStatus.ACTIVE)
        UserConnectionFactory(user=user, provider="suunto", status=ConnectionStatus.ACTIVE)

        mock_session_local.return_value.__enter__ = MagicMock(return_value=db)
        mock_session_local.return_value.__exit__ = MagicMock(return_value=None)

        # Act
        result = sync_all_users()

        # Assert
        # User should only be counted once despite having 3 connections
        assert result["users_for_sync"] == 1
        mock_sync_vendor_data.delay.assert_called_once_with(user_id=str(user.id), start_date=None, end_date=None)

    @patch("app.integrations.celery.tasks.periodic_sync_task.SessionLocal")
    @patch("app.integrations.celery.tasks.periodic_sync_task.sync_vendor_data")
    def test_sync_all_users_mixed_connection_statuses(
        self,
        mock_sync_vendor_data: MagicMock,
        mock_session_local: MagicMock,
        db: Session,
        mock_celery_app: MagicMock,
    ) -> None:
        """Test syncing users with mixed connection statuses."""
        # Arrange
        user1 = UserFactory()
        user2 = UserFactory()
        user3 = UserFactory()

        # User 1: connected
        UserConnectionFactory(user=user1, provider="garmin", status=ConnectionStatus.ACTIVE)

        # User 2: mixed statuses (has at least one connected)
        UserConnectionFactory(user=user2, provider="polar", status=ConnectionStatus.ACTIVE)
        UserConnectionFactory(user=user2, provider="suunto", status=ConnectionStatus.REVOKED)

        # User 3: all disconnected
        UserConnectionFactory(user=user3, provider="garmin", status=ConnectionStatus.REVOKED)

        mock_session_local.return_value.__enter__ = MagicMock(return_value=db)
        mock_session_local.return_value.__exit__ = MagicMock(return_value=None)

        # Act
        result = sync_all_users()

        # Assert
        assert result["users_for_sync"] == 2  # Only user1 and user2
        assert mock_sync_vendor_data.delay.call_count == 2

        call_args_list = [call.kwargs["user_id"] for call in mock_sync_vendor_data.delay.call_args_list]
        assert str(user1.id) in call_args_list
        assert str(user2.id) in call_args_list
        assert str(user3.id) not in call_args_list

    @patch("app.integrations.celery.tasks.periodic_sync_task.SessionLocal")
    @patch("app.integrations.celery.tasks.periodic_sync_task.sync_vendor_data")
    def test_sync_all_users_queues_async_tasks(
        self,
        mock_sync_vendor_data: MagicMock,
        mock_session_local: MagicMock,
        db: Session,
        mock_celery_app: MagicMock,
    ) -> None:
        """Test that sync tasks are queued asynchronously with delay."""
        # Arrange
        user = UserFactory()
        UserConnectionFactory(user=user, provider="garmin", status=ConnectionStatus.ACTIVE)

        mock_session_local.return_value.__enter__ = MagicMock(return_value=db)
        mock_session_local.return_value.__exit__ = MagicMock(return_value=None)

        # Act
        sync_all_users()

        # Assert - verify .delay() was called (async execution)
        mock_sync_vendor_data.delay.assert_called_once()
        # Verify .apply() or direct call was NOT used
        mock_sync_vendor_data.apply.assert_not_called() if hasattr(mock_sync_vendor_data, "apply") else None

    @patch("app.integrations.celery.tasks.periodic_sync_task.SessionLocal")
    @patch("app.integrations.celery.tasks.periodic_sync_task.sync_vendor_data")
    def test_sync_all_users_large_batch(
        self,
        mock_sync_vendor_data: MagicMock,
        mock_session_local: MagicMock,
        db: Session,
        mock_celery_app: MagicMock,
    ) -> None:
        """Test syncing a large number of users."""
        # Arrange - create 10 users with connections
        users = []
        for i in range(10):
            user = UserFactory()
            users.append(user)
            UserConnectionFactory(user=user, provider="garmin", status=ConnectionStatus.ACTIVE)

        mock_session_local.return_value.__enter__ = MagicMock(return_value=db)
        mock_session_local.return_value.__exit__ = MagicMock(return_value=None)

        # Act
        result = sync_all_users()

        # Assert
        assert result["users_for_sync"] == 10
        assert mock_sync_vendor_data.delay.call_count == 10

        # Verify all users were queued
        call_args_list = [call.kwargs["user_id"] for call in mock_sync_vendor_data.delay.call_args_list]
        for user in users:
            assert str(user.id) in call_args_list
