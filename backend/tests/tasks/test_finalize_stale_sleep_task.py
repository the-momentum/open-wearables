"""
Tests for finalize_stale_sleeps Celery task.

Tests the background task that finalizes sleep sessions that have been
inactive in Redis for longer than the configured threshold.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

from sqlalchemy.orm import Session

from app.integrations.celery.tasks.finalize_stale_sleep_task import finalize_stale_sleeps
from tests.factories import UserFactory


class TestFinalizeStaleSleepsTask:
    """Test suite for finalize_stale_sleeps task."""

    @patch("app.integrations.celery.tasks.finalize_stale_sleep_task.get_redis_client")
    @patch("app.integrations.celery.tasks.finalize_stale_sleep_task.SessionLocal")
    def test_finalize_stale_sleeps_no_active_users(
        self,
        mock_session_local: MagicMock,
        mock_redis_client_func: MagicMock,
        db: Session,
        mock_celery_app: MagicMock,
    ) -> None:
        """Verify task completes successfully when no active sleep sessions exist."""
        # Arrange
        mock_session_local.return_value.__enter__ = MagicMock(return_value=db)
        mock_session_local.return_value.__exit__ = MagicMock(return_value=None)

        mock_redis = MagicMock()
        mock_redis.smembers.return_value = []  # No active users
        mock_redis_client_func.return_value = mock_redis

        # Act
        result = finalize_stale_sleeps()

        # Assert
        assert result is None  # Task should complete without errors
        mock_redis.smembers.assert_called_once()

    @patch("app.integrations.celery.tasks.finalize_stale_sleep_task.finish_sleep")
    @patch("app.integrations.celery.tasks.finalize_stale_sleep_task.load_sleep_state")
    @patch("app.integrations.celery.tasks.finalize_stale_sleep_task.get_redis_client")
    @patch("app.integrations.celery.tasks.finalize_stale_sleep_task.SessionLocal")
    def test_finalize_stale_sleeps_with_stale_session(
        self,
        mock_session_local: MagicMock,
        mock_redis_client_func: MagicMock,
        mock_load_state: MagicMock,
        mock_finish_sleep: MagicMock,
        db: Session,
        mock_celery_app: MagicMock,
    ) -> None:
        """Verify task finalizes sleep sessions older than threshold."""
        # Arrange
        user_id = str(uuid4())
        now = datetime.now(timezone.utc)
        stale_timestamp = now - timedelta(hours=2)  # Older than 1 hour threshold

        mock_session_local.return_value.__enter__ = MagicMock(return_value=db)
        mock_session_local.return_value.__exit__ = MagicMock(return_value=None)

        mock_redis = MagicMock()
        mock_redis.smembers.return_value = [user_id]
        mock_redis_client_func.return_value = mock_redis

        # Mock sleep state with old timestamp
        mock_sleep_state = {
            "uuid": str(uuid4()),
            "source_name": "Apple Watch",
            "start_time": stale_timestamp.isoformat(),
            "last_timestamp": stale_timestamp.isoformat(),
            "last_type": 3,  # ASLEEP_CORE
            "in_bed": 900,
            "awake": 300,
            "light": 3600,
            "deep": 1800,
            "rem": 1200,
        }
        mock_load_state.return_value = mock_sleep_state

        # Act
        finalize_stale_sleeps()

        # Assert
        mock_load_state.assert_called_once_with(user_id)
        mock_finish_sleep.assert_called_once_with(db, user_id, mock_sleep_state)

    @patch("app.integrations.celery.tasks.finalize_stale_sleep_task.finish_sleep")
    @patch("app.integrations.celery.tasks.finalize_stale_sleep_task.load_sleep_state")
    @patch("app.integrations.celery.tasks.finalize_stale_sleep_task.get_redis_client")
    @patch("app.integrations.celery.tasks.finalize_stale_sleep_task.SessionLocal")
    def test_finalize_stale_sleeps_skips_recent_session(
        self,
        mock_session_local: MagicMock,
        mock_redis_client_func: MagicMock,
        mock_load_state: MagicMock,
        mock_finish_sleep: MagicMock,
        db: Session,
        mock_celery_app: MagicMock,
    ) -> None:
        """Verify task does not finalize recent sleep sessions."""
        # Arrange
        user_id = str(uuid4())
        now = datetime.now(timezone.utc)
        recent_timestamp = now - timedelta(minutes=30)  # Less than 1 hour threshold

        mock_session_local.return_value.__enter__ = MagicMock(return_value=db)
        mock_session_local.return_value.__exit__ = MagicMock(return_value=None)

        mock_redis = MagicMock()
        mock_redis.smembers.return_value = [user_id]
        mock_redis_client_func.return_value = mock_redis

        # Mock recent sleep state
        mock_sleep_state = {
            "uuid": str(uuid4()),
            "source_name": "Apple Watch",
            "start_time": recent_timestamp.isoformat(),
            "last_timestamp": recent_timestamp.isoformat(),
            "last_type": 3,
            "in_bed": 900,
            "awake": 0,
            "light": 900,
            "deep": 0,
            "rem": 0,
        }
        mock_load_state.return_value = mock_sleep_state

        # Act
        finalize_stale_sleeps()

        # Assert
        mock_load_state.assert_called_once_with(user_id)
        mock_finish_sleep.assert_not_called()  # Should not finalize recent sessions

    @patch("app.integrations.celery.tasks.finalize_stale_sleep_task.load_sleep_state")
    @patch("app.integrations.celery.tasks.finalize_stale_sleep_task.get_redis_client")
    @patch("app.integrations.celery.tasks.finalize_stale_sleep_task.SessionLocal")
    def test_finalize_stale_sleeps_handles_missing_state(
        self,
        mock_session_local: MagicMock,
        mock_redis_client_func: MagicMock,
        mock_load_state: MagicMock,
        db: Session,
        mock_celery_app: MagicMock,
    ) -> None:
        """Verify task gracefully handles users with no sleep state."""
        # Arrange
        user_id = str(uuid4())

        mock_session_local.return_value.__enter__ = MagicMock(return_value=db)
        mock_session_local.return_value.__exit__ = MagicMock(return_value=None)

        mock_redis = MagicMock()
        mock_redis.smembers.return_value = [user_id]
        mock_redis_client_func.return_value = mock_redis

        mock_load_state.return_value = None  # State not found

        # Act
        result = finalize_stale_sleeps()

        # Assert
        assert result is None
        mock_load_state.assert_called_once_with(user_id)

    @patch("app.integrations.celery.tasks.finalize_stale_sleep_task.finish_sleep")
    @patch("app.integrations.celery.tasks.finalize_stale_sleep_task.load_sleep_state")
    @patch("app.integrations.celery.tasks.finalize_stale_sleep_task.get_redis_client")
    @patch("app.integrations.celery.tasks.finalize_stale_sleep_task.SessionLocal")
    def test_finalize_stale_sleeps_handles_multiple_users(
        self,
        mock_session_local: MagicMock,
        mock_redis_client_func: MagicMock,
        mock_load_state: MagicMock,
        mock_finish_sleep: MagicMock,
        db: Session,
        mock_celery_app: MagicMock,
    ) -> None:
        """Verify task processes multiple users with stale sessions."""
        # Arrange
        user_id_1 = str(uuid4())
        user_id_2 = str(uuid4())
        user_id_3 = str(uuid4())
        now = datetime.now(timezone.utc)
        stale_timestamp = now - timedelta(hours=2)

        mock_session_local.return_value.__enter__ = MagicMock(return_value=db)
        mock_session_local.return_value.__exit__ = MagicMock(return_value=None)

        mock_redis = MagicMock()
        mock_redis.smembers.return_value = [user_id_1, user_id_2, user_id_3]
        mock_redis_client_func.return_value = mock_redis

        # User 1: Stale session (should finalize)
        state_1 = {
            "uuid": str(uuid4()),
            "source_name": "Apple Watch",
            "start_time": stale_timestamp.isoformat(),
            "last_timestamp": stale_timestamp.isoformat(),
            "last_type": 3,
            "in_bed": 900,
            "awake": 0,
            "light": 3600,
            "deep": 1800,
            "rem": 1200,
        }

        # User 2: No state (should skip)
        state_2 = None

        # User 3: Stale session (should finalize)
        state_3 = {
            "uuid": str(uuid4()),
            "source_name": "iPhone",
            "start_time": stale_timestamp.isoformat(),
            "last_timestamp": stale_timestamp.isoformat(),
            "last_type": 2,
            "in_bed": 600,
            "awake": 600,
            "light": 0,
            "deep": 0,
            "rem": 0,
        }

        mock_load_state.side_effect = [state_1, state_2, state_3]

        # Act
        finalize_stale_sleeps()

        # Assert
        assert mock_load_state.call_count == 3
        assert mock_finish_sleep.call_count == 2  # Only user 1 and 3

        mock_finish_sleep.assert_any_call(db, user_id_1, state_1)
        mock_finish_sleep.assert_any_call(db, user_id_3, state_3)

    @patch("app.integrations.celery.tasks.finalize_stale_sleep_task.log_and_capture_error")
    @patch("app.integrations.celery.tasks.finalize_stale_sleep_task.finish_sleep")
    @patch("app.integrations.celery.tasks.finalize_stale_sleep_task.load_sleep_state")
    @patch("app.integrations.celery.tasks.finalize_stale_sleep_task.get_redis_client")
    @patch("app.integrations.celery.tasks.finalize_stale_sleep_task.SessionLocal")
    def test_finalize_stale_sleeps_handles_finish_error(
        self,
        mock_session_local: MagicMock,
        mock_redis_client_func: MagicMock,
        mock_load_state: MagicMock,
        mock_finish_sleep: MagicMock,
        mock_log_error: MagicMock,
        db: Session,
        mock_celery_app: MagicMock,
    ) -> None:
        """Verify task continues processing other users if one finalization fails."""
        # Arrange
        user_id_1 = str(uuid4())
        user_id_2 = str(uuid4())
        now = datetime.now(timezone.utc)
        stale_timestamp = now - timedelta(hours=2)

        mock_session_local.return_value.__enter__ = MagicMock(return_value=db)
        mock_session_local.return_value.__exit__ = MagicMock(return_value=None)

        mock_redis = MagicMock()
        mock_redis.smembers.return_value = [user_id_1, user_id_2]
        mock_redis_client_func.return_value = mock_redis

        state_1 = {
            "uuid": str(uuid4()),
            "source_name": "Apple Watch",
            "start_time": stale_timestamp.isoformat(),
            "last_timestamp": stale_timestamp.isoformat(),
            "last_type": 3,
            "in_bed": 900,
            "awake": 0,
            "light": 3600,
            "deep": 0,
            "rem": 0,
        }

        state_2 = {
            "uuid": str(uuid4()),
            "source_name": "iPhone",
            "start_time": stale_timestamp.isoformat(),
            "last_timestamp": stale_timestamp.isoformat(),
            "last_type": 5,
            "in_bed": 0,
            "awake": 0,
            "light": 0,
            "deep": 0,
            "rem": 1800,
        }

        mock_load_state.side_effect = [state_1, state_2]

        # User 1 finalization fails
        mock_finish_sleep.side_effect = [Exception("Database error"), None]

        # Act
        finalize_stale_sleeps()

        # Assert
        assert mock_finish_sleep.call_count == 2
        mock_log_error.assert_called_once()  # Error should be logged for user 1

        # Verify user 2 was still processed despite user 1 error
        mock_finish_sleep.assert_any_call(db, user_id_2, state_2)

    @patch("app.integrations.celery.tasks.finalize_stale_sleep_task.load_sleep_state")
    @patch("app.integrations.celery.tasks.finalize_stale_sleep_task.get_redis_client")
    @patch("app.integrations.celery.tasks.finalize_stale_sleep_task.SessionLocal")
    def test_finalize_stale_sleeps_handles_invalid_timestamp(
        self,
        mock_session_local: MagicMock,
        mock_redis_client_func: MagicMock,
        mock_load_state: MagicMock,
        db: Session,
        mock_celery_app: MagicMock,
    ) -> None:
        """Verify task handles malformed timestamp in sleep state."""
        # Arrange
        user_id = str(uuid4())

        mock_session_local.return_value.__enter__ = MagicMock(return_value=db)
        mock_session_local.return_value.__exit__ = MagicMock(return_value=None)

        mock_redis = MagicMock()
        mock_redis.smembers.return_value = [user_id]
        mock_redis_client_func.return_value = mock_redis

        # Invalid timestamp format
        mock_sleep_state = {
            "uuid": str(uuid4()),
            "source_name": "Apple Watch",
            "start_time": "2026-01-01T00:00:00Z",
            "last_timestamp": "invalid-timestamp",
            "last_type": 3,
            "in_bed": 900,
            "awake": 0,
            "light": 3600,
            "deep": 0,
            "rem": 0,
        }
        mock_load_state.return_value = mock_sleep_state

        # Act - should not crash
        result = finalize_stale_sleeps()

        # Assert
        assert result is None  # Task completes despite error
