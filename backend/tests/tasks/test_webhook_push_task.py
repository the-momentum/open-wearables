"""Tests for webhook → sync-log instrumentation in process_webhook_push.

The new-vs-updated split is derived centrally: a provider only has to return a
WriteCounts as its count, and the task surfaces the split — no per-provider
plumbing. Saves become SUCCESS runs, errors FAILED, no-ops SKIPPED, and
deliveries with no resolvable user (or from self-reporting Garmin) are dropped.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import ANY, MagicMock, patch
from uuid import UUID, uuid4

import pytest

import app.integrations.celery.tasks.webhook_push_task as task
from app.repositories.data_point_series_repository import WriteCounts
from app.schemas.sync_status import SyncStatus
from app.utils.exceptions import ReauthRequiredError


@pytest.fixture
def user_id() -> str:
    return str(uuid4())


def _capture() -> tuple[list[dict], Any]:
    calls: list[dict] = []

    def fake(uid: Any, provider: str, **kw: Any) -> None:
        calls.append({"provider": provider, "user_id": str(uid), **kw})

    return calls, fake


def test_writecounts_split_surfaces_without_explicit_keys(user_id: str) -> None:
    """A WriteCounts count yields the new/updated split centrally (no records_inserted keys)."""
    calls, fake = _capture()
    with patch.object(task.sync_status_service, "emit_webhook_delivered", side_effect=fake):
        task._emit_webhook_sync_status(
            "oura",
            {
                "status": "processed",
                "data_type": "daily_activity",
                "records_saved": WriteCounts(0, 3),
                "user_id": user_id,
            },
        )
    assert len(calls) == 1
    c = calls[0]
    assert c["status"] == SyncStatus.SUCCESS
    assert c["items_processed"] == 3
    assert c["metadata"] == {"inserted": 0, "updated": 3}
    assert c["message"] == "webhook 0 new, 3 updated"


def test_plain_int_count_has_no_breakdown(user_id: str) -> None:
    """Workout-style providers returning a plain int still log a success run, no split."""
    calls, fake = _capture()
    with patch.object(task.sync_status_service, "emit_webhook_delivered", side_effect=fake):
        task._emit_webhook_sync_status("strava", {"status": "processed", "records_saved": 2, "user_id": user_id})
    assert calls[0]["status"] == SyncStatus.SUCCESS
    assert calls[0]["items_processed"] == 2
    assert calls[0]["metadata"] is None


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        ({"status": "error", "error": "boom"}, SyncStatus.FAILED),
        ({"status": "ignored", "reason": "duplicate_activity"}, SyncStatus.SKIPPED),
        ({"status": "processed", "records_saved": 0}, SyncStatus.SKIPPED),  # saved nothing
    ],
)
def test_status_mapping(result: dict, expected: SyncStatus, user_id: str) -> None:
    calls, fake = _capture()
    with patch.object(task.sync_status_service, "emit_webhook_delivered", side_effect=fake):
        task._emit_webhook_sync_status("oura", {**result, "user_id": user_id})
    assert calls[0]["status"] == expected


def test_no_user_resolved_is_dropped() -> None:
    """user_not_found / invalid payloads carry no user_id → nothing to attribute."""
    calls, fake = _capture()
    with patch.object(task.sync_status_service, "emit_webhook_delivered", side_effect=fake):
        task._emit_webhook_sync_status("oura", {"status": "user_not_found", "oura_user_id": "x"})
    assert calls == []


def test_self_reporting_provider_excluded(user_id: str) -> None:
    """Garmin reports its own sync status; the shared task must not duplicate it."""
    calls, fake = _capture()
    with patch.object(task.sync_status_service, "emit_webhook_delivered", side_effect=fake):
        task._emit_webhook_sync_status("garmin", {"status": "processed", "saved_count": 9, "user_id": user_id})
    assert calls == []


def test_emission_never_raises() -> None:
    """Sync-log emission must never break webhook processing."""
    calls, fake = _capture()
    with patch.object(task.sync_status_service, "emit_webhook_delivered", side_effect=fake):
        task._emit_webhook_sync_status("oura", None)
        task._emit_webhook_sync_status("oura", {"status": "processed", "records_saved": 1, "user_id": "not-a-uuid"})
    assert calls == []


def test_reauth_required_fails_delivery_without_retry(user_id: str) -> None:
    """A dead grant raised out of the handler is logged FAILED and not retried."""
    calls, fake = _capture()
    handler = MagicMock()
    handler.extract_user_id.return_value = "athlete-1"
    handler.process_payload.side_effect = ReauthRequiredError("strava", UUID(user_id), "reconnection required")
    with (
        patch.object(task, "SessionLocal"),
        patch.object(task, "ProviderFactory") as factory,
        patch.object(task.process_webhook_push, "retry") as retry,
        patch.object(task.sync_status_service, "emit_webhook_delivered", side_effect=fake),
    ):
        factory.return_value.get_provider.return_value.webhooks = handler
        result = task.process_webhook_push.run("strava", {}, "trace")

    retry.assert_not_called()
    assert result == {"status": "error", "error": "reconnection required", "user_id": user_id}
    assert calls[0]["status"] == SyncStatus.FAILED


@pytest.mark.parametrize(("retries", "expect_failed"), [(0, False), (3, True)])
def test_failed_run_logged_only_when_retries_run_out(retries: int, expect_failed: bool, user_id: str) -> None:
    """A retriable error logs nothing until the last attempt, which is logged FAILED."""
    calls, fake = _capture()
    handler = MagicMock()
    handler.extract_user_id.return_value = "athlete-1"
    handler.process_payload.side_effect = RuntimeError("upstream timeout")
    handler.find_connection.return_value = MagicMock(user_id=UUID(user_id))
    with (
        patch.object(task, "SessionLocal"),
        patch.object(task, "ProviderFactory") as factory,
        patch.object(task.process_webhook_push, "retry", side_effect=RuntimeError("retry")),
        patch.object(task.sync_status_service, "emit_webhook_delivered", side_effect=fake),
    ):
        factory.return_value.get_provider.return_value.webhooks = handler
        task.process_webhook_push.push_request(retries=retries)
        try:
            with pytest.raises(RuntimeError, match="retry"):
                task.process_webhook_push.run("strava", {}, "trace")
        finally:
            task.process_webhook_push.pop_request()

    if expect_failed:
        handler.find_connection.assert_called_once_with(ANY, "athlete-1")
        assert calls[0]["status"] == SyncStatus.FAILED
        assert calls[0]["error"] == "RuntimeError"
    else:
        assert calls == []
