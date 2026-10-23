"""Regression for #1825: a dead OAuth connection was reported as SKIPPED, not FAILED.

Both scenarios run a Whoop ``workout.updated`` delivery through the real
``process_webhook_push`` task (handler -> loader -> api_client token check ->
sync-log status mapping) against the test DB. Only the HTTP call to the Whoop
API and the sync-log sink are replaced.

- legit:  token is valid, Whoop returns a workout that is not scored yet.
          Nothing to save -> SKIPPED, and the connection is stamped as synced.
- dead:   token expired and no refresh token is stored. The fetch error reaches
          the task, so the delivery is FAILED (not retried), last_synced_at keeps
          its old value and the connection is revoked so the integrator is told
          to reconnect.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

import app.integrations.celery.tasks.webhook_push_task as task
from app.schemas.auth import ConnectionStatus
from app.schemas.sync_status import SyncStatus
from app.services.providers.factory import ProviderFactory
from tests.factories import UserConnectionFactory

WHOOP_USER_ID = 424242


def _whoop_connection(**overrides: Any) -> Any:
    return UserConnectionFactory(
        provider="whoop",
        provider_user_id=str(WHOOP_USER_ID),
        last_synced_at=datetime.now(timezone.utc) - timedelta(days=21),
        **overrides,
    )


def _http_client_returning(body: dict) -> MagicMock:
    response = httpx.Response(200, json=body, request=httpx.Request("GET", "https://api.prod.whoop.com/x"))
    client = MagicMock()
    client.__enter__.return_value.request.return_value = response
    return client


def _unscored_workout() -> dict:
    now = datetime.now(timezone.utc)
    return {
        "id": str(uuid4()),
        "user_id": WHOOP_USER_ID,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "start": (now - timedelta(hours=1)).isoformat(),
        "end": now.isoformat(),
        "score_state": "PENDING_SCORE",
        "score": None,
    }


def _run_webhook(db: Session, http_client: MagicMock | None = None) -> tuple[dict, list[dict], bool]:
    """Run one workout.updated delivery through process_webhook_push on the test session."""
    payload = {"user_id": WHOOP_USER_ID, "id": str(uuid4()), "type": "workout.updated"}
    emitted: list[dict] = []
    with (
        patch.object(task, "SessionLocal") as session_local,
        patch("app.services.providers.api_client.httpx.Client", return_value=http_client or MagicMock()) as client,
        patch("app.services.providers.templates.base_oauth.on_connection_revoked"),
        patch.object(
            task.sync_status_service, "emit_webhook_delivered", side_effect=lambda *a, **kw: emitted.append(kw)
        ),
    ):
        session_local.return_value.__enter__.return_value = db
        result = task.process_webhook_push.run("whoop", payload, "repro-1825")
    return result, emitted, client.called


def test_legit_skipped_unscored_workout(db: Session) -> None:
    connection = _whoop_connection()
    before = connection.last_synced_at

    result, emitted, http_called = _run_webhook(db, _http_client_returning(_unscored_workout()))
    db.refresh(connection)

    assert http_called is True
    assert result["records_saved"] == 0
    assert emitted[0]["status"] == SyncStatus.SKIPPED
    assert connection.last_synced_at > before
    assert connection.status == ConnectionStatus.ACTIVE


def test_dead_connection_fails_and_is_revoked(db: Session) -> None:
    connection = _whoop_connection(
        refresh_token=None,
        token_expires_at=datetime.now(timezone.utc) - timedelta(days=20),
    )
    before = connection.last_synced_at

    result, emitted, http_called = _run_webhook(db)
    db.refresh(connection)

    assert http_called is False
    assert result["status"] == "error"
    assert emitted[0]["status"] == SyncStatus.FAILED
    assert "reconnection required" in emitted[0]["error"]
    assert connection.last_synced_at == before
    assert connection.status == ConnectionStatus.REVOKED


def test_workout_fetch_error_propagates(db: Session) -> None:
    """A failed fetch is not "nothing to save": it must reach the task to fail or retry."""
    connection = _whoop_connection()
    workouts = ProviderFactory().get_provider("whoop").webhooks.workouts
    with (
        patch.object(workouts, "get_workout_detail_from_api", side_effect=HTTPException(status_code=503)),
        pytest.raises(HTTPException),
    ):
        workouts.load_single_workout(db, connection.user_id, str(uuid4()))


def test_unparseable_workout_is_skipped(db: Session) -> None:
    """A record that cannot be parsed is skipped, not raised."""
    connection = _whoop_connection()
    workouts = ProviderFactory().get_provider("whoop").webhooks.workouts
    with patch.object(workouts, "get_workout_detail_from_api", return_value={"id": "broken"}):
        assert workouts.load_single_workout(db, connection.user_id, "broken") == 0
