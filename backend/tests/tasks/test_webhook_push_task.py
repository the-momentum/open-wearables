"""Tests for webhook → sync-log instrumentation in process_webhook_push.

The new-vs-updated split is derived centrally: a provider only has to return a
WriteCounts as its count, and the task surfaces the split — no per-provider
plumbing. Saves become SUCCESS runs, errors FAILED, no-ops SKIPPED, and
deliveries with no resolvable user (or from self-reporting Garmin) are dropped.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from celery.exceptions import Retry
from psycopg.errors import CheckViolation, ForeignKeyViolation, NotNullViolation
from sqlalchemy.exc import IntegrityError

import app.integrations.celery.tasks.webhook_push_task as task
from app.repositories.data_point_series_repository import WriteCounts
from app.schemas.sync_status import SyncStatus
from app.utils.exceptions import (
    AppError,
    NotFoundError,
    ProviderError,
    ProviderNotConnectedError,
    ProviderRateLimitError,
    ProviderReauthorizationRequiredError,
)


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


def _run_with_failing_handler(exc: Exception) -> dict[str, Any]:
    handler = MagicMock()
    handler.extract_user_id.return_value = "provider-user"
    handler.process_payload.side_effect = exc
    with (
        patch.object(task, "ProviderFactory") as factory,
        patch.object(task, "SessionLocal", MagicMock()),
        patch.object(task.process_webhook_push, "retry", side_effect=Retry()),
    ):
        factory.return_value.get_provider.return_value.webhooks = handler
        return task.process_webhook_push.run("oura", {}, "trace-1")


@pytest.mark.parametrize(
    "exc",
    [
        IntegrityError("stmt", {}, ForeignKeyViolation("user deleted meanwhile")),
        ForeignKeyViolation("raw psycopg, from a COPY"),
        NotFoundError("User not found."),
    ],
)
def test_own_client_errors_are_dropped_not_retried(exc: Exception) -> None:
    result = _run_with_failing_handler(exc)

    assert result == {"status": "skipped", "reason": "non_retriable", "error_type": type(exc).__name__}


@pytest.mark.parametrize(
    "exc",
    [
        AppError("broken invariant"),
        RuntimeError("database down"),
    ],
)
def test_server_errors_are_retried(exc: Exception) -> None:
    with pytest.raises(Retry):
        _run_with_failing_handler(exc)


@pytest.mark.parametrize("upstream_status", [400, 403, 404, 410, 422])
def test_upstream_client_errors_are_dropped_not_retried(upstream_status: int) -> None:
    """A deleted or unqueryable object at the provider fails the same way on every attempt."""
    result = _run_with_failing_handler(ProviderError("oura", upstream_status=upstream_status))

    assert result == {"status": "skipped", "reason": "upstream_non_retriable", "upstream_status": upstream_status}


@pytest.mark.parametrize(
    "exc",
    [
        ProviderError("oura", upstream_status=500),
        ProviderError("oura"),  # no response: timeout, connection reset
        ProviderRateLimitError("oura", upstream_status=429),
    ],
)
def test_upstream_outages_are_retried(exc: ProviderError) -> None:
    with pytest.raises(Retry):
        _run_with_failing_handler(exc)


@pytest.mark.parametrize(("upstream_status", "alerted"), [(400, True), (422, True), (404, False), (410, False)])
def test_only_a_request_the_provider_refused_alerts_when_skipped(upstream_status: int, alerted: bool) -> None:
    """A 400 or 422 is most likely our bug; a deleted object at the provider is not."""
    with patch.object(task, "logger") as logger:
        _run_with_failing_handler(ProviderError("oura", upstream_status=upstream_status))

    assert logger.warning.call_args.kwargs["alert"] is alerted


def test_last_failed_attempt_alerts_that_the_payload_is_lost() -> None:
    task.process_webhook_push.push_request(retries=task.process_webhook_push.max_retries)
    try:
        with patch.object(task, "logger") as logger, pytest.raises(Retry):
            _run_with_failing_handler(ProviderError("oura", upstream_status=503))
    finally:
        task.process_webhook_push.pop_request()

    assert logger.warning.call_args.args[0] == "Webhook push task failed upstream, giving up"
    assert logger.warning.call_args.kwargs["alert"] is True


def test_earlier_failed_attempts_do_not_alert() -> None:
    with patch.object(task, "logger") as logger, pytest.raises(Retry):
        _run_with_failing_handler(ProviderError("oura", upstream_status=503))

    assert logger.warning.call_args.args[0] == "Webhook push task failed, scheduling retry"
    assert "alert" not in logger.warning.call_args.kwargs


@pytest.mark.parametrize(
    "exc",
    [
        ProviderReauthorizationRequiredError("oura"),
        ProviderNotConnectedError("oura"),
    ],
)
def test_unusable_connection_is_dropped_not_retried(exc: Exception) -> None:
    """No retry gets past a revoked grant or a missing connection: only the user can fix it."""
    result = _run_with_failing_handler(exc)

    assert result == {"status": "skipped", "reason": "non_retriable", "error_type": type(exc).__name__}


@pytest.mark.parametrize(
    ("exc", "violation"),
    [
        (IntegrityError("INSERT ...", {"heart_rate": 187}, NotNullViolation("not null")), "NotNullViolation"),
        (CheckViolation("raw psycopg, from a COPY"), "CheckViolation"),
    ],
)
def test_own_constraint_bug_fails_without_retry(exc: Exception, violation: str) -> None:
    """Retrying the same payload violates the constraint again; raising gets it to Sentry."""
    with patch.object(task, "logger") as logger, pytest.raises(type(exc)):
        _run_with_failing_handler(exc)

    kwargs = logger.error.call_args.kwargs
    assert kwargs["error_type"] == violation
    assert "187" not in str(kwargs)


def test_skipped_integrity_error_is_logged_without_the_payloads_values() -> None:
    """The message of an IntegrityError carries the statement's parameters, i.e. health data."""
    exc = IntegrityError("INSERT ...", {"heart_rate": 187}, ForeignKeyViolation("fk"))

    with patch.object(task, "logger") as logger:
        _run_with_failing_handler(exc)

    kwargs = logger.warning.call_args.kwargs
    assert kwargs["error_type"] == "ForeignKeyViolation"
    assert "exc_info" not in kwargs
    assert "187" not in str(kwargs)
