"""Tests for scripts/data_migrations/dedupe_workouts_by_external_id.py."""

import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType

from sqlalchemy.orm import Session

from app.models import DataSource, EventRecord, EventRecordAggregate, HealthScore, WorkoutDetails
from app.schemas.enums import ProviderName
from tests.factories import (
    DataSourceFactory,
    EventRecordFactory,
    HealthScoreFactory,
    UserFactory,
    WorkoutDetailsFactory,
)

_SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "data_migrations" / "dedupe_workouts_by_external_id.py"
START = datetime(2026, 9, 24, 17, 7, 56, tzinfo=timezone.utc)
INGESTED = datetime(2026, 9, 25, 2, tzinfo=timezone.utc)


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("dedupe_workouts_by_external_id", _SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


dedupe_workouts = _load_module().dedupe_workouts


def _workout(
    ds: DataSource, external_id: str, *, start: datetime = START, end_ms: int = 1_543_190, ingested: int = 0
) -> EventRecord:
    return EventRecordFactory(
        data_source=ds,
        category="workout",
        external_id=external_id,
        start_datetime=start,
        end_datetime=start + timedelta(milliseconds=end_ms),
        created_at=INGESTED + timedelta(hours=ingested),
    )


def _suunto_source() -> DataSource:
    return DataSourceFactory(user=UserFactory(), provider=ProviderName.SUUNTO, source="suunto")


class TestDedupeWorkoutsByExternalId:
    def test_keeps_newest_overlapping_copy(self, db: Session) -> None:
        ds = _suunto_source()
        old = _workout(ds, "6aa1", end_ms=1_543_190)
        new = _workout(ds, "6aa1", end_ms=1_543_443, ingested=17)
        old_id = old.id

        assert dedupe_workouts(db, dry_run=False) == 1
        db.expire_all()

        assert db.get(EventRecord, old_id) is None
        assert db.get(EventRecord, new.id) is not None

    def test_shared_id_of_workouts_apart_is_not_a_duplicate(self, db: Session) -> None:
        """Suunto stored workoutId 0 for every workout; only copies of one workout overlap."""
        ds = _suunto_source()
        first = _workout(ds, "0")
        _workout(ds, "0", start=START + timedelta(days=1), ingested=24)
        _workout(ds, "0", start=START + timedelta(days=2), ingested=48)
        _workout(ds, "0", end_ms=1_543_443, ingested=17)
        first_id = first.id

        assert dedupe_workouts(db, dry_run=False) == 1
        db.expire_all()

        assert db.get(EventRecord, first_id) is None
        assert db.query(EventRecord).filter(EventRecord.data_source_id == ds.id).count() == 3

    def test_back_to_back_workouts_are_not_duplicates(self, db: Session) -> None:
        ds = _suunto_source()
        _workout(ds, "0", end_ms=1_800_000)
        _workout(ds, "0", start=START + timedelta(minutes=30), ingested=1)

        assert dedupe_workouts(db, dry_run=False) == 0

    def test_keeper_takes_what_it_lacks(self, db: Session) -> None:
        ds = _suunto_source()
        old = _workout(ds, "6aa1")
        new = _workout(ds, "6aa1", end_ms=1_543_443, ingested=17)
        WorkoutDetailsFactory(event_record=old, steps_count=4200)
        score = HealthScoreFactory(data_source=ds, provider=ProviderName.SUUNTO, event_record_id=old.id)
        aggregate_ids = [a.id for a in db.query(EventRecordAggregate).filter(EventRecordAggregate.record_id == old.id)]

        dedupe_workouts(db, dry_run=False)
        db.expire_all()

        assert db.get(WorkoutDetails, new.id).steps_count == 4200
        assert db.get(HealthScore, score.id).event_record_id == new.id
        assert aggregate_ids
        assert {db.get(EventRecordAggregate, a).record_id for a in aggregate_ids} == {new.id}

    def test_other_source_and_dry_run_untouched(self, db: Session) -> None:
        user = UserFactory()
        watch = DataSourceFactory(user=user, provider=ProviderName.SUUNTO, source="suunto", device_model="Race")
        other = DataSourceFactory(user=user, provider=ProviderName.SUUNTO, source="suunto", device_model="Vertical")
        _workout(watch, "6aa1")
        _workout(other, "6aa1", end_ms=1_543_443, ingested=17)
        later = START + timedelta(days=1)
        _workout(watch, "7bb2", start=later)
        _workout(watch, "7bb2", start=later, end_ms=1_543_443, ingested=17)

        assert dedupe_workouts(db, dry_run=True) == 1
        assert dedupe_workouts(db, dry_run=False) == 1
        db.expire_all()

        assert db.query(EventRecord).filter(EventRecord.external_id == "6aa1").count() == 2
        assert dedupe_workouts(db, dry_run=False) == 0
