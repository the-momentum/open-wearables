"""Tests for the one-off purge of Google Health API energy rows written from total-calories.

Legacy rows are untagged (external_id IS NULL) energy rows on source='google_health_api';
rows the fixed ingestion writes carry an external_id. Archive buckets carry no marker, so
every Health API energy bucket goes. Everything else — other series on the same source,
energy from other sources/providers — must survive.
See scripts/data_migrations/purge_google_total_calories_energy.py.
"""

import importlib.util
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import ModuleType
from typing import cast
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models import DataPointSeries, DataPointSeriesArchive, DataSource, SeriesTypeDefinition
from app.schemas.enums import SeriesType
from app.schemas.enums.aggregation_method import AggregationMethod
from app.schemas.enums.provider import ProviderName
from app.schemas.enums.series_types import get_series_type_id
from tests.factories import DataPointSeriesFactory, DataSourceFactory

ENERGY_ID = get_series_type_id(SeriesType.active_energy)
BASAL_ID = get_series_type_id(SeriesType.basal_energy)
T0 = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)

_SCRIPT_PATH = (
    Path(__file__).resolve().parents[2] / "scripts" / "data_migrations" / "purge_google_total_calories_energy.py"
)


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("purge_google_total_calories_energy", _SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


purge = _load_module().run


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _source(provider: ProviderName, source: str, device_model: str | None = "TestDevice") -> DataSource:
    return cast(DataSource, DataSourceFactory(provider=provider, source=source, device_model=device_model))


def _health_api_source() -> DataSource:
    return _source(ProviderName.GOOGLE_HEALTH, "google_health_api", device_model=None)


def _point(db: Session, source: DataSource, *, type_id: int, offset_hours: int, external_id: str | None = None) -> None:
    DataPointSeriesFactory(
        data_source=source,
        series_type=db.get(SeriesTypeDefinition, type_id),
        recorded_at=T0 + timedelta(hours=offset_hours),
        value=Decimal("100.0"),
        external_id=external_id,
    )


def _archive_row(db: Session, source: DataSource, *, type_id: int, day: int) -> None:
    db.add(
        DataPointSeriesArchive(
            id=uuid4(),
            data_source_id=source.id,
            series_type_definition_id=type_id,
            bucket_start_at=T0 + timedelta(days=day),
            aggregation_type=AggregationMethod.SUM,
            value=Decimal("2400.0"),
            sample_count=24,
        )
    )
    db.flush()


def _live_rows(db: Session, source: DataSource) -> list[DataPointSeries]:
    return db.query(DataPointSeries).filter(DataPointSeries.data_source_id == source.id).all()


def _archive_count(db: Session, source: DataSource) -> int:
    return db.query(DataPointSeriesArchive).filter(DataPointSeriesArchive.data_source_id == source.id).count()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_deletes_untagged_energy_and_keeps_tagged(db: Session) -> None:
    source = _health_api_source()
    for h in range(5):
        _point(db, source, type_id=ENERGY_ID, offset_hours=h)
    _point(db, source, type_id=ENERGY_ID, offset_hours=10, external_id="energy:2026-01-01T10:00:00+00:00")

    # batch=2 forces several iterations of the delete loop.
    result = purge(db, dry_run=False, batch=2)

    assert result["series_deleted"] == 5
    remaining = _live_rows(db, source)
    assert [r.external_id for r in remaining] == ["energy:2026-01-01T10:00:00+00:00"]


def test_keeps_other_series_and_other_sources(db: Session) -> None:
    api = _health_api_source()
    _point(db, api, type_id=ENERGY_ID, offset_hours=0)
    _point(db, api, type_id=BASAL_ID, offset_hours=0)  # derived basal: untagged, must stay
    # Health Connect SDK rows carry the reporting app as source, not google_health_api.
    sdk = _source(ProviderName.HEALTH_CONNECT, "Fitbit")
    _point(db, sdk, type_id=ENERGY_ID, offset_hours=0)
    apple = _source(ProviderName.APPLE, "apple_health_sdk")
    _point(db, apple, type_id=ENERGY_ID, offset_hours=0)

    result = purge(db, dry_run=False)

    assert result["series_deleted"] == 1
    assert [r.series_type_definition_id for r in _live_rows(db, api)] == [BASAL_ID]
    assert len(_live_rows(db, sdk)) == 1
    assert len(_live_rows(db, apple)) == 1


def test_dry_run_reports_and_changes_nothing(db: Session) -> None:
    source = _health_api_source()
    _point(db, source, type_id=ENERGY_ID, offset_hours=0)
    _point(db, source, type_id=ENERGY_ID, offset_hours=1)
    _archive_row(db, source, type_id=ENERGY_ID, day=-30)

    result = purge(db, dry_run=True)

    assert result == {"series_deleted": 2, "archive_deleted": 1}
    assert len(_live_rows(db, source)) == 2
    assert _archive_count(db, source) == 1


def test_purges_archive_energy_buckets_only(db: Session) -> None:
    api = _health_api_source()
    _archive_row(db, api, type_id=ENERGY_ID, day=-30)
    _archive_row(db, api, type_id=ENERGY_ID, day=-29)
    _archive_row(db, api, type_id=BASAL_ID, day=-30)
    sdk = _source(ProviderName.HEALTH_CONNECT, "Fitbit")
    _archive_row(db, sdk, type_id=ENERGY_ID, day=-30)

    result = purge(db, dry_run=False, batch=1)

    assert result["archive_deleted"] == 2
    api_left = db.query(DataPointSeriesArchive).filter(DataPointSeriesArchive.data_source_id == api.id).all()
    assert [r.series_type_definition_id for r in api_left] == [BASAL_ID]
    assert _archive_count(db, sdk) == 1


def test_skip_archive_leaves_archive_alone(db: Session) -> None:
    source = _health_api_source()
    _point(db, source, type_id=ENERGY_ID, offset_hours=0)
    _archive_row(db, source, type_id=ENERGY_ID, day=-30)

    result = purge(db, dry_run=False, include_archive=False)

    assert result == {"series_deleted": 1, "archive_deleted": 0}
    assert _archive_count(db, source) == 1


def test_idempotent_second_run_is_noop(db: Session) -> None:
    source = _health_api_source()
    _point(db, source, type_id=ENERGY_ID, offset_hours=0)
    _archive_row(db, source, type_id=ENERGY_ID, day=-30)

    purge(db, dry_run=False)
    second = purge(db, dry_run=False)

    assert second == {"series_deleted": 0, "archive_deleted": 0}


def test_finds_the_series_when_the_stored_name_is_still_the_retired_one(db: Session) -> None:
    """The purge may run before the active_energy rename reaches the database.

    Resolving the series by name would come up empty there and report "nothing to purge",
    which reads as "no data" rather than "lookup failed". The id is what rows reference.
    """
    definition = db.get(SeriesTypeDefinition, ENERGY_ID)
    assert definition is not None
    definition.code = "energy"
    db.flush()

    source = _health_api_source()
    _point(db, source, type_id=ENERGY_ID, offset_hours=0)

    result = purge(db, dry_run=False)

    assert result["series_deleted"] == 1
    assert _live_rows(db, source) == []


def test_no_health_api_sources_is_noop(db: Session) -> None:
    apple = _source(ProviderName.APPLE, "apple_health_sdk")
    _point(db, apple, type_id=ENERGY_ID, offset_hours=0)

    result = purge(db, dry_run=False)

    assert result == {"series_deleted": 0, "archive_deleted": 0}
    assert len(_live_rows(db, apple)) == 1
