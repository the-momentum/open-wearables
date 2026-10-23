"""Tests for the one-off merge of split data sources and duplicate events."""

import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType

import pytest
from sqlalchemy.orm import Session

from app.models import DataSource, EventRecord, HealthScore, SeriesSample
from app.schemas.enums import ProviderName
from tests.factories import (
    DataPointSeriesFactory,
    DataSourceFactory,
    EventRecordFactory,
    HealthScoreFactory,
    UserFactory,
)

_SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "data_migrations" / "merge_duplicate_data_sources.py"
START = datetime(2026, 9, 1, 7, tzinfo=timezone.utc)


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("merge_duplicate_data_sources", _SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


merge_module = _load_module()
merge_duplicate_data_sources = merge_module.merge_duplicate_data_sources


def _event(ds: DataSource, start: datetime = START, category: str = "workout") -> EventRecord:
    return EventRecordFactory(
        data_source=ds, category=category, start_datetime=start, end_datetime=start + timedelta(hours=1)
    )


class TestMergeDuplicateDataSources:
    def test_placeholder_model_merges_into_existing_source(self, db: Session) -> None:
        user = UserFactory()
        unknown = DataSourceFactory(user=user, provider=ProviderName.GARMIN, device_model="unknown", source="garmin")
        target = DataSourceFactory(user=user, provider=ProviderName.GARMIN, device_model=None, source="garmin")
        _event(unknown)
        _event(target)
        moved = _event(unknown, START + timedelta(days=1))
        DataPointSeriesFactory(data_source=unknown, recorded_at=START)
        unknown_id = unknown.id

        result = merge_duplicate_data_sources(db, dry_run=False)
        db.expire_all()

        assert result["merged_sources"] == 1
        assert db.query(DataSource).filter(DataSource.id == unknown_id).one_or_none() is None
        assert db.query(EventRecord).filter(EventRecord.data_source_id == target.id).count() == 2
        assert db.get(EventRecord, moved.id).data_source_id == target.id

    def test_platform_model_without_target_is_renamed(self, db: Session) -> None:
        ds = DataSourceFactory(
            provider=ProviderName.GOOGLE_HEALTH, device_model="HEALTH_KIT", source="google_health_api"
        )

        merge_duplicate_data_sources(db, dry_run=False)
        db.expire_all()

        assert db.get(DataSource, ds.id).device_model is None

    def test_duplicate_event_keeps_specific_source_and_its_score(self, db: Session) -> None:
        user = UserFactory()
        legacy = DataSourceFactory(user=user, provider=ProviderName.APPLE, device_model="Watch6,2", source="apple")
        writer = DataSourceFactory(
            user=user, provider=ProviderName.APPLE, device_model="Watch6,2", source="Apple Watch"
        )
        dropped = _event(legacy, category="sleep")
        kept = _event(writer, category="sleep")
        score = HealthScoreFactory(data_source=legacy, provider=ProviderName.APPLE, event_record_id=dropped.id)
        dropped_id = dropped.id

        result = merge_duplicate_data_sources(db, dry_run=False)
        db.expire_all()

        assert result["duplicate_events_removed"] == 1
        assert db.query(EventRecord).filter(EventRecord.id == dropped_id).one_or_none() is None
        assert db.get(HealthScore, score.id).event_record_id == kept.id

    def test_meals_sharing_an_interval_are_kept(self, db: Session) -> None:
        user = UserFactory()
        ds = DataSourceFactory(user=user, provider=ProviderName.APPLE, device_model=None, source="MyFitnessPal")
        other = DataSourceFactory(user=user, provider=ProviderName.APPLE, device_model=None, source="Cronometer")
        for source, external_id in ((ds, "breakfast-eggs"), (ds, "breakfast-coffee"), (other, "lunch")):
            meal = _event(source, category="meal")
            meal.external_id = external_id
        db.flush()

        result = merge_duplicate_data_sources(db, dry_run=False)

        assert result["duplicate_events_removed"] == 0
        assert db.query(EventRecord).filter(EventRecord.category == "meal").count() == 3

    def test_samples_move_in_batches_dropping_copies_the_target_holds(
        self, db: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(merge_module, "_BATCH_SIZE", 2)
        user = UserFactory()
        ids = {"user": user, "provider": ProviderName.GOOGLE_HEALTH, "source": "google_health_api"}
        platform = DataSourceFactory(**ids, device_model="HEALTH_KIT")
        target = DataSourceFactory(**ids, device_model=None)
        for minute in range(5):
            DataPointSeriesFactory(data_source=platform, recorded_at=START + timedelta(minutes=minute))
        for minute in range(2):
            DataPointSeriesFactory(data_source=target, recorded_at=START + timedelta(minutes=minute))
        platform_id = platform.id

        result = merge_duplicate_data_sources(db, dry_run=False)
        db.expire_all()

        assert result["merged_sources"] == 1
        assert db.query(DataSource).filter(DataSource.id == platform_id).one_or_none() is None
        assert db.query(SeriesSample).filter(SeriesSample.data_source_id == target.id).count() == 5

    def test_duplicate_events_are_removed_in_batches(self, db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(merge_module, "_BATCH_SIZE", 2)
        user = UserFactory()
        legacy = DataSourceFactory(user=user, provider=ProviderName.APPLE, device_model="Watch6,2", source="apple")
        writer = DataSourceFactory(
            user=user, provider=ProviderName.APPLE, device_model="Watch6,2", source="Apple Watch"
        )
        for day in range(5):
            _event(legacy, START + timedelta(days=day), category="sleep")
            _event(writer, START + timedelta(days=day), category="sleep")

        result = merge_duplicate_data_sources(db, dry_run=False)

        assert result["duplicate_events_removed"] == 5
        assert db.query(EventRecord).filter(EventRecord.data_source_id == legacy.id).count() == 0
        assert db.query(EventRecord).filter(EventRecord.data_source_id == writer.id).count() == 5

    def test_score_of_best_ranked_copy_moves_when_several_copies_have_one(self, db: Session) -> None:
        user = UserFactory()
        kept_source = DataSourceFactory(
            user=user, provider=ProviderName.APPLE, device_model="Watch6,2", source="Apple Watch"
        )
        named = DataSourceFactory(user=user, provider=ProviderName.APPLE, device_model=None, source="Health")
        legacy = DataSourceFactory(user=user, provider=ProviderName.APPLE, device_model=None, source="apple")
        kept = _event(kept_source, category="sleep")
        best_copy, worse_copy = _event(named, category="sleep"), _event(legacy, category="sleep")
        best_score = HealthScoreFactory(data_source=named, provider=ProviderName.APPLE, event_record_id=best_copy.id)
        HealthScoreFactory(data_source=legacy, provider=ProviderName.APPLE, event_record_id=worse_copy.id)

        result = merge_duplicate_data_sources(db, dry_run=False)
        db.expire_all()

        assert result["duplicate_events_removed"] == 2
        assert [s.id for s in db.query(HealthScore).filter(HealthScore.event_record_id == kept.id)] == [best_score.id]

    def test_dry_run_changes_nothing_and_rerun_is_noop(self, db: Session) -> None:
        ds = DataSourceFactory(provider=ProviderName.POLAR, device_model=None, source=None)

        dry = merge_duplicate_data_sources(db, dry_run=True)
        assert dry["renamed_sources"] == 1
        assert db.get(DataSource, ds.id).source is None

        merge_duplicate_data_sources(db, dry_run=False)
        rerun = merge_duplicate_data_sources(db, dry_run=False)
        db.expire_all()

        assert db.get(DataSource, ds.id).source == "polar"
        assert not any(rerun.values())
