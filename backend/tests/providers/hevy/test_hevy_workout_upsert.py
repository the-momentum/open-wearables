"""Hevy edits are applied to the stored workout by Hevy id, against a real database."""

from datetime import datetime, timezone
from unittest.mock import patch
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import DataSource, EventRecord, WorkoutDetails
from app.services.providers.hevy.strategy import HevyStrategy
from app.services.providers.hevy.workouts import HevyWorkouts
from tests.factories import UserFactory
from tests.providers.hevy.test_hevy_workouts import _workout_payload

HEVY_ID = "b459cba5-cd6d-463c-abd6-54f8eafcadcb"


def _load(workouts: HevyWorkouts, db: Session, user_id: UUID, updated: list[dict], deleted: list[str] = []) -> int:  # noqa: B006
    with patch.object(workouts, "get_workout_events", return_value=(updated, deleted)):
        return workouts.load_data(db, user_id, start_date="2026-08-01T00:00:00Z")


def _stored(db: Session, user_id: UUID) -> list[EventRecord]:
    return (
        db.query(EventRecord)
        .join(DataSource, EventRecord.data_source_id == DataSource.id)
        .filter(DataSource.user_id == user_id, EventRecord.category == "workout")
        .order_by(EventRecord.start_datetime)
        .all()
    )


def _detail(db: Session, record_id: UUID) -> WorkoutDetails:
    return db.query(WorkoutDetails).filter(WorkoutDetails.record_id == record_id).one()


def _utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


class TestHevyUpsertByExternalId:
    def test_moved_times_update_the_same_row_and_replace_the_detail(self, db: Session) -> None:
        user = UserFactory()
        workouts = HevyStrategy().workouts
        _load(workouts, db, user.id, [_workout_payload()])
        [original] = _stored(db, user.id)
        assert _detail(db, original.id).distance is not None

        edited = _workout_payload(
            title="Morning Run",
            start_time="2026-08-01T12:30:00Z",
            end_time="2026-08-01T13:30:00Z",
        )
        edited["exercises"] = edited["exercises"][:1]  # treadmill removed in Hevy
        assert _load(workouts, db, user.id, [edited]) == 1

        db.expire_all()
        [record] = _stored(db, user.id)
        assert record.id == original.id
        assert record.external_id == HEVY_ID
        assert _utc(record.start_datetime) == datetime(2026, 8, 1, 12, 30, tzinfo=timezone.utc)
        assert _utc(record.end_datetime) == datetime(2026, 8, 1, 13, 30, tzinfo=timezone.utc)
        assert record.duration_seconds == 60 * 60
        assert record.type == "running"
        detail = _detail(db, record.id)
        # Replaced, not merged: the removed treadmill set takes its distance with it.
        assert detail.distance is None
        assert detail.segments is not None
        assert [s["title"] for s in detail.segments] == ["Bench Press (Barbell)"]

    def test_same_times_still_replace_the_detail(self, db: Session) -> None:
        user = UserFactory()
        workouts = HevyStrategy().workouts
        _load(workouts, db, user.id, [_workout_payload()])

        edited = _workout_payload()
        edited["exercises"][0]["sets"][1]["weight_kg"] = 105
        _load(workouts, db, user.id, [edited])

        db.expire_all()
        [record] = _stored(db, user.id)
        segments = _detail(db, record.id).segments
        assert segments is not None
        assert segments[0]["sets"][1]["weight_kg"] == 105.0

    def test_duplicates_from_earlier_syncs_are_folded_into_one(self, db: Session) -> None:
        user = UserFactory()
        workouts = HevyStrategy().workouts
        # What the old code left behind: the same Hevy workout at two different times.
        _load(workouts, db, user.id, [_workout_payload()])
        with patch.object(workouts, "_stored_workouts", return_value=[]):
            _load(
                workouts,
                db,
                user.id,
                [_workout_payload(start_time="2026-08-01T14:00:00Z", end_time="2026-08-01T15:00:00Z")],
            )
        assert len(_stored(db, user.id)) == 2

        _load(
            workouts,
            db,
            user.id,
            [_workout_payload(start_time="2026-08-01T16:00:00Z", end_time="2026-08-01T17:00:00Z")],
        )

        db.expire_all()
        [record] = _stored(db, user.id)
        assert _utc(record.start_datetime) == datetime(2026, 8, 1, 16, 0, tzinfo=timezone.utc)
        assert db.query(WorkoutDetails).filter(WorkoutDetails.record_id == record.id).count() == 1

    def test_an_edit_onto_another_workouts_slot_is_skipped(self, db: Session) -> None:
        user = UserFactory()
        workouts = HevyStrategy().workouts
        other = _workout_payload(id="other-workout", start_time="2026-08-02T12:00:00Z", end_time="2026-08-02T13:00:00Z")
        _load(workouts, db, user.id, [_workout_payload(), other])

        clashing = _workout_payload(start_time="2026-08-02T12:00:00Z", end_time="2026-08-02T13:00:00Z")
        assert _load(workouts, db, user.id, [clashing]) == 0

        db.expire_all()
        records = _stored(db, user.id)
        assert [(r.external_id, _utc(r.start_datetime).day) for r in records] == [(HEVY_ID, 1), ("other-workout", 2)]

    def test_new_workouts_and_deletes_still_work(self, db: Session) -> None:
        user = UserFactory()
        workouts = HevyStrategy().workouts
        _load(workouts, db, user.id, [_workout_payload()])
        _load(workouts, db, user.id, [], deleted=[HEVY_ID])
        assert _stored(db, user.id) == []
