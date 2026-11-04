"""Google Health sleep sessions: typed as sleep_session so a re-fetched night updates in place."""

from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.models import EventRecord
from app.schemas.enums import EventCategory
from app.services.providers.google_health.sleep import GoogleHealthApiSleep
from tests.factories import UserFactory

WINDOW = (datetime(2026, 5, 1, tzinfo=timezone.utc), datetime(2026, 5, 3, tzinfo=timezone.utc))
INTERVAL = {"startTime": "2026-05-01T22:10:00Z", "endTime": "2026-05-02T05:40:00Z", "startUtcOffset": "7200s"}
STAGES = [
    {"type": "LIGHT", "startTime": "2026-05-01T22:10:00Z", "endTime": "2026-05-02T01:00:00Z"},
    {"type": "DEEP", "startTime": "2026-05-02T01:00:00Z", "endTime": "2026-05-02T05:40:00Z"},
]


def _point(**sleep: Any) -> dict[str, Any]:
    return {
        "name": "users/me/dataTypes/sleep/dataPoints/night-1",
        "sleep": {"interval": INTERVAL, "summary": {"minutesInSleepPeriod": 450, "minutesAsleep": 420}, **sleep},
    }


@pytest.fixture
def handler() -> GoogleHealthApiSleep:
    return GoogleHealthApiSleep(oauth=MagicMock(), connection_repo=MagicMock(), api_base_url="https://x")


def test_a_session_is_typed_as_sleep_session(handler: GoogleHealthApiSleep) -> None:
    sleep = _point()["sleep"]
    start, end = datetime(2026, 5, 1, 22, 10, tzinfo=timezone.utc), datetime(2026, 5, 2, 5, 40, tzinfo=timezone.utc)

    record, _ = handler._normalize(_point(), sleep, INTERVAL, start, end, uuid4())

    assert (record.category, record.type) == (EventCategory.SLEEP, "sleep_session")


def test_a_re_fetched_night_refreshes_its_details_without_a_webhook(db: Session, handler: GoogleHealthApiSleep) -> None:
    user = UserFactory()

    with patch("app.services.event_record_service.on_sleep_created") as sleep_created:
        with patch.object(handler, "_fetch", return_value=[_point()]):
            handler.load_and_save(db, user.id, *WINDOW)
        with patch.object(handler, "_fetch", return_value=[_point(stages=STAGES)]):
            handler.load_and_save(db, user.id, *WINDOW)

    records = db.query(EventRecord).filter(EventRecord.category == EventCategory.SLEEP).all()
    assert len(records) == 1
    db.refresh(records[0])
    assert [stage["stage"] for stage in records[0].sleep_detail.sleep_stages] == ["light", "deep"]
    sleep_created.assert_called_once()


@pytest.mark.parametrize(
    ("metadata", "state"),
    [({"processed": True}, "processed"), ({"processed": False}, "processing"), ({}, None)],
)
def test_a_session_keeps_whether_google_finished_processing_it(
    handler: GoogleHealthApiSleep, metadata: dict[str, Any], state: str | None
) -> None:
    point = _point(metadata=metadata)
    start, end = datetime(2026, 5, 1, 22, 10, tzinfo=timezone.utc), datetime(2026, 5, 2, 5, 40, tzinfo=timezone.utc)

    _, detail = handler._normalize(point, point["sleep"], INTERVAL, start, end, uuid4())

    assert detail.provider_state == state
