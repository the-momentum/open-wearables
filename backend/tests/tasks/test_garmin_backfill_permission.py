"""Tests for Garmin backfill permission checking.

Verifies that start_full_backfill skips when the user has not granted
HISTORICAL_DATA_EXPORT in their Garmin connection scope.
"""

from collections.abc import Generator
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
import redis
from pytest_mock import MockerFixture
from sqlalchemy.orm import Session

from app.integrations.celery.tasks.garmin.backfill_task import start_full_backfill
from app.models import UserConnection

MODULE = "app.integrations.celery.tasks.garmin.backfill_task"
TRIGGER_MODULE = "app.integrations.celery.tasks.garmin.backfill_trigger"


def _make_connection(scope: str | None) -> UserConnection:
    return UserConnection(scope=scope)


@pytest.fixture
def _patch_redis() -> Generator[MagicMock, None, None]:
    with patch(f"{MODULE}.get_redis_client", autospec=True) as mock_get:
        mock = mock_get.return_value = MagicMock(spec=redis.Redis)
        mock.get.return_value = None
        yield mock


@pytest.fixture
def _patch_session() -> Generator[MagicMock, None, None]:
    mock_db = MagicMock(spec=Session)
    with patch(f"{MODULE}.SessionLocal", autospec=True) as mock:
        mock.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock.return_value.__exit__ = MagicMock(return_value=None)
        yield mock


class TestBackfillPermissionCheck:
    """Ensure start_full_backfill respects HISTORICAL_DATA_EXPORT scope."""

    @pytest.mark.usefixtures("_patch_redis", "_patch_session")
    def test_skips_without_historical_data_export(self, mocker: MockerFixture) -> None:
        mock_repo_cls = mocker.patch(f"{MODULE}.UserConnectionRepository", autospec=True)
        mock_repo_cls.return_value.get_by_user_and_provider.return_value = _make_connection(
            "ACTIVITY_EXPORT HEALTH_EXPORT"
        )

        result = start_full_backfill(str(uuid4()))

        assert result["status"] == "skipped"
        assert "HISTORICAL_DATA_EXPORT" in result["reason"]

    @pytest.mark.usefixtures("_patch_redis", "_patch_session")
    def test_proceeds_when_scope_is_none(self, mocker: MockerFixture) -> None:
        """scope=None means permissions fetch failed during OAuth — treat as unknown and proceed."""
        mock_repo_cls = mocker.patch(f"{MODULE}.UserConnectionRepository", autospec=True)
        mock_repo_cls.return_value.get_by_user_and_provider.return_value = _make_connection(None)

        with (
            patch(f"{MODULE}.acquire_backfill_lock", autospec=True, return_value=True),
            patch(f"{MODULE}.set_trace_id", autospec=True, return_value="trace-123"),
            patch(f"{MODULE}.get_current_window", autospec=True, return_value=0),
            patch(f"{MODULE}.init_window_state", autospec=True),
            patch(f"{MODULE}.reset_type_status", autospec=True),
            patch(f"{MODULE}.trigger_backfill_for_type", autospec=True),
        ):
            result = start_full_backfill(str(uuid4()))

        assert result["status"] == "started"

    @pytest.mark.usefixtures("_patch_redis", "_patch_session")
    def test_proceeds_with_historical_data_export(self, mocker: MockerFixture) -> None:
        mock_repo_cls = mocker.patch(f"{MODULE}.UserConnectionRepository", autospec=True)
        mock_repo_cls.return_value.get_by_user_and_provider.return_value = _make_connection(
            "ACTIVITY_EXPORT HISTORICAL_DATA_EXPORT"
        )

        with (
            patch(f"{MODULE}.acquire_backfill_lock", autospec=True, return_value=True),
            patch(f"{MODULE}.set_trace_id", autospec=True, return_value="trace-123"),
            patch(f"{MODULE}.get_current_window", autospec=True, return_value=0),
            patch(f"{MODULE}.init_window_state", autospec=True),
            patch(f"{MODULE}.reset_type_status", autospec=True),
            patch(f"{MODULE}.trigger_backfill_for_type", autospec=True),
        ):
            result = start_full_backfill(str(uuid4()))

        assert result["status"] == "started"
