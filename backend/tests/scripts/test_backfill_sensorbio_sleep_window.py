import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType

from sqlalchemy import event
from sqlalchemy.orm import Session

from app.models import EventRecord, SleepDetails
from app.schemas.enums import ProviderName
from tests.factories import DataSourceFactory, EventRecordFactory, SleepDetailsFactory

_SCRIPT_PATH = (
    Path(__file__).resolve().parents[2] / "scripts" / "data_migrations" / "backfill_sensorbio_sleep_window.py"
)


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("backfill_sensorbio_sleep_window", _SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


backfill_sensorbio_sleep_window = _load_module().backfill_sensorbio_sleep_window

START = datetime(2026, 10, 1, 22, 13, tzinfo=timezone.utc)
END = START + timedelta(hours=8)


def _sleep(provider: ProviderName, *, duration_seconds: int, time_in_bed_minutes: int) -> SleepDetails:
    record = EventRecordFactory(
        data_source=DataSourceFactory(provider=provider, source=provider.value),
        category="sleep",
        type="sleep_session",
        start_datetime=START,
        end_datetime=END,
        duration_seconds=duration_seconds,
    )
    return SleepDetailsFactory(
        event_record=record, sleep_total_duration_minutes=420, sleep_time_in_bed_minutes=time_in_bed_minutes
    )


def _stored(db: Session, details: SleepDetails) -> tuple[int | None, int | None]:
    db.expire_all()
    return (
        db.get(EventRecord, details.record_id).duration_seconds,
        db.get(SleepDetails, details.record_id).sleep_time_in_bed_minutes,
    )


class TestBackfillSensorbioSleepWindow:
    def test_sets_window_on_sensorbio_sleep_only(self, db: Session) -> None:
        asleep = _sleep(ProviderName.SENSORBIO, duration_seconds=25200, time_in_bed_minutes=420)
        zero = _sleep(ProviderName.SENSORBIO, duration_seconds=0, time_in_bed_minutes=0)
        other = _sleep(ProviderName.OURA, duration_seconds=25200, time_in_bed_minutes=420)

        assert backfill_sensorbio_sleep_window(db, dry_run=False) == 2

        assert _stored(db, asleep) == (28800, 480)
        assert _stored(db, zero) == (28800, 480)
        assert _stored(db, other) == (25200, 420)
        assert backfill_sensorbio_sleep_window(db, dry_run=False) == 0

    def test_without_sensorbio_source_only_checks_data_source(self, db: Session) -> None:
        other = _sleep(ProviderName.OURA, duration_seconds=25200, time_in_bed_minutes=420)
        db.flush()
        statements: list[str] = []
        connection = db.connection()

        def _record(*args: object) -> None:
            statements.append(str(args[2]))

        event.listen(connection, "before_cursor_execute", _record)
        try:
            assert backfill_sensorbio_sleep_window(db, dry_run=False) == 0
        finally:
            event.remove(connection, "before_cursor_execute", _record)

        assert len(statements) == 1
        assert "event_record" not in statements[0]
        assert _stored(db, other) == (25200, 420)

    def test_dry_run_counts_and_changes_nothing(self, db: Session) -> None:
        details = _sleep(ProviderName.SENSORBIO, duration_seconds=0, time_in_bed_minutes=0)

        assert backfill_sensorbio_sleep_window(db, dry_run=True) == 1
        assert _stored(db, details) == (0, 0)
