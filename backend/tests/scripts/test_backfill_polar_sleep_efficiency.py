import importlib.util
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import ModuleType

from sqlalchemy.orm import Session

from app.models import SleepDetails
from app.repositories.data_migration_repository import DataMigrationRepository
from app.schemas.enums import ProviderName
from tests.factories import DataSourceFactory, EventRecordFactory, SleepDetailsFactory

_SCRIPT_PATH = (
    Path(__file__).resolve().parents[2] / "scripts" / "data_migrations" / "backfill_polar_sleep_efficiency.py"
)


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("backfill_polar_sleep_efficiency", _SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


module = _load_module()
backfill_polar_sleep_efficiency = module.backfill_polar_sleep_efficiency

START = datetime(2026, 10, 20, 20, 36, tzinfo=timezone.utc)
END = START + timedelta(hours=8)


def _night(
    provider: ProviderName = ProviderName.POLAR,
    *,
    awake_minutes: int | None = 30,
    efficiency: Decimal | None = None,
) -> SleepDetails:
    record = EventRecordFactory(
        data_source=DataSourceFactory(provider=provider, source=provider.value),
        category="sleep",
        type="sleep_session",
        start_datetime=START,
        end_datetime=END,
        duration_seconds=8 * 3600,
    )
    return SleepDetailsFactory(
        event_record=record,
        sleep_awake_minutes=awake_minutes,
        sleep_time_in_bed_minutes=8 * 60,
        sleep_efficiency_score=efficiency,
    )


def _efficiency(db: Session, details: SleepDetails) -> Decimal | None:
    db.expire_all()
    return db.get(SleepDetails, details.record_id).sleep_efficiency_score


class TestBackfillPolarSleepEfficiency:
    def test_sets_the_night_without_its_interruptions_on_polar_nights(self, db: Session) -> None:
        night = _night()
        other = _night(ProviderName.OURA)

        assert backfill_polar_sleep_efficiency(db, dry_run=False) == 1
        assert _efficiency(db, night) == Decimal("93.75")
        assert _efficiency(db, other) is None

    def test_leaves_reported_and_underivable_nights_alone(self, db: Session) -> None:
        reported = _night(efficiency=Decimal("88.00"))
        without_interruptions = _night(awake_minutes=None)
        awake_longer_than_the_night = _night(awake_minutes=9 * 60)
        # 480 stored minutes may be up to 59 seconds more than the 8 h night
        awake_the_whole_night = _night(awake_minutes=8 * 60)
        negative = _night(awake_minutes=-1)

        assert backfill_polar_sleep_efficiency(db, dry_run=False) == 0
        assert _efficiency(db, reported) == Decimal("88.00")
        assert _efficiency(db, without_interruptions) is None
        assert _efficiency(db, awake_longer_than_the_night) is None
        assert _efficiency(db, awake_the_whole_night) is None
        assert _efficiency(db, negative) is None

    def test_a_second_run_changes_nothing(self, db: Session) -> None:
        _night()

        backfill_polar_sleep_efficiency(db, dry_run=False)

        assert backfill_polar_sleep_efficiency(db, dry_run=False) == 0

    def test_dry_run_counts_and_changes_nothing(self, db: Session) -> None:
        night = _night()

        assert backfill_polar_sleep_efficiency(db, dry_run=True) == 1
        assert _efficiency(db, night) is None

    def test_waits_for_the_polar_sleep_dedupe(self, db: Session) -> None:
        night = _night()

        assert module._migrate(db, dry_run=False) is False
        assert _efficiency(db, night) is None

        DataMigrationRepository().mark_completed(db, "dedupe_polar_sleep")

        assert module._migrate(db, dry_run=False) is True
        assert _efficiency(db, night) == Decimal("93.75")
