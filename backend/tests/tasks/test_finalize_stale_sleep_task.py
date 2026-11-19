"""
Tests for finalize_stale_sleeps Celery task.

Tests the background task that finalizes in-progress sleep sessions that have been
inactive for longer than the configured threshold. The task is backend-agnostic:
it discovers active users via ``iter_active_user_ids`` and serializes per user via
``user_sleep_lock`` (Redis or Postgres depending on configuration).
"""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

from sqlalchemy.orm import Session

from app.integrations.celery.tasks.finalize_stale_sleep_task import finalize_stale_sleeps
from app.schemas.providers.mobile_sdk import SleepState


@contextmanager
def _acquired_lock(*_args: object, **_kwargs: object) -> Iterator[bool]:
    """Stand-in for user_sleep_lock that always acquires."""
    yield True


def _state(timestamp: datetime, source_name: str = "Apple Watch") -> SleepState:
    return SleepState(
        uuid=str(uuid4()),
        source_name=source_name,
        device_model=None,
        provider=None,
        start_time=timestamp,
        end_time=timestamp,
        last_start_timestamp=timestamp,
        last_end_timestamp=timestamp,
        in_bed_seconds=900,
        awake_seconds=0,
        light_seconds=3600,
        deep_seconds=1800,
        rem_seconds=1200,
        stages=[],
    )


