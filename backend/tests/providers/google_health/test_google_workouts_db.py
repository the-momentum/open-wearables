"""Google Health workouts saved in one batch against a real database."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import DataSource, EventRecord
from app.repositories.event_record_repository import EventRecordRepository
from app.schemas.enums import EventCategory
from app.services.event_record_service import event_record_service
from app.services.providers.google_health.workouts import GoogleHealthApiWorkouts
from tests.factories import UserFactory

START = datetime(2026, 10, 14, 6, 0, tzinfo=timezone.utc)


def _exercise(name: str, day: int, device: str) -> dict:
    start = START + timedelta(days=day)
    return {
        "name": f"users/me/dataTypes/exercise/dataPoints/{name}",
        "dataSource": {"platform": "FITBIT", "device": {"displayName": device}},
        "exercise": {
            "interval": {
                "startTime": start.isoformat(),
                "endTime": (start + timedelta(minutes=45)).isoformat(),
                "startUtcOffset": "19800s",
            },
            "exerciseType": "RUNNING",
            "metricsSummary": {"caloriesKcal": 400, "steps": 6000},
        },
    }


def _load(db: Session, user_id: UUID, points: list[dict]) -> int:
    workouts = GoogleHealthApiWorkouts(EventRecordRepository(EventRecord), MagicMock(), MagicMock(), "https://x")
    with patch.object(workouts, "_fetch_points", return_value=points):
        return workouts.load_data(db, user_id, start_date=START, end_date=START + timedelta(days=7))


def test_a_batch_from_two_devices_is_stored_under_each_device(db: Session) -> None:
    user = UserFactory()
    db.commit()
    points = [_exercise("w0", 0, "Fitbit Air"), _exercise("w1", 1, "Pixel Watch"), _exercise("w2", 2, "Fitbit Air")]

    assert _load(db, user.id, points) == 3

    rows = (
        db.query(EventRecord.external_id, DataSource.device_model)
        .join(DataSource, EventRecord.data_source_id == DataSource.id)
        .filter(EventRecord.category == EventCategory.WORKOUT)
        .order_by(EventRecord.start_datetime)
        .all()
    )
    assert [(ext.rsplit("/", 1)[-1], device) for ext, device in rows] == [
        ("w0", "Fitbit Air"),
        ("w1", "Pixel Watch"),
        ("w2", "Fitbit Air"),
    ]
    assert all(r.workout_detail.energy_burned == 400 for r in db.query(EventRecord).all())


def test_a_resync_writes_and_announces_nothing(db: Session) -> None:
    user = UserFactory()
    db.commit()
    points = [_exercise("w0", 0, "Fitbit Air"), _exercise("w1", 1, "Fitbit Air")]

    with (
        patch("app.services.event_record_service.svix_service.is_enabled", return_value=True),
        patch.object(event_record_service, "_emit_event_record_webhook") as emit,
    ):
        assert _load(db, user.id, points) == 2
        assert emit.call_count == 2
        emit.reset_mock()

        assert _load(db, user.id, points) == 0
        emit.assert_not_called()

    assert db.query(EventRecord).count() == 2


def test_a_batch_past_the_bind_parameter_limit_is_stored(db: Session) -> None:
    # A workout detail binds 22 parameters, so 3,000 in one INSERT would pass PostgreSQL's 65,535.
    user = UserFactory()
    db.commit()
    points = [_exercise(f"w{i}", 0, "Fitbit Air") for i in range(3000)]
    for i, point in enumerate(points):
        start = START + timedelta(minutes=i)
        point["exercise"]["interval"] |= {"startTime": start.isoformat(), "endTime": start.isoformat()}

    assert _load(db, user.id, points) == 3000
