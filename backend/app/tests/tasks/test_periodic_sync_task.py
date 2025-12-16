"""
Tests for sync_all_users periodic Celery task.

Tests the periodic task that syncs data for all users with active connections.
"""

import pytest
from unittest.mock import MagicMock, patch

from sqlalchemy.orm import Session

from app.integrations.celery.tasks.periodic_sync_task import sync_all_users
from app.tests.utils.factories import create_user, create_user_connection
from app.schemas import ConnectionStatus


class TestSyncAllUsersTask:
    """Test suite for sync_all_users periodic task."""

    @patch("app.integrations.celery.tasks.periodic_sync_task.SessionLocal")
    @patch("app.integrations.celery.tasks.periodic_sync_task.sync_vendor_data")
    def test_sync_all_users_with_active_connections(
        self,
        mock_sync_vendor_data,
        mock_session_local,
        db: Session,
        mock_celery_app,
    ):
        """Test syncing all users with active connections."""
        # Arrange
        user1 = create_user(db)
        user2 = create_user(db)
        user3 = create_user(db)

        create_user_connection(db, user=user1, provider="garmin", status=ConnectionStatus.CONNECTED)
        create_user_connection(db, user=user2, provider="polar", status=ConnectionStatus.CONNECTED)
        create_user_connection(db, user=user3, provider="suunto", status=ConnectionStatus.CONNECTED)

        mock_session_local.return_value.__enter__ = MagicMock(return_value=db)
        mock_session_local.return_value.__exit__ = MagicMock(return_value=None)

        # Act
        result = sync_all_users()

        # Assert
        assert result["users_for_sync"] == 3
        assert mock_sync_vendor_data.delay.call_count == 3

        # Verify each user was queued for sync
        call_args_list = [call[0][0] for call in mock_sync_vendor_data.delay.call_args_list]
        assert str(user1.id) in call_args_list
        assert str(user2.id) in call_args_list
        assert str(user3.id) in call_args_list

    @patch("app.integrations.celery.tasks.periodic_sync_task.SessionLocal")
    @patch("app.integrations.celery.tasks.periodic_sync_task.sync_vendor_data")
    def test_sync_all_users_with_date_range(
        self,
        mock_sync_vendor_data,
        mock_session_local,
        db: Session,
        mock_celery_app,
    ):
        """Test syncing all users with specific date range."""
        # Arrange
        user = create_user(db)
        create_user_connection(db, user=user, provider="garmin", status=ConnectionStatus.CONNECTED)

        mock_session_local.return_value.__enter__ = MagicMock(return_value=db)
        mock_session_local.return_value.__exit__ = MagicMock(return_value=None)

        start_date = "2025-01-01T00:00:00Z"
        end_date = "2025-12-31T23:59:59Z"

        # Act
        result = sync_all_users(start_date=start_date, end_date=end_date)

        # Assert
        assert result["users_for_sync"] == 1
        mock_sync_vendor_data.delay.assert_called_once_with(
            str(user.id),
            start_date,
            end_date,
        )

    @patch("app.integrations.celery.tasks.periodic_sync_task.SessionLocal")
    @patch("app.integrations.celery.tasks.periodic_sync_task.sync_vendor_data")
    def test_sync_all_users_skips_disconnected_users(
        self,
        mock_sync_vendor_data,
        mock_session_local,
        db: Session,
        mock_celery_app,
    ):
        """Test that users without active connections are not synced."""
        # Arrange
        user1 = create_user(db)
        user2 = create_user(db)

        # User 1 has active connection
        create_user_connection(db, user=user1, provider="garmin", status=ConnectionStatus.CONNECTED)

        # User 2 has disconnected connection
        create_user_connection(db, user=user2, provider="polar", status=ConnectionStatus.DISCONNECTED)

        mock_session_local.return_value.__enter__ = MagicMock(return_value=db)
        mock_session_local.return_value.__exit__ = MagicMock(return_value=None)

        # Act
        result = sync_all_users()

        # Assert
        assert result["users_for_sync"] == 1
        mock_sync_vendor_data.delay.assert_called_once()

        # Verify only user1 was queued
        call_args = mock_sync_vendor_data.delay.call_args[0]
        assert call_args[0] == str(user1.id)

    @patch("app.integrations.celery.tasks.periodic_sync_task.SessionLocal")
    @patch("app.integrations.celery.tasks.periodic_sync_task.sync_vendor_data")
    def test_sync_all_users_no_users(
        self,
        mock_sync_vendor_data,
        mock_session_local,
        db: Session,
        mock_celery_app,
    ):
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
        mock_sync_vendor_data,
        mock_session_local,
        db: Session,
        mock_celery_app,
    ):
        """Test that users with multiple connections are only queued once."""
        # Arrange
        user = create_user(db)

        # User has multiple active connections
        create_user_connection(db, user=user, provider="garmin", status=ConnectionStatus.CONNECTED)
        create_user_connection(db, user=user, provider="polar", status=ConnectionStatus.CONNECTED)
        create_user_connection(db, user=user, provider="suunto", status=ConnectionStatus.CONNECTED)

        mock_session_local.return_value.__enter__ = MagicMock(return_value=db)
        mock_session_local.return_value.__exit__ = MagicMock(return_value=None)

        # Act
        result = sync_all_users()

        # Assert
        # User should only be counted once despite having 3 connections
        assert result["users_for_sync"] == 1
        mock_sync_vendor_data.delay.assert_called_once_with(str(user.id), None, None)

    @patch("app.integrations.celery.tasks.periodic_sync_task.SessionLocal")
    @patch("app.integrations.celery.tasks.periodic_sync_task.sync_vendor_data")
    def test_sync_all_users_mixed_connection_statuses(
        self,
        mock_sync_vendor_data,
        mock_session_local,
        db: Session,
        mock_celery_app,
    ):
        """Test syncing users with mixed connection statuses."""
        # Arrange
        user1 = create_user(db)
        user2 = create_user(db)
        user3 = create_user(db)

        # User 1: connected
        create_user_connection(db, user=user1, provider="garmin", status=ConnectionStatus.CONNECTED)

        # User 2: mixed statuses (has at least one connected)
        create_user_connection(db, user=user2, provider="polar", status=ConnectionStatus.CONNECTED)
        create_user_connection(db, user=user2, provider="suunto", status=ConnectionStatus.DISCONNECTED)

        # User 3: all disconnected
        create_user_connection(db, user=user3, provider="garmin", status=ConnectionStatus.DISCONNECTED)

        mock_session_local.return_value.__enter__ = MagicMock(return_value=db)
        mock_session_local.return_value.__exit__ = MagicMock(return_value=None)

        # Act
        result = sync_all_users()

        # Assert
        assert result["users_for_sync"] == 2  # Only user1 and user2
        assert mock_sync_vendor_data.delay.call_count == 2

        call_args_list = [call[0][0] for call in mock_sync_vendor_data.delay.call_args_list]
        assert str(user1.id) in call_args_list
        assert str(user2.id) in call_args_list
        assert str(user3.id) not in call_args_list

    @patch("app.integrations.celery.tasks.periodic_sync_task.SessionLocal")
    @patch("app.integrations.celery.tasks.periodic_sync_task.sync_vendor_data")
    def test_sync_all_users_queues_async_tasks(
        self,
        mock_sync_vendor_data,
        mock_session_local,
        db: Session,
        mock_celery_app,
    ):
        """Test that sync tasks are queued asynchronously with delay."""
        # Arrange
        user = create_user(db)
        create_user_connection(db, user=user, provider="garmin", status=ConnectionStatus.CONNECTED)

        mock_session_local.return_value.__enter__ = MagicMock(return_value=db)
        mock_session_local.return_value.__exit__ = MagicMock(return_value=None)

        # Act
        sync_all_users()

        # Assert - verify .delay() was called (async execution)
        mock_sync_vendor_data.delay.assert_called_once()
        # Verify .apply() or direct call was NOT used
        mock_sync_vendor_data.apply.assert_not_called() if hasattr(
            mock_sync_vendor_data, "apply"
        ) else None

    @patch("app.integrations.celery.tasks.periodic_sync_task.SessionLocal")
    @patch("app.integrations.celery.tasks.periodic_sync_task.sync_vendor_data")
    def test_sync_all_users_large_batch(
        self,
        mock_sync_vendor_data,
        mock_session_local,
        db: Session,
        mock_celery_app,
    ):
        """Test syncing a large number of users."""
        # Arrange - create 10 users with connections
        users = []
        for i in range(10):
            user = create_user(db)
            users.append(user)
            create_user_connection(db, user=user, provider="garmin", status=ConnectionStatus.CONNECTED)

        mock_session_local.return_value.__enter__ = MagicMock(return_value=db)
        mock_session_local.return_value.__exit__ = MagicMock(return_value=None)

        # Act
        result = sync_all_users()

        # Assert
        assert result["users_for_sync"] == 10
        assert mock_sync_vendor_data.delay.call_count == 10

        # Verify all users were queued
        call_args_list = [call[0][0] for call in mock_sync_vendor_data.delay.call_args_list]
        for user in users:
            assert str(user.id) in call_args_list
