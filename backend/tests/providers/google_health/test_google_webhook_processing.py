"""Processing Google Health notify-only webhook batches."""

from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

from sqlalchemy import text
from sqlalchemy.orm import Session

import app.integrations.celery.tasks.webhook_push_task as task
from app.schemas.sync_status import SyncStatus
from app.services.providers.google_health import webhook_handler
from app.services.providers.google_health.helpers import physical_interval
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

    with patch.object(webhook_handler.logger, "error"):
        result = handler.process_payload(MagicMock(), [_notification("known"), _notification("ghost")], "trace")

    failed, not_found = result["results"]
    assert failed == {"status": "error", "error": "Google API 500", "data_type": "exercise", "user_id": USER_ID}
    assert not_found["status"] == "user_not_found"
    assert "user_id" not in not_found
    handler.connection_repo.advance_last_synced_at.assert_not_called()


def test_failed_write_rolls_back_an_unusable_session() -> None:
    """A broken session must be rolled back so the task's final commit and sync-status emit still run."""
    handler = _handler()
    handler.workouts.load_data.side_effect = RuntimeError("Google API 500")
    db = MagicMock()
    db.is_active = False

    with patch.object(webhook_handler.logger, "error"):
        result = handler.process_payload(db, [_notification("known")], "trace")

    db.rollback.assert_called_once()
    assert result["results"][0]["status"] == "error"
    assert result["results"][0]["user_id"] == USER_ID


def test_each_item_commits_and_failures_roll_back_only_their_own_work() -> None:
    """Per-item commit means a failed notification can't take earlier writes down with it."""
    handler = _handler()
    handler.workouts.load_data.side_effect = [3, RuntimeError("Google API 500")]
    db = MagicMock()

    with patch.object(webhook_handler.logger, "error"):
        result = handler.process_payload(db, [_notification("known"), _notification("known")], "trace")

    assert result["results"][0]["status"] == "processed"
    assert result["results"][1]["status"] == "error"
    db.commit.assert_called_once()
    db.rollback.assert_called_once()
    # last_synced_at is the pull cursor: only the successful fetch may stamp it.
    handler.connection_repo.advance_last_synced_at.assert_called_once()


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

    with patch.object(webhook_handler.logger, "error"):
        result = handler.process_payload(db, [_notification("known"), _notification("known")], "trace")

    failed, recovered = result["results"]
    assert failed["status"] == "error"
    assert failed["user_id"] == USER_ID
    assert recovered["status"] == "processed"
    assert recovered["records_saved"] == 3
    assert db.execute(text("SELECT 1")).scalar() == 1


def test_an_instant_interval_is_widened_into_a_fetchable_window() -> None:
    """Instant records (blood-glucose & co.) notify startTime == endTime; the Health API
    400s on a zero-length filter (INVALID_TIME_RANGE), so the window must be widened."""
    handler = _handler()
    instant = {
        "data": {
            "healthUserId": "known",
            "operation": "UPSERT",
            "dataType": "blood-glucose",
            "intervals": [
                {
                    "physicalTimeInterval": {
                        "startTime": "2026-11-12T08:00:00Z",
                        "endTime": "2026-11-12T08:00:00Z",
                    }
                }
            ],
        }
    }
    handler.data_247.sync_data_type.return_value = 5

    result = handler.process_payload(MagicMock(), [instant], "trace")

    assert result["results"][0]["status"] == "processed"
    start, end = handler.data_247.sync_data_type.call_args.args[3:5]
    point = datetime(2026, 11, 12, 8, 0, tzinfo=timezone.utc)
    assert start < point < end


def test_a_subsecond_interval_is_widened_into_a_fetchable_window() -> None:
    """Instant notifications can arrive as a sub-second span; it slips past the
    ``end <= start`` check but the emitted filter truncates to whole seconds and
    still 400s, so the window must be widened the same way."""
    handler = _handler()
    instant = {
        "data": {
            "healthUserId": "known",
            "operation": "UPSERT",
            "dataType": "blood-glucose",
            "intervals": [
                {
                    "physicalTimeInterval": {
                        "startTime": "2026-11-12T08:00:00.000Z",
                        "endTime": "2026-11-12T08:00:00.999Z",
                    }
                }
            ],
        }
    }
    handler.data_247.sync_data_type.return_value = 5

    result = handler.process_payload(MagicMock(), [instant], "trace")

    assert result["results"][0]["status"] == "processed"
    start, end = handler.data_247.sync_data_type.call_args.args[3:5]
    point = datetime(2026, 11, 12, 8, 0, 0, 500000, tzinfo=timezone.utc)
    assert start < point < end


def test_physical_interval_never_emits_a_collapsed_window() -> None:
    """``to_rfc3339`` truncates to whole seconds, so the Health API sees equal
    bounds — and 400s — for any span under a second; the end must be lifted."""
    cases = [
        # (start, end)
        (datetime(2026, 11, 12, 8, 0, 0, tzinfo=timezone.utc),) * 2,  # instant
        (
            datetime(2026, 11, 12, 8, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 11, 12, 8, 0, 0, 500000, tzinfo=timezone.utc),
        ),  # sub-second
        (
            datetime(2026, 11, 12, 8, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 11, 12, 8, 0, 0, 1, tzinfo=timezone.utc),
        ),  # one microsecond — the smallest positive span
        (
            datetime(2026, 11, 12, 8, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 11, 12, 7, 59, 0, tzinfo=timezone.utc),
        ),  # inverted
    ]
    for start, end in cases:
        window = physical_interval(start, end)
        assert window["endTime"] > window["startTime"], (start, end)


def test_failure_log_message_is_stable_for_grouping() -> None:
    handler = _handler()
    handler.workouts.load_data.side_effect = RuntimeError("Google API 500")

    with patch.object(webhook_handler.logger, "error") as capture:
        handler.process_payload(MagicMock(), [_notification("known")], "trace")

    assert capture.call_args.args[0] == "Google webhook notification failed"


def test_fetch_failure_emits_a_failed_sync_run() -> None:
    handler = _handler()
    handler.workouts.load_data.side_effect = RuntimeError("Google API 500")
    with patch.object(webhook_handler.logger, "error"):
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