class TestFinalizeStaleSleepsTask:
    """Test suite for finalize_stale_sleeps task."""

    @patch("app.integrations.celery.tasks.finalize_stale_sleep_task.iter_active_user_ids")
    @patch("app.integrations.celery.tasks.finalize_stale_sleep_task.SessionLocal")
    def test_finalize_stale_sleeps_no_active_users(
        self,
        mock_session_local: MagicMock,
        mock_iter_active: MagicMock,
        db: Session,
        mock_celery_app: MagicMock,
    ) -> None:
        """Verify task completes successfully when no active sleep sessions exist."""
        mock_session_local.return_value.__enter__ = MagicMock(return_value=db)
        mock_session_local.return_value.__exit__ = MagicMock(return_value=None)
        mock_iter_active.return_value = []

        result = finalize_stale_sleeps()

        assert result is None
        mock_iter_active.assert_called_once()

    @patch("app.integrations.celery.tasks.finalize_stale_sleep_task.finish_sleep")
    @patch("app.integrations.celery.tasks.finalize_stale_sleep_task.load_sleep_state")
    @patch("app.integrations.celery.tasks.finalize_stale_sleep_task.user_sleep_lock", _acquired_lock)
    @patch("app.integrations.celery.tasks.finalize_stale_sleep_task.iter_active_user_ids")
    @patch("app.integrations.celery.tasks.finalize_stale_sleep_task.SessionLocal")
    def test_finalize_stale_sleeps_with_stale_session(
        self,
        mock_session_local: MagicMock,
        mock_iter_active: MagicMock,
        mock_load_state: MagicMock,
        mock_finish_sleep: MagicMock,
        db: Session,
        mock_celery_app: MagicMock,
    ) -> None:
        """Verify task finalizes sleep sessions older than threshold."""
        user_id = str(uuid4())
        stale_timestamp = datetime.now(timezone.utc) - timedelta(hours=2)

        mock_session_local.return_value.__enter__ = MagicMock(return_value=db)
        mock_session_local.return_value.__exit__ = MagicMock(return_value=None)
        mock_iter_active.return_value = [user_id]

        state = _state(stale_timestamp)
        mock_load_state.return_value = state

        finalize_stale_sleeps()

        mock_load_state.assert_called_once_with(db, user_id)
        mock_finish_sleep.assert_called_once_with(db, user_id, state)

    @patch("app.integrations.celery.tasks.finalize_stale_sleep_task.finish_sleep")
    @patch("app.integrations.celery.tasks.finalize_stale_sleep_task.load_sleep_state")
    @patch("app.integrations.celery.tasks.finalize_stale_sleep_task.user_sleep_lock", _acquired_lock)
    @patch("app.integrations.celery.tasks.finalize_stale_sleep_task.iter_active_user_ids")
    @patch("app.integrations.celery.tasks.finalize_stale_sleep_task.SessionLocal")
    def test_finalize_stale_sleeps_skips_recent_session(
        self,
        mock_session_local: MagicMock,
        mock_iter_active: MagicMock,
        mock_load_state: MagicMock,
        mock_finish_sleep: MagicMock,
        db: Session,
        mock_celery_app: MagicMock,
    ) -> None:
        """Verify task does not finalize recent sleep sessions."""
        user_id = str(uuid4())
        recent_timestamp = datetime.now(timezone.utc) - timedelta(minutes=30)

        mock_session_local.return_value.__enter__ = MagicMock(return_value=db)
        mock_session_local.return_value.__exit__ = MagicMock(return_value=None)
        mock_iter_active.return_value = [user_id]
        mock_load_state.return_value = _state(recent_timestamp)

        finalize_stale_sleeps()

        mock_load_state.assert_called_once_with(db, user_id)
        mock_finish_sleep.assert_not_called()

    @patch("app.integrations.celery.tasks.finalize_stale_sleep_task.finish_sleep")
    @patch("app.integrations.celery.tasks.finalize_stale_sleep_task.load_sleep_state")
    @patch("app.integrations.celery.tasks.finalize_stale_sleep_task.user_sleep_lock", _acquired_lock)
    @patch("app.integrations.celery.tasks.finalize_stale_sleep_task.iter_active_user_ids")
    @patch("app.integrations.celery.tasks.finalize_stale_sleep_task.SessionLocal")
    def test_finalize_stale_sleeps_handles_missing_state(
        self,
        mock_session_local: MagicMock,
        mock_iter_active: MagicMock,
        mock_load_state: MagicMock,
        mock_finish_sleep: MagicMock,
        db: Session,
        mock_celery_app: MagicMock,
    ) -> None:
        """Verify task gracefully handles users with no (or malformed) sleep state."""
        user_id = str(uuid4())

        mock_session_local.return_value.__enter__ = MagicMock(return_value=db)
        mock_session_local.return_value.__exit__ = MagicMock(return_value=None)
        mock_iter_active.return_value = [user_id]
        mock_load_state.return_value = None

        result = finalize_stale_sleeps()

        assert result is None
        mock_load_state.assert_called_once_with(db, user_id)
        mock_finish_sleep.assert_not_called()

    @patch("app.integrations.celery.tasks.finalize_stale_sleep_task.finish_sleep")
    @patch("app.integrations.celery.tasks.finalize_stale_sleep_task.load_sleep_state")
    @patch("app.integrations.celery.tasks.finalize_stale_sleep_task.user_sleep_lock", _acquired_lock)
    @patch("app.integrations.celery.tasks.finalize_stale_sleep_task.iter_active_user_ids")
    @patch("app.integrations.celery.tasks.finalize_stale_sleep_task.SessionLocal")
    def test_finalize_stale_sleeps_handles_multiple_users(
        self,
        mock_session_local: MagicMock,
        mock_iter_active: MagicMock,
        mock_load_state: MagicMock,
        mock_finish_sleep: MagicMock,
        db: Session,
        mock_celery_app: MagicMock,
    ) -> None:
        """Verify task processes multiple users with stale sessions."""
        user_id_1 = str(uuid4())
        user_id_2 = str(uuid4())
        user_id_3 = str(uuid4())
        stale_timestamp = datetime.now(timezone.utc) - timedelta(hours=2)

        mock_session_local.return_value.__enter__ = MagicMock(return_value=db)
        mock_session_local.return_value.__exit__ = MagicMock(return_value=None)
        mock_iter_active.return_value = [user_id_1, user_id_2, user_id_3]

        state_1 = _state(stale_timestamp)
        state_3 = _state(stale_timestamp, source_name="iPhone")
        # User 2 has no state and should be skipped.
        mock_load_state.side_effect = [state_1, None, state_3]

        finalize_stale_sleeps()

        assert mock_load_state.call_count == 3
        assert mock_finish_sleep.call_count == 2
        mock_finish_sleep.assert_any_call(db, user_id_1, state_1)
        mock_finish_sleep.assert_any_call(db, user_id_3, state_3)

    @patch("app.integrations.celery.tasks.finalize_stale_sleep_task.log_and_capture_error")
    @patch("app.integrations.celery.tasks.finalize_stale_sleep_task.finish_sleep")
    @patch("app.integrations.celery.tasks.finalize_stale_sleep_task.load_sleep_state")
    @patch("app.integrations.celery.tasks.finalize_stale_sleep_task.user_sleep_lock", _acquired_lock)
    @patch("app.integrations.celery.tasks.finalize_stale_sleep_task.iter_active_user_ids")
    @patch("app.integrations.celery.tasks.finalize_stale_sleep_task.SessionLocal")
    def test_finalize_stale_sleeps_handles_finish_error(
        self,
        mock_session_local: MagicMock,
        mock_iter_active: MagicMock,
        mock_load_state: MagicMock,
        mock_finish_sleep: MagicMock,
        mock_log_error: MagicMock,
        db: Session,
        mock_celery_app: MagicMock,
    ) -> None:
        """Verify task continues processing other users if one finalization fails."""
        user_id_1 = str(uuid4())
        user_id_2 = str(uuid4())
        stale_timestamp = datetime.now(timezone.utc) - timedelta(hours=2)

        mock_session_local.return_value.__enter__ = MagicMock(return_value=db)
        mock_session_local.return_value.__exit__ = MagicMock(return_value=None)
        mock_iter_active.return_value = [user_id_1, user_id_2]

        state_1 = _state(stale_timestamp)
        state_2 = _state(stale_timestamp, source_name="iPhone")
        mock_load_state.side_effect = [state_1, state_2]
        mock_finish_sleep.side_effect = [Exception("Database error"), None]

        finalize_stale_sleeps()

        assert mock_finish_sleep.call_count == 2
        mock_log_error.assert_called_once()
        mock_finish_sleep.assert_any_call(db, user_id_2, state_2)
