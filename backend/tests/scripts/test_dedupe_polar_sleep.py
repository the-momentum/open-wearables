"""Tests for the one-off data migration that removes what Polar sleep re-syncs appended (#1539).

See scripts/data_migrations/dedupe_polar_sleep.py.
"""

import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import EventRecord, SleepDetails
from app.schemas.enums.provider import ProviderName
from tests.factories import DataSourceFactory, EventRecordFactory, SleepDetailsFactory

_SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "data_migrations" / "dedupe_polar_sleep.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("dedupe_polar_sleep", _SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_module = _load_module()
dedupe_polar_sleep = _module.dedupe_polar_sleep
migrate = _module._migrate

# A night in UTC+10: the user wakes up on 24 September, which is still 23 September in UTC.
TZ = timezone(timedelta(hours=10))
START = datetime(2026, 9, 23, 22, 0, tzinfo=TZ)
END = datetime(2026, 9, 24, 6, 30, tzinfo=TZ)
SESSION_MINUTES = 510
# What one sync of the night stores
MINUTES = {
    "sleep_total_duration_minutes": 450,
    "sleep_deep_minutes": 60,
    "sleep_light_minutes": 180,
    "sleep_rem_minutes": 210,
    "sleep_awake_minutes": 60,
}
NOTHING_DONE = {"sessions_repaired": 0, "external_ids_set": 0, "sessions_skipped": 0}


def _stages(end: datetime = END) -> list[dict[str, str]]:
    bounds = [START, START + timedelta(hours=1), START + timedelta(hours=4), end]
    return [
        {"stage": stage, "start_time": start.isoformat(), "end_time": stop.isoformat()}
        for stage, start, stop in zip(["light", "deep", "rem"], bounds, bounds[1:])
    ]


def _sleep(
    provider: ProviderName = ProviderName.POLAR,
    *,
    copies: int = 1,
    stages: list[dict[str, str]] | None = None,
    with_stages: bool = True,
    end: datetime = END,
) -> UUID:
    """Id of a sleep session as `copies` syncs of the same night left it.

    The merge adds up the minutes of a night without stages and recomputes them from the timeline otherwise.
    """
    session_minutes = int((end - START).total_seconds()) // 60
    timeline = (stages or _stages(end)) if with_stages else None
    record = EventRecordFactory(
        data_source=DataSourceFactory(provider=provider),
        category="sleep",
        type="sleep_session",
        start_datetime=START,
        end_datetime=end,
        duration_seconds=session_minutes * 60,
    )
    SleepDetailsFactory(
        event_record=record,
        sleep_stages=timeline * copies if timeline else None,
        sleep_time_in_bed_minutes=session_minutes * copies,
        **{name: minutes * (1 if timeline else copies) for name, minutes in MINUTES.items()},
    )
    return record.id


def _stored(db: Session, record_id: UUID) -> tuple[EventRecord, SleepDetails]:
    db.expire_all()
    return db.get(EventRecord, record_id), db.query(SleepDetails).filter_by(record_id=record_id).one()


def test_keeps_one_copy_of_stages_and_time_in_bed(db: Session) -> None:
    record = _sleep(copies=3)

    result = dedupe_polar_sleep(db, dry_run=False)

    _, detail = _stored(db, record)
    assert result["sessions_repaired"] == 1
    assert detail.sleep_stages == _stages()
    assert detail.sleep_time_in_bed_minutes == SESSION_MINUTES
    assert {name: getattr(detail, name) for name in MINUTES} == MINUTES


def test_divides_the_added_up_minutes_of_a_night_without_stages(db: Session) -> None:
    record = _sleep(copies=3, with_stages=False)

    dedupe_polar_sleep(db, dry_run=False)

    _, detail = _stored(db, record)
    assert detail.sleep_time_in_bed_minutes == SESSION_MINUTES
    assert {name: getattr(detail, name) for name in MINUTES} == MINUTES


def test_night_without_stages_keeps_no_id(db: Session) -> None:
    """Without stages there is no offset to read its local date with; a re-sync gives it Polar's id."""
    record = _sleep(copies=3, with_stages=False)

    result = dedupe_polar_sleep(db, dry_run=False)

    assert result["external_ids_set"] == 0
    assert _stored(db, record)[0].external_id is None


def test_keys_the_night_by_its_local_wake_up_date(db: Session) -> None:
    record = _sleep()

    result = dedupe_polar_sleep(db, dry_run=False)

    stored, _ = _stored(db, record)
    assert result["external_ids_set"] == 1
    assert stored.external_id == "sleep-2026-09-24"


def test_wake_up_date_comes_from_the_session_end_not_the_last_stage(db: Session) -> None:
    """Polar's last hypnogram block can end past the session: here after midnight, while the user woke before it."""
    end = datetime(2026, 9, 23, 23, 59, 30, tzinfo=TZ)
    record = _sleep(end=end, stages=_stages(end=datetime(2026, 9, 24, 0, 0, tzinfo=TZ)))

    dedupe_polar_sleep(db, dry_run=False)

    stored, _ = _stored(db, record)
    assert stored.external_id == "sleep-2026-09-23"


def test_skips_a_night_it_cannot_read_and_repairs_the_rest(db: Session) -> None:
    unreadable = _sleep(copies=2, stages=[{"stage": "light", "start_time": START.isoformat()}])
    readable = _sleep(copies=3)

    result = dedupe_polar_sleep(db, dry_run=False)

    assert result == {"sessions_repaired": 1, "external_ids_set": 1, "sessions_skipped": 1}
    assert _stored(db, unreadable)[1].sleep_time_in_bed_minutes == 2 * SESSION_MINUTES
    assert _stored(db, readable)[1].sleep_time_in_bed_minutes == SESSION_MINUTES


def test_run_with_a_skipped_night_is_not_recorded_as_done(db: Session) -> None:
    _sleep(copies=2, stages=[{"stage": "light", "start_time": START.isoformat()}])

    assert migrate(db, dry_run=False) is False


def test_clean_run_is_recorded_as_done(db: Session) -> None:
    _sleep(copies=2)

    assert migrate(db, dry_run=False) is True


def test_repairs_every_batch(db: Session) -> None:
    records = [_sleep(copies=2) for _ in range(3)]

    result = dedupe_polar_sleep(db, dry_run=False, batch_size=2)

    assert result == {"sessions_repaired": 3, "external_ids_set": 3, "sessions_skipped": 0}
    assert all(len(_stored(db, record)[1].sleep_stages) == 3 for record in records)


def test_leaves_other_providers_untouched(db: Session) -> None:
    record = _sleep(ProviderName.OURA, copies=3)

    result = dedupe_polar_sleep(db, dry_run=False)

    stored, detail = _stored(db, record)
    assert result == NOTHING_DONE
    assert len(detail.sleep_stages) == 9
    assert stored.external_id is None


def test_dry_run_makes_no_changes(db: Session) -> None:
    record = _sleep(copies=3)

    result = dedupe_polar_sleep(db, dry_run=True)

    stored, detail = _stored(db, record)
    assert result == {"sessions_repaired": 1, "external_ids_set": 1, "sessions_skipped": 0}
    assert len(detail.sleep_stages) == 9
    assert stored.external_id is None


def test_second_run_is_a_noop(db: Session) -> None:
    _sleep(copies=3)
    _sleep(copies=3, with_stages=False)

    dedupe_polar_sleep(db, dry_run=False)

    assert dedupe_polar_sleep(db, dry_run=False) == NOTHING_DONE
