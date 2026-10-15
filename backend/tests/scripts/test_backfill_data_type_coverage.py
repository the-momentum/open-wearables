"""Tests for backfilling data_type_coverage from the series, archive and event rows already held."""

import importlib.util
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import ModuleType
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.models import DataPointSeriesArchive, DataTypeCoverage
from app.repositories.data_type_coverage_repository import data_type_coverage_repository
from app.schemas.data_type_coverage import CoverageSpan
from app.schemas.enums import AggregationMethod, ProviderName
from app.schemas.sync_status import DataTypeKind
from tests.factories import (
    DataPointSeriesFactory,
    DataSourceFactory,
    EventRecordFactory,
    SeriesTypeDefinitionFactory,
    UserFactory,
)

_SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "data_migrations" / "backfill_data_type_coverage.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("backfill_data_type_coverage", _SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


module = _load_module()
backfill_data_type_coverage = module.backfill_data_type_coverage

T = datetime(2026, 3, 1, 8, tzinfo=timezone.utc)


def _span(db: Session, user_id: object, data_type: str, kind: DataTypeKind) -> tuple[datetime, datetime] | None:
    db.expire_all()
    row = data_type_coverage_repository.get(db, user_id, "garmin", data_type, kind)  # ty: ignore[invalid-argument-type]
    return (row.coverage_start, row.coverage_end) if row else None


class TestBackfillDataTypeCoverage:
    def test_spans_live_series_archive_and_events_across_batches(
        self, db: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(module, "_BATCH_SIZE", 1)
        user = UserFactory()
        watch = DataSourceFactory(user=user, provider=ProviderName.GARMIN, device_model="Forerunner 965")
        phone = DataSourceFactory(user=user, provider=ProviderName.GARMIN, device_model="Edge 1040")
        heart_rate = SeriesTypeDefinitionFactory.get_or_create_heart_rate()
        DataPointSeriesFactory(data_source=watch, series_type=heart_rate, recorded_at=T)
        DataPointSeriesFactory(data_source=phone, series_type=heart_rate, recorded_at=T + timedelta(days=2))
        db.add(
            DataPointSeriesArchive(
                id=uuid4(),
                data_source_id=watch.id,
                series_type_definition_id=heart_rate.id,
                bucket_start_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
                aggregation_type=AggregationMethod.AVG,
                value=Decimal(60),
                sample_count=100,
            )
        )
        EventRecordFactory(data_source=phone, category="workout", start_datetime=T, end_datetime=T + timedelta(hours=1))
        db.flush()

        written = backfill_data_type_coverage(db, dry_run=False)

        assert written == {DataTypeKind.SERIES: 2, DataTypeKind.EVENT: 1}
        assert _span(db, user.id, "heart_rate", DataTypeKind.SERIES) == (
            datetime(2025, 1, 1, tzinfo=timezone.utc),
            T + timedelta(days=2),
        )
        assert _span(db, user.id, "workout", DataTypeKind.EVENT) == (T, T + timedelta(hours=1))

    def test_only_widens_what_the_write_paths_already_hold(self, db: Session) -> None:
        user = UserFactory()
        source = DataSourceFactory(user=user, provider=ProviderName.GARMIN)
        DataPointSeriesFactory(
            data_source=source, series_type=SeriesTypeDefinitionFactory.get_or_create_heart_rate(), recorded_at=T
        )
        later = T + timedelta(days=30)
        data_type_coverage_repository.record(
            db, [CoverageSpan(user.id, "garmin", "heart_rate", DataTypeKind.SERIES, later, later)]
        )
        db.flush()

        backfill_data_type_coverage(db, dry_run=False)

        assert _span(db, user.id, "heart_rate", DataTypeKind.SERIES) == (T, later)

    def test_dry_run_counts_and_writes_nothing(self, db: Session) -> None:
        source = DataSourceFactory(provider=ProviderName.GARMIN)
        DataPointSeriesFactory(
            data_source=source, series_type=SeriesTypeDefinitionFactory.get_or_create_heart_rate(), recorded_at=T
        )
        db.flush()

        assert backfill_data_type_coverage(db, dry_run=True) == {DataTypeKind.SERIES: 1, DataTypeKind.EVENT: 0}
        assert db.query(DataTypeCoverage).count() == 0
