"""Processing Google Health notify-only webhook batches."""

from typing import Any
from unittest.mock import MagicMock, patch

from sqlalchemy import text
from sqlalchemy.orm import Session

import app.integrations.celery.tasks.webhook_push_task as task
from app.schemas.sync_status import SyncStatus
from app.services.providers.google_health import webhook_handler
from app.services.providers.google_health.webhook_handler import GoogleWebhookHandler

USER_ID = "xY2kLm9PvQrStUvWzAbC3dEf4gH5"


def _notification(health_user_id: str, data_type: str = "exercise") -> dict[str, Any]:
    return {
        "data": {
            "healthUserId": health_user_id,
            "operation": "UPSERT",
            "dataType": data_type,
            "intervals": [
                {
                    "physicalTimeInterval": {
                        "startTime": "2026-11-12T08:00:00Z",
                        "endTime": "2026-11-12T09:00:00Z",
                    }
                }
            ],
        }
    }


def _handler() -> GoogleWebhookHandler:
    handler = GoogleWebhookHandler(data_247=MagicMock(), workouts=MagicMock())
    handler.connection_repo = MagicMock()
    handler.connection_repo.get_by_provider_user_id.side_effect = lambda db, provider, hid: (
        MagicMock(user_id=USER_ID) if hid == "known" else None
    )
    return handler


def test_fetch_failure_after_user_resolution_is_attributed_to_the_user() -> None:
    handler = _handler()
    handler.workouts.load_data.side_effect = RuntimeError("Google API 500")

    with patch.object(webhook_handler, "log_and_capture_error"):
        result = handler.process_payload(MagicMock(), [_notification("known"), _notification("ghost")], "trace")

    failed, not_found = result["results"]
    assert failed == {"status": "error", "error": "Google API 500", "data_type": "exercise", "user_id": USER_ID}
    assert not_found["status"] == "user_not_found"
    assert "user_id" not in not_found


def test_failed_write_rolls_back_an_unusable_session() -> None:
    """A broken session must be rolled back so the task's final commit and sync-status emit still run."""
    handler = _handler()
    handler.workouts.load_data.side_effect = RuntimeError("Google API 500")
    db = MagicMock()
    db.is_active = False

    with patch.object(webhook_handler, "log_and_capture_error"):
        result = handler.process_payload(db, [_notification("known")], "trace")

    db.rollback.assert_called_once()
    assert result["results"][0]["status"] == "error"
    assert result["results"][0]["user_id"] == USER_ID


def test_each_item_commits_and_failures_roll_back_only_their_own_work() -> None:
    """Per-item commit means a failed notification can't take earlier writes down with it."""
    handler = _handler()
    handler.workouts.load_data.side_effect = [3, RuntimeError("Google API 500")]
    db = MagicMock()

    with patch.object(webhook_handler, "log_and_capture_error"):
        result = handler.process_payload(db, [_notification("known"), _notification("known")], "trace")

    assert result["results"][0]["status"] == "processed"
    assert result["results"][1]["status"] == "error"
    db.commit.assert_called_once()
    db.rollback.assert_called_once()


def test_failed_query_does_not_poison_the_rest_of_the_batch(db: Session) -> None:
    """A failed SQL statement aborts the PG transaction while ``is_active`` stays true;
    the per-item rollback must recover it so later batch items still process."""
    handler = _handler()
    calls = {"count": 0}

    def load_data(db_: Session, user_id: str, **kwargs: Any) -> int:
        calls["count"] += 1
        if calls["count"] == 1:
            db_.execute(text("SELECT * FROM table_that_does_not_exist"))
        # A real query proves the transaction recovered; it would raise
        # InFailedSqlTransaction if the aborted state had leaked through.
        return int(db_.execute(text("SELECT 1")).scalar() or 0) + 2

    handler.workouts.load_data.side_effect = load_data

    with patch.object(webhook_handler, "log_and_capture_error"):
        result = handler.process_payload(db, [_notification("known"), _notification("known")], "trace")

    failed, recovered = result["results"]
    assert failed["status"] == "error"
    assert failed["user_id"] == USER_ID
    assert recovered["status"] == "processed"
    assert recovered["records_saved"] == 3
    assert db.execute(text("SELECT 1")).scalar() == 1


def test_failure_log_message_is_stable_for_grouping() -> None:
    handler = _handler()
    handler.workouts.load_data.side_effect = RuntimeError("Google API 500")

    with patch.object(webhook_handler, "log_and_capture_error") as capture:
        handler.process_payload(MagicMock(), [_notification("known")], "trace")

    assert capture.call_args.args[2] == "Google webhook notification failed"


def test_fetch_failure_emits_a_failed_sync_run() -> None:
    handler = _handler()
    handler.workouts.load_data.side_effect = RuntimeError("Google API 500")
    with patch.object(webhook_handler, "log_and_capture_error"):
        result = handler.process_payload(MagicMock(), [_notification("known")], "trace")

    calls: list[dict[str, Any]] = []
    with patch.object(
        task.sync_status_service,
        "emit_webhook_delivered",
        side_effect=lambda uid, provider, **kw: calls.append({"user_id": uid, **kw}),
    ):
        task._emit_webhook_sync_status("google_health", result)

    assert len(calls) == 1
    assert calls[0]["user_id"] == USER_ID
    assert calls[0]["status"] == SyncStatus.FAILED
    assert calls[0]["error"] == "Google API 500"
