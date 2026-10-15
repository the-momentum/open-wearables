"""Tests for the one-off data migration that relabels Ultrahuman active_time -> exercise_time.

Ultrahuman documents active minutes as moderate to vigorous activity, so they
belong in exercise_time (id=84), not active_time (id=88). This script relabels existing
Ultrahuman rows, scoped strictly to provider='ultrahuman' so other providers' active_time
is left untouched. See scripts/data_migrations/relabel_ultrahuman_active_time_to_exercise_time.py.
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

ACTIVE_TIME_ID = 88
EXERCISE_TIME_ID = 84

_SCRIPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "data_migrations"
    / "relabel_ultrahuman_active_time_to_exercise_time.py"
)


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("relabel_ultrahuman_active_time_to_exercise_time", _SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


relabel_ultrahuman_active_time = _load_module().relabel_ultrahuman_active_time


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _series_type(db: Session, type_id: int) -> SeriesTypeDefinition:
    """Fetch a series type seeded at session scope (see conftest.engine)."""
    return db.get(SeriesTypeDefinition, type_id)


def _make_point(
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
            aggregation_type=AggregationMethod.SUM,
            value=Decimal("35"),
            sample_count=1,
        )
    )
    db.flush()


def _type_ids(db: Session, table: str) -> list[int]:
    rows = db.execute(text(f"SELECT series_type_definition_id FROM {table}")).scalars().all()
    return list(rows)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_relabels_ultrahuman_active_time_to_exercise_time(db: Session) -> None:
    t = datetime(2026, 1, 1, tzinfo=timezone.utc)
    _make_point(db, provider=ProviderName.ULTRAHUMAN, type_id=ACTIVE_TIME_ID, recorded_at=t, value="35")
    _make_point(
        db, provider=ProviderName.ULTRAHUMAN, type_id=ACTIVE_TIME_ID, recorded_at=t + timedelta(days=1), value="20"
    )

    result = relabel_ultrahuman_active_time(db, dry_run=False)

    assert result["series_updated"] == 2
    assert _type_ids(db, "data_point_series") == [EXERCISE_TIME_ID, EXERCISE_TIME_ID]


def test_leaves_non_ultrahuman_active_time_untouched(db: Session) -> None:
    t = datetime(2026, 1, 1, tzinfo=timezone.utc)
    # Garmin's active_time is genuine non-sedentary time — must not be relabeled.
    _make_point(db, provider=ProviderName.GARMIN, type_id=ACTIVE_TIME_ID, recorded_at=t, value="80")
    _make_point(db, provider=ProviderName.ULTRAHUMAN, type_id=ACTIVE_TIME_ID, recorded_at=t, value="35")

    result = relabel_ultrahuman_active_time(db, dry_run=False)

    assert result["series_updated"] == 1
    assert sorted(_type_ids(db, "data_point_series")) == [EXERCISE_TIME_ID, ACTIVE_TIME_ID]


def test_dry_run_makes_no_changes(db: Session) -> None:
    t = datetime(2026, 1, 1, tzinfo=timezone.utc)
    _make_point(db, provider=ProviderName.ULTRAHUMAN, type_id=ACTIVE_TIME_ID, recorded_at=t, value="35")

    result = relabel_ultrahuman_active_time(db, dry_run=True)

    assert result["series_updated"] == 1  # reported as "would update"
    assert _type_ids(db, "data_point_series") == [ACTIVE_TIME_ID]


def test_idempotent_second_run_is_noop(db: Session) -> None:
    t = datetime(2026, 1, 1, tzinfo=timezone.utc)
    _make_point(db, provider=ProviderName.ULTRAHUMAN, type_id=ACTIVE_TIME_ID, recorded_at=t, value="35")

    relabel_ultrahuman_active_time(db, dry_run=False)
    second = relabel_ultrahuman_active_time(db, dry_run=False)

    assert second["series_updated"] == 0
    assert second["series_deleted"] == 0
    assert _type_ids(db, "data_point_series") == [EXERCISE_TIME_ID]


def test_handles_unique_conflict_with_existing_exercise_time(db: Session) -> None:
    """If an exercise_time row already exists at the same (source, recorded_at) — written
    by a re-sync after the mapping fix — the stale active_time row is removed instead of
    triggering a unique-constraint violation."""
    t = datetime(2026, 1, 1, tzinfo=timezone.utc)
    source = DataSourceFactory(provider=ProviderName.ULTRAHUMAN)
    DataPointSeriesFactory(
        data_source=source, series_type=_series_type(db, ACTIVE_TIME_ID), recorded_at=t, value=Decimal("35")
    )
    DataPointSeriesFactory(
        data_source=source, series_type=_series_type(db, EXERCISE_TIME_ID), recorded_at=t, value=Decimal("35")
    )

    result = relabel_ultrahuman_active_time(db, dry_run=False)

    assert result["series_deleted"] == 1
    assert result["series_updated"] == 0
    rows = db.query(DataPointSeries).filter(DataPointSeries.data_source_id == source.id).all()
    assert len(rows) == 1
    assert rows[0].series_type_definition_id == EXERCISE_TIME_ID


def test_relabels_archive_table(db: Session) -> None:
    t = datetime(2026, 1, 1, tzinfo=timezone.utc)
    _make_archive_row(db, provider=ProviderName.ULTRAHUMAN, type_id=ACTIVE_TIME_ID, bucket_start_at=t)
    _make_archive_row(db, provider=ProviderName.GARMIN, type_id=ACTIVE_TIME_ID, bucket_start_at=t)

    result = relabel_ultrahuman_active_time(db, dry_run=False)

    assert result["archive_updated"] == 1
    assert sorted(_type_ids(db, "data_point_series_archive")) == [EXERCISE_TIME_ID, ACTIVE_TIME_ID]
