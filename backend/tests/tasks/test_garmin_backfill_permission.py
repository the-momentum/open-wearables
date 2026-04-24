"""Tests for Garmin backfill permission checking.

Verifies that start_full_backfill skips when the user has not granted
HISTORICAL_DATA_EXPORT in their Garmin connection scope.
"""

from collections.abc import Generator
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.integrations.celery.tasks.garmin.backfill_task import start_full_backfill

MODULE = "app.integrations.celery.tasks.garmin.backfill_task"
TRIGGER_MODULE = "app.integrations.celery.tasks.garmin.backfill_trigger"


def _make_connection(scope: str | None) -> MagicMock:
    conn = MagicMock()
    conn.scope = scope
    return conn


@pytest.fixture
def _patch_redis() -> Generator[MagicMock, None, None]:
    with patch(f"{MODULE}.get_redis_client") as mock_get:
        mock = mock_get.return_value
        mock.get.return_value = None
        yield mock


@pytest.fixture
def _patch_session() -> Generator[MagicMock, None, None]:
    mock_db = MagicMock()
    with patch(f"{MODULE}.SessionLocal") as mock:
        mock.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock.return_value.__exit__ = MagicMock(return_value=None)
        yield mock


class TestBackfillPermissionCheck:
    """Ensure start_full_backfill respects HISTORICAL_DATA_EXPORT scope."""

    @patch(f"{MODULE}.UserConnectionRepository")
    @pytest.mark.usefixtures("_patch_redis", "_patch_session")
    def test_skips_without_historical_data_export(self, mock_repo_cls: MagicMock) -> None:
        mock_repo_cls.return_value.get_by_user_and_provider.return_value = _make_connection(
            "ACTIVITY_EXPORT HEALTH_EXPORT"
        )

        result = start_full_backfill(str(uuid4()))

        assert result["status"] == "skipped"
        assert "HISTORICAL_DATA_EXPORT" in result["reason"]

    @patch(f"{MODULE}.UserConnectionRepository")
    @pytest.mark.usefixtures("_patch_redis", "_patch_session")
    def test_proceeds_when_scope_is_none(self, mock_repo_cls: MagicMock) -> None:
        """scope=None means permissions fetch failed during OAuth — treat as unknown and proceed."""
        mock_repo_cls.return_value.get_by_user_and_provider.return_value = _make_connection(None)

        with (
            patch(f"{MODULE}.acquire_backfill_lock", return_value=True),
            patch(f"{MODULE}.set_trace_id", return_value="trace-123"),
            patch(f"{MODULE}.get_current_window", return_value=0),
            patch(f"{MODULE}.is_cancelled", return_value=False),
            patch(f"{MODULE}.init_window_state"),
            patch(f"{MODULE}.reset_type_status"),
            patch(f"{MODULE}.trigger_backfill_for_type") as mock_trigger,
        ):
            mock_trigger.apply_async = MagicMock()
            result = start_full_backfill(str(uuid4()))

        assert result["status"] == "started"

    @patch(f"{MODULE}.UserConnectionRepository")
    @pytest.mark.usefixtures("_patch_redis", "_patch_session")
    def test_proceeds_with_historical_data_export(self, mock_repo_cls: MagicMock) -> None:
        mock_repo_cls.return_value.get_by_user_and_provider.return_value = _make_connection(
            "ACTIVITY_EXPORT HISTORICAL_DATA_EXPORT"
        )

        with (
            patch(f"{MODULE}.acquire_backfill_lock", return_value=True),
            patch(f"{MODULE}.set_trace_id", return_value="trace-123"),
            patch(f"{MODULE}.get_current_window", return_value=0),
            patch(f"{MODULE}.is_cancelled", return_value=False),
            patch(f"{MODULE}.init_window_state"),
            patch(f"{MODULE}.reset_type_status"),
            patch(f"{MODULE}.trigger_backfill_for_type") as mock_trigger,
        ):
            mock_trigger.apply_async = MagicMock()
            result = start_full_backfill(str(uuid4()))

        assert result["status"] == "started"
