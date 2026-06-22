"""Tests for the one-off data migration that relabels Oura HRV SDNN -> RMSSD.

Oura reports RMSSD-based HRV, but the ingestion historically stored it under the
SDNN series type (id=3). This script relabels existing Oura rows to RMSSD (id=7),
scoped strictly to provider='oura' so other providers' genuine SDNN data is left
untouched. See scripts/data_migrations/relabel_oura_hrv_sdnn_to_rmssd.py.
"""

import importlib.util
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import ModuleType
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import DataPointSeries, DataPointSeriesArchive, SeriesTypeDefinition
from app.schemas.enums.aggregation_method import AggregationMethod
from app.schemas.enums.provider import ProviderName
from tests.factories import DataPointSeriesFactory, DataSourceFactory

SDNN_ID = 3
RMSSD_ID = 7

_SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "data_migrations" / "relabel_oura_hrv_sdnn_to_rmssd.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("relabel_oura_hrv_sdnn_to_rmssd", _SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


relabel_oura_hrv = _load_module().relabel_oura_hrv


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _series_type(db: Session, type_id: int) -> SeriesTypeDefinition:
    """Fetch a series type seeded at session scope (see conftest.engine)."""
    return db.get(SeriesTypeDefinition, type_id)


def _make_hrv_point(
    db: Session, *, provider: ProviderName, type_id: int, recorded_at: datetime, value: str
) -> DataPointSeries:
    source = DataSourceFactory(provider=provider)
    return DataPointSeriesFactory(
        data_source=source,
        series_type=_series_type(db, type_id),
        recorded_at=recorded_at,
        value=Decimal(value),
    )


def _make_archive_row(db: Session, *, provider: ProviderName, type_id: int, bucket_start_at: datetime) -> None:
    source = DataSourceFactory(provider=provider)
    db.add(
        DataPointSeriesArchive(
            id=uuid4(),
            data_source_id=source.id,
            series_type_definition_id=type_id,
            bucket_start_at=bucket_start_at,
            aggregation_type=AggregationMethod.AVG,
            value=Decimal("42.0"),
            sample_count=10,
        )
    )
    db.flush()


def _type_ids(db: Session, table: str) -> list[int]:
    rows = db.execute(text(f"SELECT series_type_definition_id FROM {table}")).scalars().all()
    return list(rows)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_relabels_oura_sdnn_to_rmssd(db: Session) -> None:
    t = datetime(2026, 1, 1, 2, 0, tzinfo=timezone.utc)
    _make_hrv_point(db, provider=ProviderName.OURA, type_id=SDNN_ID, recorded_at=t, value="55.0")
    _make_hrv_point(db, provider=ProviderName.OURA, type_id=SDNN_ID, recorded_at=t + timedelta(minutes=5), value="60.0")

    result = relabel_oura_hrv(db, dry_run=False)

    assert result["series_updated"] == 2
    type_ids = _type_ids(db, "data_point_series")
    assert type_ids == [RMSSD_ID, RMSSD_ID]


def test_leaves_non_oura_sdnn_untouched(db: Session) -> None:
    t = datetime(2026, 1, 1, 2, 0, tzinfo=timezone.utc)
    # Apple genuinely reports SDNN — must not be relabeled.
    _make_hrv_point(db, provider=ProviderName.APPLE, type_id=SDNN_ID, recorded_at=t, value="48.0")
    _make_hrv_point(db, provider=ProviderName.OURA, type_id=SDNN_ID, recorded_at=t, value="55.0")

    result = relabel_oura_hrv(db, dry_run=False)

    assert result["series_updated"] == 1
    type_ids = sorted(_type_ids(db, "data_point_series"))
    assert type_ids == [SDNN_ID, RMSSD_ID]


def test_dry_run_makes_no_changes(db: Session) -> None:
    t = datetime(2026, 1, 1, 2, 0, tzinfo=timezone.utc)
    _make_hrv_point(db, provider=ProviderName.OURA, type_id=SDNN_ID, recorded_at=t, value="55.0")

    result = relabel_oura_hrv(db, dry_run=True)

    assert result["series_updated"] == 1  # reported as "would update"
    assert _type_ids(db, "data_point_series") == [SDNN_ID]


def test_idempotent_second_run_is_noop(db: Session) -> None:
    t = datetime(2026, 1, 1, 2, 0, tzinfo=timezone.utc)
    _make_hrv_point(db, provider=ProviderName.OURA, type_id=SDNN_ID, recorded_at=t, value="55.0")

    relabel_oura_hrv(db, dry_run=False)
    second = relabel_oura_hrv(db, dry_run=False)

    assert second["series_updated"] == 0
    assert second["series_deleted"] == 0
    assert _type_ids(db, "data_point_series") == [RMSSD_ID]


def test_handles_unique_conflict_with_existing_rmssd(db: Session) -> None:
    """If a correct RMSSD row already exists at the same (source, recorded_at)
    — e.g. re-ingested after the ingestion fix — the stale SDNN duplicate must be
    removed instead of triggering a unique-constraint violation."""
    t = datetime(2026, 1, 1, 2, 0, tzinfo=timezone.utc)
    source = DataSourceFactory(provider=ProviderName.OURA)
    DataPointSeriesFactory(
        data_source=source, series_type=_series_type(db, SDNN_ID), recorded_at=t, value=Decimal("55.0")
    )
    DataPointSeriesFactory(
        data_source=source, series_type=_series_type(db, RMSSD_ID), recorded_at=t, value=Decimal("55.0")
    )

    result = relabel_oura_hrv(db, dry_run=False)

    assert result["series_deleted"] == 1
    assert result["series_updated"] == 0
    rows = db.query(DataPointSeries).filter(DataPointSeries.data_source_id == source.id).all()
    assert len(rows) == 1
    assert rows[0].series_type_definition_id == RMSSD_ID


def test_relabels_archive_table(db: Session) -> None:
    t = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    _make_archive_row(db, provider=ProviderName.OURA, type_id=SDNN_ID, bucket_start_at=t)
    _make_archive_row(db, provider=ProviderName.APPLE, type_id=SDNN_ID, bucket_start_at=t)

    result = relabel_oura_hrv(db, dry_run=False)

    assert result["archive_updated"] == 1
    type_ids = sorted(_type_ids(db, "data_point_series_archive"))
    assert type_ids == [SDNN_ID, RMSSD_ID]
