"""Tests for the one-off typing of Google Health sleep rows saved without ``sleep_session``."""

import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType

from sqlalchemy.orm import Session

from app.models import EventRecord
from app.schemas.enums import ProviderName
from tests.factories import DataSourceFactory, EventRecordFactory

_SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "data_migrations" / "backfill_google_sleep_type.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("backfill_google_sleep_type", _SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


backfill_google_sleep_type = _load_module().backfill_google_sleep_type

NIGHT = datetime(2026, 5, 1, 22, 0, tzinfo=timezone.utc)


def _row(provider: ProviderName, *, category: str = "sleep", type_: str | None = None, night: int = 0) -> EventRecord:
    return EventRecordFactory(
        data_source=DataSourceFactory(provider=provider),
        category=category,
        type=type_,
        start_datetime=NIGHT + timedelta(days=night),
        duration_seconds=8 * 3600,
    )


def test_types_only_untyped_google_sleep(db: Session) -> None:
    google_sleep = _row(ProviderName.GOOGLE_HEALTH)
    google_workout = _row(ProviderName.GOOGLE_HEALTH, category="workout", night=1)
    oura_sleep = _row(ProviderName.OURA)

    assert backfill_google_sleep_type(db, dry_run=False, batch_size=1) == 1

    db.refresh(google_sleep)
    db.refresh(google_workout)
    db.refresh(oura_sleep)
    assert (google_sleep.type, google_workout.type, oura_sleep.type) == ("sleep_session", None, None)


def test_a_second_run_changes_nothing(db: Session) -> None:
    _row(ProviderName.GOOGLE_HEALTH)

    backfill_google_sleep_type(db, dry_run=False)

    assert backfill_google_sleep_type(db, dry_run=False) == 0


def test_dry_run_counts_without_writing(db: Session) -> None:
    google_sleep = _row(ProviderName.GOOGLE_HEALTH)

    assert backfill_google_sleep_type(db, dry_run=True) == 1

    db.refresh(google_sleep)
    assert google_sleep.type is None
