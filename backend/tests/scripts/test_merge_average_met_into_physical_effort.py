"""Tests for the data migration that merges average_met into physical_effort.

See scripts/data_migrations/merge_average_met_into_physical_effort.py.
"""

import importlib.util
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import ModuleType

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import EventRecordAggregate, SeriesTypeDefinition
from app.repositories import AggregateRepository
from app.schemas.enums import ComputedBy
from app.schemas.enums.series_types import SeriesType, get_series_type_id
from tests.factories import DataPointSeriesFactory, DataSourceFactory, EventRecordFactory

AVERAGE_MET_ID = 87
PHYSICAL_EFFORT_ID = get_series_type_id(SeriesType.physical_effort)

_SCRIPT_PATH = (
    Path(__file__).resolve().parents[2] / "scripts" / "data_migrations" / "merge_average_met_into_physical_effort.py"
)


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("merge_average_met_into_physical_effort", _SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


merge_average_met = _load_module().merge_average_met

T = datetime(2026, 1, 1, 9, tzinfo=timezone.utc)


@pytest.fixture
def average_met(db: Session) -> SeriesTypeDefinition:
    """The retired definition, which a database that ran an older version still holds."""
    definition = SeriesTypeDefinition(id=AVERAGE_MET_ID, code="average_met", unit="met")
    db.add(definition)
    db.flush()
    return definition


def _rows(db: Session, table: str) -> list[tuple[int, Decimal]]:
    value = "value" if table == "series_sample" else "avg"
    return sorted(db.execute(text(f"SELECT series_type_definition_id, {value} FROM {table}")).tuples().all())


def test_moves_samples_and_workout_values_onto_physical_effort(db: Session, average_met: SeriesTypeDefinition) -> None:
    source = DataSourceFactory()
    workout = EventRecordFactory(data_source=source)
    DataPointSeriesFactory(data_source=source, series_type=average_met, recorded_at=T, value=Decimal("5.8"))
    AggregateRepository(EventRecordAggregate).upsert(
        db,
        [
            {
                "record_id": workout.id,
                "series_type_definition_id": AVERAGE_MET_ID,
                "computed_by": ComputedBy.PROVIDER,
                "avg": Decimal("5.8"),
                "count": 1,
            }
        ],
    )

    result = merge_average_met(db, dry_run=False)

    assert (result["series_sample_updated"], result["event_record_aggregate_updated"]) == (1, 1)
    assert _rows(db, "series_sample") == [(PHYSICAL_EFFORT_ID, Decimal("5.8"))]
    assert _rows(db, "event_record_aggregate") == [(PHYSICAL_EFFORT_ID, Decimal("5.8"))]


def test_keeps_the_physical_effort_row_already_at_the_same_instant(
    db: Session, average_met: SeriesTypeDefinition
) -> None:
    source = DataSourceFactory()
    for definition, value in ((average_met, "5.8"), (db.get(SeriesTypeDefinition, PHYSICAL_EFFORT_ID), "6.1")):
        DataPointSeriesFactory(data_source=source, series_type=definition, recorded_at=T, value=Decimal(value))

    result = merge_average_met(db, dry_run=False)

    assert (result["series_sample_updated"], result["series_sample_deleted"]) == (0, 1)
    assert _rows(db, "series_sample") == [(PHYSICAL_EFFORT_ID, Decimal("6.1"))]


def test_a_dry_run_changes_nothing(db: Session, average_met: SeriesTypeDefinition) -> None:
    DataPointSeriesFactory(data_source=DataSourceFactory(), series_type=average_met, recorded_at=T, value=Decimal("4"))

    result = merge_average_met(db, dry_run=True)

    assert result["series_sample_updated"] == 1
    assert _rows(db, "series_sample") == [(AVERAGE_MET_ID, Decimal("4"))]
