"""Strava webhook: last_synced_at moves only when the activity was fetched from the API."""

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.services.providers.factory import ProviderFactory
from tests.factories import UserConnectionFactory

ATHLETE_ID = 424242


@pytest.fixture
def handler() -> Any:
    return ProviderFactory().get_provider("strava").webhooks


def _connection() -> Any:
    return UserConnectionFactory(
        provider="strava",
        provider_user_id=str(ATHLETE_ID),
        last_synced_at=datetime.now(timezone.utc) - timedelta(days=3),
    )


def _payload(aspect_type: str) -> dict[str, Any]:
    return {
        "object_type": "activity",
        "object_id": 1001,
        "aspect_type": aspect_type,
        "owner_id": ATHLETE_ID,
        "subscription_id": 1,
        "event_time": 1_700_000_000,
    }


def test_delete_keeps_last_synced_at(db: Session, handler: Any) -> None:
    connection = _connection()
    before = connection.last_synced_at

    with patch.object(handler.workouts, "get_workout_detail_from_api") as api:
        result = handler.process_payload(db, _payload("delete"), "trace-1")
    db.refresh(connection)

    api.assert_not_called()
    assert result["status"] == "deleted"
    assert connection.last_synced_at == before


def test_completed_fetch_updates_last_synced_at(db: Session, handler: Any) -> None:
    connection = _connection()
    before = connection.last_synced_at

    with patch.object(handler.workouts, "get_workout_detail_from_api", return_value={}) as api:
        result = handler.process_payload(db, _payload("create"), "trace-2")
    db.refresh(connection)

    api.assert_called_once()
    assert result["status"] == "warning"
    assert connection.last_synced_at > before
