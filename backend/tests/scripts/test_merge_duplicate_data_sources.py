"""Tests for the one-off merge of split data sources and duplicate events."""

import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType

from sqlalchemy.orm import Session

from app.models import DataSource, EventRecord, HealthScore
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


merge_duplicate_data_sources = _load_module().merge_duplicate_data_sources


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
