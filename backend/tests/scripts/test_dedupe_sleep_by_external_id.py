"""Tests for scripts/data_migrations/dedupe_sleep_by_external_id.py."""

import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType
from uuid import uuid4

from pytest_mock import MockerFixture
from sqlalchemy.orm import Session

from app.models import DataSource, EventRecord, EventRecordAggregate, HealthScore, SleepDetails
from app.schemas.enums import ProviderName
from app.schemas.enums.series_types import SeriesType, get_series_type_id
from tests.factories import DataSourceFactory, EventRecordFactory, HealthScoreFactory, SleepDetailsFactory, UserFactory

_SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "data_migrations" / "dedupe_sleep_by_external_id.py"
START = datetime(2026, 9, 24, 22, tzinfo=timezone.utc)
INGESTED = datetime(2026, 9, 25, 8, tzinfo=timezone.utc)
UNDATED = datetime(1970, 1, 1, tzinfo=timezone.utc)


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("dedupe_sleep_by_external_id", _SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_module = _load_module()
dedupe_sleep = _module.dedupe_sleep


def _sleep(
    ds: DataSource,
    external_id: str,
    *,
    start: datetime = START,
    hours: float = 8,
    ingested: int = 0,
    is_nap: bool = False,
    in_bed: int | None = None,
    undated: bool = False,
) -> EventRecord:
    record = EventRecordFactory(
        data_source=ds,
        category="sleep",
        type_="sleep_session",
        external_id=external_id,
        start_datetime=start,
        end_datetime=start + timedelta(hours=hours),
        created_at=UNDATED if undated else INGESTED + timedelta(hours=ingested),
    )
    SleepDetailsFactory(event_record=record, is_nap=is_nap, sleep_time_in_bed_minutes=in_bed)
    return record


def _source(provider: ProviderName) -> DataSource:
    return DataSourceFactory(user=UserFactory(), provider=provider, source=provider.value)


class TestDedupeSleepByExternalId:
    def test_keeps_newest_copy_of_a_moved_night(self, db: Session) -> None:
        ds = _source(ProviderName.WHOOP)
        old = _sleep(ds, "night-1")
        new = _sleep(ds, "night-1", start=START + timedelta(hours=5), ingested=12)
        score = HealthScoreFactory(data_source=ds, provider=ProviderName.WHOOP, event_record_id=old.id)
        old_id = old.id

        assert dedupe_sleep(db, dry_run=False) == 1
        db.expire_all()

        assert db.get(EventRecord, old_id) is None
        assert db.get(EventRecord, new.id) is not None
        assert db.get(HealthScore, score.id).event_record_id == new.id

    def test_copy_aggregates_go_with_it_and_the_keepers_days_are_rolled_up(
        self, db: Session, mocker: MockerFixture
    ) -> None:
        ds = _source(ProviderName.WHOOP)
        old = _sleep(ds, "night-1")
        new = _sleep(ds, "night-1", start=START + timedelta(hours=5), ingested=12)
        db.add(
            EventRecordAggregate(
                id=uuid4(),
                record_id=old.id,
                series_type_definition_id=get_series_type_id(SeriesType.heart_rate),
                computed_by="open_wearables",
                avg=55,
                count=1,
            )
        )
        db.flush()
        mark_dirty_days = mocker.patch.object(_module, "mark_dirty_days", autospec=True)

        assert dedupe_sleep(db, dry_run=False) == 1
        db.expire_all()

        assert db.query(EventRecordAggregate).count() == 0
        [queued] = mark_dirty_days.call_args.args[1:]
        assert (ds.id, new.end_datetime.date()) in set(queued)

    def test_drops_the_unlinked_score_at_a_deleted_copys_end(self, db: Session) -> None:
        ds = _source(ProviderName.GARMIN)
        old = _sleep(ds, "summary-1")
        new = _sleep(ds, "summary-1", start=START + timedelta(hours=1), ingested=12)
        stale = HealthScoreFactory(data_source_id=None, user_id=ds.user_id, recorded_at=old.end_datetime)
        kept = HealthScoreFactory(data_source_id=None, user_id=ds.user_id, recorded_at=new.end_datetime)
        stale_id = stale.id

        assert dedupe_sleep(db, dry_run=False) == 1
        db.expire_all()

        assert db.get(HealthScore, stale_id) is None
        assert db.get(HealthScore, kept.id) is not None

    def test_undated_partial_syncs_keep_the_copy_spanning_the_night(self, db: Session) -> None:
        ds = _source(ProviderName.APPLE)
        stub = _sleep(ds, "uuid-1", hours=1, undated=True)
        whole = _sleep(ds, "uuid-1", hours=8, undated=True)
        partial = _sleep(ds, "uuid-1", hours=3, undated=True)
        stub_id, partial_id = stub.id, partial.id

        assert dedupe_sleep(db, dry_run=False) == 2
        db.expire_all()

        assert db.get(EventRecord, whole.id) is not None
        assert db.get(EventRecord, stub_id) is None
        assert db.get(EventRecord, partial_id) is None

    def test_undated_copies_none_spanning_the_night_are_left_alone(self, db: Session) -> None:
        ds = _source(ProviderName.APPLE)
        first_half = _sleep(ds, "uuid-1", hours=4, undated=True)
        second_half = _sleep(ds, "uuid-1", start=START + timedelta(hours=4), hours=4, undated=True)

        assert dedupe_sleep(db, dry_run=False) == 0
        db.expire_all()

        assert db.get(EventRecord, first_half.id) is not None
        assert db.get(EventRecord, second_half.id) is not None

    def test_shared_id_of_nights_apart_is_not_a_duplicate(self, db: Session) -> None:
        ds = _source(ProviderName.WHOOP)
        _sleep(ds, "night-1")
        _sleep(ds, "night-1", start=START + timedelta(days=3), ingested=72)

        assert dedupe_sleep(db, dry_run=False) == 0

    def test_garmin_naps_get_their_own_id_and_are_kept(self, db: Session) -> None:
        ds = _source(ProviderName.GARMIN)
        night = _sleep(ds, "summary-1", in_bed=480)
        nap_start = START + timedelta(hours=15)
        nap = _sleep(ds, "summary-1", start=nap_start, hours=0.5, is_nap=True, ingested=1)

        assert dedupe_sleep(db, dry_run=False) == 0
        db.expire_all()

        assert db.get(EventRecord, night.id).external_id == "summary-1"
        assert db.get(EventRecord, nap.id).external_id == f"summary-1-nap-{int(nap_start.timestamp())}"

    def test_dry_run_changes_nothing_and_rerun_is_a_noop(self, db: Session) -> None:
        ds = _source(ProviderName.GARMIN)
        old = _sleep(ds, "summary-1", in_bed=480)
        new = _sleep(ds, "summary-1", start=START + timedelta(hours=3), ingested=12, in_bed=420)
        nap = _sleep(ds, "summary-1", start=START + timedelta(hours=16), hours=0.5, is_nap=True, ingested=1)
        old_id, nap_id = old.id, nap.id

        assert dedupe_sleep(db, dry_run=True) == 1
        db.expire_all()
        assert db.get(EventRecord, old_id) is not None
        assert db.get(EventRecord, nap_id).external_id == "summary-1"

        assert dedupe_sleep(db, dry_run=False) == 1
        db.expire_all()
        assert db.get(EventRecord, old_id) is None
        assert db.get(SleepDetails, new.id).sleep_time_in_bed_minutes == 420
        assert db.get(EventRecord, nap_id) is not None
        assert dedupe_sleep(db, dry_run=False) == 0
