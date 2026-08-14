"""
Tests for durable sync run storage.

Covers the emit() hook that writes runs to Postgres: the historical-only default,
the live opt-in, insert on start then update on terminal, and that a storage failure
cannot break the sync it is tracking.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models import SyncRun, SyncRunDataType
from app.schemas.enums import SeriesType
from app.schemas.sync_status import (
    DataTypeKind,
    DataTypeOutcome,
    SyncScope,
    SyncSource,
    SyncStage,
    SyncStatus,
    SyncStatusEvent,
)
from app.integrations.celery.tasks.close_stale_sync_runs_task import close_stale_sync_runs
from app.services.sync_status_service import try_persist_run, try_record_data_types
from tests.factories import UserFactory


def _event(user_id, **overrides) -> SyncStatusEvent:
    defaults = {
        "run_id": f"pull_{uuid4().hex[:16]}",
        "user_id": user_id,
        "provider": "oura",
        "source": SyncSource.PULL,
        "scope": SyncScope.HISTORICAL,
        "stage": SyncStage.STARTED,
        "status": SyncStatus.IN_PROGRESS,
        "started_at": datetime.now(timezone.utc),
    }
    return SyncStatusEvent(**{**defaults, **overrides})


class TestTryPersistRun:
    @patch("app.services.sync_status_service.SessionLocal")
    def test_historical_run_is_stored(self, mock_session_local: MagicMock, db: Session) -> None:
        mock_session_local.return_value.__enter__.return_value = db
        user = UserFactory()
        event = _event(user.id)

        try_persist_run(event)

        run = db.query(SyncRun).filter(SyncRun.run_key == event.run_id).one()
        assert run.scope == SyncScope.HISTORICAL
        assert run.status == SyncStatus.IN_PROGRESS
        assert run.ended_at is None

    @patch("app.services.sync_status_service.SessionLocal")
    def test_live_run_is_skipped_by_default(self, mock_session_local: MagicMock, db: Session) -> None:
        """Live runs are one row per webhook or batch, so they are opt-in."""
        mock_session_local.return_value.__enter__.return_value = db
        user = UserFactory()
        event = _event(user.id, scope=SyncScope.LIVE)

        try_persist_run(event)

        assert db.query(SyncRun).filter(SyncRun.run_key == event.run_id).one_or_none() is None

    @patch("app.services.sync_status_service.settings")
    @patch("app.services.sync_status_service.SessionLocal")
    def test_live_run_stored_when_opted_in(
        self, mock_session_local: MagicMock, mock_settings: MagicMock, db: Session
    ) -> None:
        mock_session_local.return_value.__enter__.return_value = db
        mock_settings.sync_run_tracking_enabled = True
        mock_settings.sync_run_persist_live = True
        user = UserFactory()
        event = _event(user.id, scope=SyncScope.LIVE)

        try_persist_run(event)

        assert db.query(SyncRun).filter(SyncRun.run_key == event.run_id).one().scope == SyncScope.LIVE

    @patch("app.services.sync_status_service.settings")
    @patch("app.services.sync_status_service.SessionLocal")
    def test_tracking_disabled_stores_nothing(
        self, mock_session_local: MagicMock, mock_settings: MagicMock, db: Session
    ) -> None:
        mock_session_local.return_value.__enter__.return_value = db
        mock_settings.sync_run_tracking_enabled = False
        user = UserFactory()
        event = _event(user.id)

        try_persist_run(event)

        assert db.query(SyncRun).filter(SyncRun.run_key == event.run_id).one_or_none() is None

    @patch("app.services.sync_status_service.SessionLocal")
    def test_terminal_event_updates_the_same_row(self, mock_session_local: MagicMock, db: Session) -> None:
        """Both events share a run_id, so the run must end up as one row."""
        mock_session_local.return_value.__enter__.return_value = db
        user = UserFactory()
        started_at = datetime.now(timezone.utc)
        run_id = f"pull_{uuid4().hex[:16]}"

        try_persist_run(_event(user.id, run_id=run_id, started_at=started_at))
        try_persist_run(
            _event(
                user.id,
                run_id=run_id,
                stage=SyncStage.COMPLETED,
                status=SyncStatus.SUCCESS,
                started_at=started_at,
                ended_at=started_at + timedelta(seconds=30),
                metadata={"inserted": 120, "updated": 5},
            )
        )

        run = db.query(SyncRun).filter(SyncRun.run_key == run_id).one()
        assert run.status == SyncStatus.SUCCESS
        assert run.ended_at is not None
        assert (run.items_inserted, run.items_updated) == (120, 5)
        # started_at describes the run's intent and must survive the update
        assert run.started_at == started_at

    @patch("app.services.sync_status_service.SessionLocal")
    def test_storage_failure_does_not_raise(self, mock_session_local: MagicMock, db: Session) -> None:
        """A sync must not fail because run tracking did."""
        mock_session_local.side_effect = RuntimeError("db gone")

        try_persist_run(_event(uuid4()))


class TestTryRecordDataTypes:
    @patch("app.services.sync_status_service.SessionLocal")
    def test_outcomes_are_stored_against_the_run(self, mock_session_local: MagicMock, db: Session) -> None:
        mock_session_local.return_value.__enter__.return_value = db
        user = UserFactory()
        event = _event(user.id)
        try_persist_run(event)

        try_record_data_types(
            event.run_id,
            [
                DataTypeOutcome(
                    data_type="heart_rate",
                    kind=DataTypeKind.SERIES,
                    status=SyncStatus.SUCCESS,
                    items_inserted=100,
                    items_updated=3,
                ),
                DataTypeOutcome(
                    data_type="spo2",
                    kind=DataTypeKind.TASK,
                    status=SyncStatus.FAILED,
                    error="authorization_denied",
                ),
            ],
        )

        rows = {r.data_type: r for r in db.query(SyncRunDataType).all()}
        assert rows["heart_rate"].items_inserted == 100
        assert rows["heart_rate"].series_type == SeriesType.heart_rate
        assert rows["spo2"].status == SyncStatus.FAILED
        # spo2 is a provider task name, not a series type
        assert rows["spo2"].series_type is None

    @patch("app.services.sync_status_service.SessionLocal")
    def test_repeated_outcomes_accumulate(self, mock_session_local: MagicMock, db: Session) -> None:
        """Several batches of one type fold into a single row with a widening range."""
        mock_session_local.return_value.__enter__.return_value = db
        user = UserFactory()
        event = _event(user.id)
        try_persist_run(event)

        early = datetime(2026, 1, 1, tzinfo=timezone.utc)
        late = datetime(2026, 6, 1, tzinfo=timezone.utc)
        for covered_start, covered_end, inserted in ((late, late, 10), (early, early, 5)):
            try_record_data_types(
                event.run_id,
                [
                    DataTypeOutcome(
                        data_type="steps",
                        kind=DataTypeKind.SERIES,
                        status=SyncStatus.SUCCESS,
                        items_inserted=inserted,
                        covered_start=covered_start,
                        covered_end=covered_end,
                    )
                ],
            )

        row = db.query(SyncRunDataType).filter(SyncRunDataType.data_type == "steps").one()
        assert row.items_inserted == 15
        assert row.covered_start == early
        assert row.covered_end == late
        assert row.attempt == 2

    @patch("app.services.sync_status_service.SessionLocal")
    def test_no_run_row_means_no_op(self, mock_session_local: MagicMock, db: Session) -> None:
        """Live syncs are not persisted, so their outcomes have nowhere to go."""
        mock_session_local.return_value.__enter__.return_value = db

        try_record_data_types(
            "pull_does_not_exist",
            [DataTypeOutcome(data_type="steps", kind=DataTypeKind.SERIES, status=SyncStatus.SUCCESS)],
        )

        assert db.query(SyncRunDataType).count() == 0


class TestCloseStaleSyncRuns:
    @patch("app.integrations.celery.tasks.close_stale_sync_runs_task.SessionLocal")
    @patch("app.services.sync_status_service.SessionLocal")
    def test_only_old_in_progress_runs_are_closed(
        self, mock_emit_session: MagicMock, mock_task_session: MagicMock, db: Session
    ) -> None:
        """Unknown rather than failed: the run never reported what happened."""
        mock_emit_session.return_value.__enter__.return_value = db
        mock_task_session.return_value.__enter__.return_value = db
        user = UserFactory()
        old = datetime.now(timezone.utc) - timedelta(hours=48)

        try_persist_run(_event(user.id, run_id="pull_stale", started_at=old))
        try_persist_run(_event(user.id, run_id="pull_recent"))

        result = close_stale_sync_runs()

        assert result["run_keys"] == ["pull_stale"]
        assert db.query(SyncRun).filter(SyncRun.run_key == "pull_stale").one().status == SyncStatus.UNKNOWN
        assert db.query(SyncRun).filter(SyncRun.run_key == "pull_recent").one().status == SyncStatus.IN_PROGRESS
