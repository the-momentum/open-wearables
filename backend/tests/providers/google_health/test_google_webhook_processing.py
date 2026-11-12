"""Processing Google Health notify-only webhook batches."""

from typing import Any
from unittest.mock import MagicMock, patch

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


def test_failed_write_resets_an_unusable_session() -> None:
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


def test_healthy_session_is_not_rolled_back() -> None:
    """A non-database failure must not discard pending writes from earlier batch items."""
    handler = _handler()
    handler.workouts.load_data.side_effect = RuntimeError("Google API 500")
    db = MagicMock()
    db.is_active = True

    with patch.object(webhook_handler, "log_and_capture_error"):
        handler.process_payload(db, [_notification("known")], "trace")

    db.rollback.assert_not_called()


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
