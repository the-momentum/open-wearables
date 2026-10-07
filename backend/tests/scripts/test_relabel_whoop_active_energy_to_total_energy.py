"""Tests for the data migration that relabels Whoop active_energy -> total_energy.

See scripts/data_migrations/relabel_whoop_active_energy_to_total_energy.py.
"""

import importlib.util
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import ModuleType

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import DataPointSeries, SeriesTypeDefinition
from app.schemas.enums.provider import ProviderName
from tests.factories import DataPointSeriesFactory, DataSourceFactory

ACTIVE_ENERGY_ID = 81
TOTAL_ENERGY_ID = 89

_SCRIPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "data_migrations"
    / "relabel_whoop_active_energy_to_total_energy.py"
)


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("relabel_whoop_active_energy_to_total_energy", _SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


relabel_whoop_active_energy = _load_module().relabel_whoop_active_energy

T = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _make_point(db: Session, *, provider: ProviderName, type_id: int, recorded_at: datetime, value: str) -> None:
    DataPointSeriesFactory(
        data_source=DataSourceFactory(provider=provider),
        series_type=db.get(SeriesTypeDefinition, type_id),
        recorded_at=recorded_at,
        value=Decimal(value),
    )


def _rows(db: Session) -> list[tuple[int, Decimal]]:
    return sorted(db.execute(text("SELECT series_type_definition_id, value FROM data_point_series")).tuples().all())


def test_relabels_whoop_energy_and_drops_zero_rows(db: Session) -> None:
    _make_point(db, provider=ProviderName.WHOOP, type_id=ACTIVE_ENERGY_ID, recorded_at=T, value="2150")
    _make_point(db, provider=ProviderName.WHOOP, type_id=ACTIVE_ENERGY_ID, recorded_at=T + timedelta(days=1), value="0")

    result = relabel_whoop_active_energy(db, dry_run=False)

    assert result["series_updated"] == 1
    assert result["series_deleted"] == 1
    assert _rows(db) == [(TOTAL_ENERGY_ID, Decimal("2150"))]


def test_leaves_other_providers_alone(db: Session) -> None:
    _make_point(db, provider=ProviderName.GARMIN, type_id=ACTIVE_ENERGY_ID, recorded_at=T, value="450")

    relabel_whoop_active_energy(db, dry_run=False)

    assert _rows(db) == [(ACTIVE_ENERGY_ID, Decimal("450"))]


def test_dry_run_changes_nothing_and_rerun_is_noop(db: Session) -> None:
    _make_point(db, provider=ProviderName.WHOOP, type_id=ACTIVE_ENERGY_ID, recorded_at=T, value="2150")

    preview = relabel_whoop_active_energy(db, dry_run=True)
    assert preview["series_updated"] == 1
    assert db.query(DataPointSeries).one().series_type_definition_id == ACTIVE_ENERGY_ID

    relabel_whoop_active_energy(db, dry_run=False)
    assert not any(relabel_whoop_active_energy(db, dry_run=False).values())
