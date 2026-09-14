"""Tests for the one-off data migration that relabels Ultrahuman temperature
body_temperature -> skin_temperature.

Ultrahuman's ring reports skin temperature, but the ingestion historically stored it
under the body_temperature series type (id=45). This script relabels existing Ultrahuman
rows to skin_temperature (id=46), scoped strictly to provider='ultrahuman' so other
providers' genuine core body-temperature data is left untouched. See
scripts/data_migrations/relabel_ultrahuman_body_temp_to_skin_temp.py.
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

BODY_TEMP_ID = 45
SKIN_TEMP_ID = 46

_SCRIPT_PATH = (
    Path(__file__).resolve().parents[2] / "scripts" / "data_migrations" / "relabel_ultrahuman_body_temp_to_skin_temp.py"
)


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("relabel_ultrahuman_body_temp_to_skin_temp", _SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


relabel_ultrahuman_temp = _load_module().relabel_ultrahuman_temp


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _series_type(db: Session, type_id: int) -> SeriesTypeDefinition:
    """Fetch a series type seeded at session scope (see conftest.engine)."""
    return db.get(SeriesTypeDefinition, type_id)


def _make_temp_point(
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
            value=Decimal("31.0"),
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


def test_relabels_ultrahuman_body_to_skin(db: Session) -> None:
    t = datetime(2026, 1, 1, 2, 0, tzinfo=timezone.utc)
    _make_temp_point(db, provider=ProviderName.ULTRAHUMAN, type_id=BODY_TEMP_ID, recorded_at=t, value="31.0")
    _make_temp_point(
        db, provider=ProviderName.ULTRAHUMAN, type_id=BODY_TEMP_ID, recorded_at=t + timedelta(minutes=5), value="30.5"
    )

    result = relabel_ultrahuman_temp(db, dry_run=False)

    assert result["series_updated"] == 2
    type_ids = _type_ids(db, "data_point_series")
    assert type_ids == [SKIN_TEMP_ID, SKIN_TEMP_ID]


def test_leaves_non_ultrahuman_body_temp_untouched(db: Session) -> None:
    t = datetime(2026, 1, 1, 2, 0, tzinfo=timezone.utc)
    # Apple genuinely reports core body temperature — must not be relabeled.
    _make_temp_point(db, provider=ProviderName.APPLE, type_id=BODY_TEMP_ID, recorded_at=t, value="36.8")
    _make_temp_point(db, provider=ProviderName.ULTRAHUMAN, type_id=BODY_TEMP_ID, recorded_at=t, value="31.0")

    result = relabel_ultrahuman_temp(db, dry_run=False)

    assert result["series_updated"] == 1
    type_ids = sorted(_type_ids(db, "data_point_series"))
    assert type_ids == [BODY_TEMP_ID, SKIN_TEMP_ID]


def test_dry_run_makes_no_changes(db: Session) -> None:
    t = datetime(2026, 1, 1, 2, 0, tzinfo=timezone.utc)
    _make_temp_point(db, provider=ProviderName.ULTRAHUMAN, type_id=BODY_TEMP_ID, recorded_at=t, value="31.0")

    result = relabel_ultrahuman_temp(db, dry_run=True)

    assert result["series_updated"] == 1  # reported as "would update"
    assert _type_ids(db, "data_point_series") == [BODY_TEMP_ID]


def test_idempotent_second_run_is_noop(db: Session) -> None:
    t = datetime(2026, 1, 1, 2, 0, tzinfo=timezone.utc)
    _make_temp_point(db, provider=ProviderName.ULTRAHUMAN, type_id=BODY_TEMP_ID, recorded_at=t, value="31.0")

    relabel_ultrahuman_temp(db, dry_run=False)
    second = relabel_ultrahuman_temp(db, dry_run=False)

    assert second["series_updated"] == 0
    assert second["series_deleted"] == 0
    assert _type_ids(db, "data_point_series") == [SKIN_TEMP_ID]


def test_handles_unique_conflict_with_existing_skin_temp(db: Session) -> None:
    """If a correct skin_temperature row already exists at the same (source, recorded_at)
    — e.g. re-ingested after the ingestion fix — the stale body_temperature duplicate must
    be removed instead of triggering a unique-constraint violation."""
    t = datetime(2026, 1, 1, 2, 0, tzinfo=timezone.utc)
    source = DataSourceFactory(provider=ProviderName.ULTRAHUMAN)
    DataPointSeriesFactory(
        data_source=source, series_type=_series_type(db, BODY_TEMP_ID), recorded_at=t, value=Decimal("31.0")
    )
    DataPointSeriesFactory(
        data_source=source, series_type=_series_type(db, SKIN_TEMP_ID), recorded_at=t, value=Decimal("31.0")
    )

    result = relabel_ultrahuman_temp(db, dry_run=False)

    assert result["series_deleted"] == 1
    assert result["series_updated"] == 0
    rows = db.query(DataPointSeries).filter(DataPointSeries.data_source_id == source.id).all()
    assert len(rows) == 1
    assert rows[0].series_type_definition_id == SKIN_TEMP_ID


def test_relabels_archive_table(db: Session) -> None:
    t = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    _make_archive_row(db, provider=ProviderName.ULTRAHUMAN, type_id=BODY_TEMP_ID, bucket_start_at=t)
    _make_archive_row(db, provider=ProviderName.APPLE, type_id=BODY_TEMP_ID, bucket_start_at=t)

    result = relabel_ultrahuman_temp(db, dry_run=False)

    assert result["archive_updated"] == 1
    type_ids = sorted(_type_ids(db, "data_point_series_archive"))
    assert type_ids == [BODY_TEMP_ID, SKIN_TEMP_ID]
