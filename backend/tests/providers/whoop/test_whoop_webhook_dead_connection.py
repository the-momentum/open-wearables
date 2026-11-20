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

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import patch
from uuid import uuid4

import pytest
import respx
from fastapi import HTTPException
from sqlalchemy.orm import Session

import app.integrations.celery.tasks.webhook_push_task as task
from app.schemas.auth import ConnectionStatus
from app.schemas.sync_status import SyncStatus
from app.services.providers.factory import ProviderFactory
from tests.factories import UserConnectionFactory

WHOOP_USER_ID = 424242
WORKOUT_URL = "https://api.prod.whoop.com/developer/v2/activity/workout"


def _whoop_connection(**overrides: Any) -> Any:
    return UserConnectionFactory(
        provider="whoop",
        provider_user_id=str(WHOOP_USER_ID),
        last_synced_at=datetime.now(timezone.utc) - timedelta(days=21),
        **overrides,
    )


def _unscored_workout(workout_id: str) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "id": workout_id,
        "user_id": WHOOP_USER_ID,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "start": (now - timedelta(hours=1)).isoformat(),
        "end": now.isoformat(),
        "score_state": "PENDING_SCORE",
        "score": None,
    }


def _run_webhook(db: Session, workout_id: str) -> tuple[dict, list[dict]]:
    """Run one workout.updated delivery through process_webhook_push on the test session."""
    payload = {"user_id": WHOOP_USER_ID, "id": workout_id, "type": "workout.updated"}
    emitted: list[dict] = []
    with (
        patch.object(task, "SessionLocal", autospec=True) as session_local,
        patch("app.services.providers.templates.base_oauth.on_connection_revoked", autospec=True),
        patch.object(
            task.sync_status_service,
            "emit_webhook_delivered",
            autospec=True,
            side_effect=lambda *a, **kw: emitted.append(kw),
        ),
    ):
        session_local.return_value.__enter__.return_value = db
        result = task.process_webhook_push.run("whoop", payload, "repro-1825")
    return result, emitted


def test_legit_skipped_unscored_workout(respx_mock: respx.MockRouter, db: Session) -> None:
    connection = _whoop_connection()
    before = connection.last_synced_at
    workout_id = str(uuid4())
    route = respx_mock.get(f"{WORKOUT_URL}/{workout_id}").respond(200, json=_unscored_workout(workout_id))

    result, emitted = _run_webhook(db, workout_id)
    db.refresh(connection)

    assert route.call_count == 1
    assert result["records_saved"] == 0
    assert emitted[0]["status"] == SyncStatus.SKIPPED
    assert connection.last_synced_at > before
    assert connection.status == ConnectionStatus.ACTIVE


def test_dead_connection_fails_and_is_revoked(respx_mock: respx.MockRouter, db: Session) -> None:
    connection = _whoop_connection(
        refresh_token=None,
        token_expires_at=datetime.now(timezone.utc) - timedelta(days=20),
    )
    before = connection.last_synced_at
    workout_id = str(uuid4())
    route = respx_mock.get(f"{WORKOUT_URL}/{workout_id}").respond(200, json=_unscored_workout(workout_id))

    result, emitted = _run_webhook(db, workout_id)
    db.refresh(connection)

    assert not route.called
    assert result["status"] == "error"
    assert emitted[0]["status"] == SyncStatus.FAILED
    assert emitted[0]["error"] == "reauth_required"
    assert connection.last_synced_at == before
    assert connection.status == ConnectionStatus.REVOKED


def test_workout_fetch_error_propagates(db: Session) -> None:
    """A failed fetch is not "nothing to save": it must reach the task to fail or retry."""
    connection = _whoop_connection()
    workouts = ProviderFactory().get_provider("whoop").webhooks.workouts
    with (
        patch.object(
            workouts, "get_workout_detail_from_api", autospec=True, side_effect=HTTPException(status_code=503)
        ),
        pytest.raises(HTTPException),
    ):
        workouts.load_single_workout(db, connection.user_id, str(uuid4()))


def test_unparseable_workout_is_skipped(db: Session) -> None:
    """A record that cannot be parsed is skipped, not raised."""
    connection = _whoop_connection()
    workouts = ProviderFactory().get_provider("whoop").webhooks.workouts
    with patch.object(workouts, "get_workout_detail_from_api", autospec=True, return_value={"id": "broken"}):
        assert workouts.load_single_workout(db, connection.user_id, "broken") == 0
