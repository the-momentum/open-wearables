"""Tests for the repair of HealthKit condensed series stored over their originals (#1983): the task and its script."""

import importlib.util
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.integrations.celery.tasks import repair_condensed_series_task
from app.integrations.celery.tasks.repair_condensed_series_task import (
    MIGRATION,
    repair_condensed_series,
    repair_sources,
)
from app.integrations.redis_client import get_redis_client
from app.integrations.rollup_queue import pop_dirty_days
from app.models import DataSource, SeriesSample, SeriesTypeDefinition, User
from app.repositories.data_migration_repository import DataMigrationRepository
from app.schemas.enums import ProviderName, SeriesType
from app.services.timeseries_service import timeseries_service
from tests.factories import DataPointSeriesFactory, DataSourceFactory, EventRecordFactory, UserFactory
from tests.fixtures.healthkit_records import (
    ACTIVE_ENERGY,
    APPLE_WATCH_APP_ID,
    healthkit_record,
    load_healthkit_records,
    stored_samples,
)

_SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "data_migrations" / "repair_condensed_series.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("repair_condensed_series", _SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_script = _load_module()
_TASK = "app.integrations.celery.tasks.repair_condensed_series_task"

NOW = datetime(2026, 11, 5, 12, tzinfo=timezone.utc)
START = datetime(2026, 7, 2, 22, 27, tzinfo=timezone.utc)


def _source(user: User | None = None, model: str = "Watch6,18", app_id: str = APPLE_WATCH_APP_ID) -> DataSource:
    return DataSourceFactory(user=user, provider=ProviderName.APPLE, source_app_id=app_id, device_model=model)


def _sample(
    db: Session,
    source: DataSource,
    series_type: SeriesType,
    at: datetime,
    value: str,
    window: int | None = None,
    external_id: str | None = None,
) -> SeriesSample:
    """Windowed rows get an external id as the SDK's series always have one."""
    if window and external_id is None:
        external_id = str(uuid4())
    definition = db.query(SeriesTypeDefinition).filter_by(code=series_type.value).one()
    return DataPointSeriesFactory(
        data_source=source,
        series_type=definition,
        recorded_at=at,
        value=Decimal(value),
        window_seconds=window,
        external_id=external_id,
        zone_offset="+02:00",
    )


def _workout(source: DataSource, start: datetime = START, end: datetime | None = None) -> None:
    """An Apple workout of the source's user, from five minutes before start to end, by default an hour after start."""
    EventRecordFactory(
        data_source=source,
        category="workout",
        type_="running",
        start_datetime=start - timedelta(minutes=5),
        end_datetime=end or start + timedelta(hours=1),
    )


def _originals(
    db: Session,
    source: DataSource,
    first_minute: int = 1,
    series_type: SeriesType = SeriesType.active_energy,
    value: str = "1.5",
) -> None:
    """A workout's samples stored before samples kept a window: one a minute up to minute 9 (1.5 kcal by default)."""
    for minute in range(first_minute, 10):
        _sample(db, source, series_type, START + timedelta(minutes=minute), value)


def _repair(db: Session) -> Counter[str]:
    return repair_sources(db, None, 60, now=NOW).done


def _session(db: Session) -> MagicMock:
    session = MagicMock()
    session.__enter__.return_value = db
    return session


def _row(db: Session, sample: SeriesSample) -> SeriesSample | None:
    identity = inspect(sample).identity  # the commit expired the sample, and a deleted one can't reload its id
    assert identity is not None
    db.expire_all()
    return db.get(SeriesSample, identity)


class TestRepairCondensedSeries:
    @pytest.mark.parametrize(
        ("series_type", "minute_value", "series_value"),
        [
            (SeriesType.active_energy, "1.5", "15"),
            (SeriesType.basal_energy, "1.2", "12"),
            (SeriesType.distance_walking_running, "80", "800"),
        ],
    )
    def test_a_series_that_replaced_an_original_gives_it_back(
        self, db: Session, series_type: SeriesType, minute_value: str, series_value: str
    ) -> None:
        source = _source()
        _workout(source)
        _originals(db, source, series_type=series_type, value=minute_value)  # minutes 1-9; minute 0 was replaced
        series = _sample(db, source, series_type, START, series_value, window=600, external_id="SERIES")

        assert _repair(db) == Counter(restored=1)
        repaired = _row(db, series)
        assert repaired is not None
        assert (repaired.value, repaired.window_seconds, repaired.external_id) == (Decimal(minute_value), None, None)

    def test_a_series_that_replaced_nothing_is_deleted(self, db: Session) -> None:
        source = _source()
        _workout(source)
        _originals(db, source, first_minute=0)  # 15 kcal
        series = _sample(db, source, SeriesType.active_energy, START - timedelta(seconds=30), "15", window=630)

        assert _repair(db) == Counter(deleted=1)
        assert _row(db, series) is None

    def test_a_heart_rate_series_is_deleted(self, db: Session) -> None:
        source = _source()
        _workout(source)
        for second in range(30, 300, 30):
            _sample(db, source, SeriesType.heart_rate, START + timedelta(seconds=second), "140")
        series = _sample(db, source, SeriesType.heart_rate, START, "144.5", window=300)

        assert _repair(db) == Counter(deleted=1)
        assert _row(db, series) is None

    def test_heart_rate_series_covering_only_each_other_are_kept(self, db: Session) -> None:
        user = UserFactory()
        watch = _source(user)
        phone = _source(user, model="iPhone15,2")
        _workout(watch)
        # a series and its re-condensation filed under the phone cover each other and a later one, but no readings
        series = [
            _sample(db, watch, SeriesType.heart_rate, START, "144", window=600),
            _sample(db, phone, SeriesType.heart_rate, START, "146", window=600),
            _sample(db, watch, SeriesType.heart_rate, START + timedelta(minutes=5), "150", window=300),
        ]

        assert _repair(db) == Counter(kept=2)
        rows = [_row(db, sample) for sample in series]
        assert [(row.value, row.window_seconds) for row in rows if row] == [
            (Decimal("144"), 600),
            (Decimal("146"), 600),
            (Decimal("150"), 300),
        ]

    def test_a_series_filed_under_another_model_is_matched_with_the_watch(self, db: Session) -> None:
        user = UserFactory()
        watch = _source(user)
        _workout(watch)
        _originals(db, watch, first_minute=0)
        series = _sample(db, _source(user, model="iPhone15,2"), SeriesType.active_energy, START, "15", window=600)

        assert _repair(db) == Counter(deleted=1)
        assert _row(db, series) is None

    def test_leaves_samples_that_are_not_condensed_series_alone(self, db: Session) -> None:
        user = UserFactory()
        watch = _source(user)
        _workout(watch)
        _originals(db, watch)
        recent = NOW - timedelta(days=1)
        _workout(watch, recent)
        for minute in (1, 2):
            _sample(db, watch, SeriesType.active_energy, recent + timedelta(minutes=minute), "1")
        oura = _source(user, model="Oura Ring", app_id="com.ouraring.oura")
        for minute in (1, 2):
            _sample(db, oura, SeriesType.active_energy, START + timedelta(minutes=minute), "1")
        untouched = [
            # covers nothing
            _sample(db, watch, SeriesType.active_energy, START + timedelta(minutes=20), "3", window=600),
            # far above what it covers
            _sample(db, watch, SeriesType.active_energy, START, "40", window=600),
            # too recent
            _sample(db, watch, SeriesType.active_energy, recent, "2", window=600),
            # a third-party app
            _sample(db, oura, SeriesType.active_energy, START, "2", window=600),
        ]

        assert _repair(db) == Counter(kept=1)
        assert [row.window_seconds for row in (_row(db, sample) for sample in untouched) if row] == [600] * 4

    def test_a_second_run_changes_nothing(self, db: Session) -> None:
        source = _source()
        _workout(source)
        _originals(db, source)
        _sample(db, source, SeriesType.active_energy, START, "15", window=600)
        _repair(db)

        assert _repair(db) == Counter()

    def test_queues_the_local_days_for_the_rollup(self, db: Session) -> None:
        source = _source()
        _workout(source)
        _originals(db, source)
        _sample(db, source, SeriesType.active_energy, START, "15", window=600)
        pop_dirty_days(100)

        _repair(db)

        assert pop_dirty_days(100) == [(source.id, date(2026, 7, 3))]

    def test_dry_run_changes_nothing(self, db: Session) -> None:
        source = _source()
        _workout(source)
        _originals(db, source)
        series = _sample(db, source, SeriesType.active_energy, START, "15", window=600)

        assert _script.count_repairs(db, now=NOW) == Counter({("active_energy", "restored"): 1})
        repaired = _row(db, series)
        assert repaired is not None
        assert repaired.value == Decimal("15")

    def test_leaves_a_series_outside_any_workout_alone(self, db: Session) -> None:
        source = _source()
        _workout(source, START - timedelta(hours=5))
        _originals(db, source)
        series = _sample(db, source, SeriesType.active_energy, START, "15", window=600)

        assert _repair(db) == Counter()
        assert _row(db, series) is not None

    def test_a_series_a_little_below_the_sum_is_deleted(self, db: Session) -> None:
        source = _source()
        _workout(source)
        _originals(db, source)  # 13.5 kcal
        series = _sample(db, source, SeriesType.active_energy, START, "13.4", window=600)

        assert _repair(db) == Counter(deleted=1)
        assert _row(db, series) is None

    def test_leaves_a_row_that_covers_one_sample_alone(self, db: Session) -> None:
        source = _source()
        _workout(source)
        _sample(db, source, SeriesType.active_energy, START + timedelta(minutes=1), "1.5")
        series = _sample(db, source, SeriesType.active_energy, START, "3", window=600)

        assert _repair(db) == Counter()
        assert _row(db, series) is not None

    def test_repairs_the_sources_of_two_users_in_one_run(self, db: Session) -> None:
        for _ in range(2):
            source = _source()
            _workout(source)
            _originals(db, source)
            _sample(db, source, SeriesType.active_energy, START, "15", window=600)

        assert _repair(db) == Counter(restored=2)

    def test_a_series_starting_just_before_its_workout_is_repaired(self, db: Session) -> None:
        source = _source()
        _workout(source, START + timedelta(minutes=5))  # starts at START
        _originals(db, source, first_minute=0)  # 15 kcal
        series = _sample(db, source, SeriesType.active_energy, START - timedelta(seconds=30), "15", window=630)

        assert _repair(db) == Counter(deleted=1)
        assert _row(db, series) is None

    def test_a_workout_stored_in_two_sources_counts_the_series_once(self, db: Session) -> None:
        user = UserFactory()
        watch = _source(user)
        xml = DataSourceFactory(user=user, provider=ProviderName.APPLE, source="apple_health_xml", source_app_id=None)
        _workout(watch)
        _workout(xml)
        _originals(db, watch)
        _sample(db, watch, SeriesType.active_energy, START, "15", window=600)

        assert _repair(db) == Counter(restored=1)

    def test_two_copies_of_one_series_in_sibling_sources_are_repaired_once(self, db: Session) -> None:
        user = UserFactory()
        watch = _source(user)
        phone = _source(user, model="iPhone15,2")
        _workout(watch)
        _originals(db, watch)
        for source in (watch, phone):  # copies of one HealthKit series share its UUID
            _sample(db, source, SeriesType.active_energy, START, "15", window=600, external_id="SERIES")

        assert _repair(db) == Counter(restored=1, deleted=1)
        assert sum(value for *_, value in stored_samples(db)) == Decimal("15")

    def test_a_series_inside_two_overlapping_workouts_is_repaired_once(self, db: Session) -> None:
        source = _source()
        _workout(source)  # START-5min .. START+1h
        _workout(source, START + timedelta(minutes=15), START + timedelta(hours=2))  # START+10min .. START+2h
        for minute in range(13, 22):  # inside both workouts; minute 12 was replaced
            _sample(db, source, SeriesType.active_energy, START + timedelta(minutes=minute), "1.5")
        _sample(db, source, SeriesType.active_energy, START + timedelta(minutes=12), "15", window=600)

        assert _repair(db) == Counter(restored=1)

    def test_a_failing_source_does_not_stop_the_others(self, db: Session) -> None:
        series = []
        for _ in range(2):
            source = _source()
            _workout(source)
            _originals(db, source)
            series.append(_sample(db, source, SeriesType.active_energy, START, "15", window=600))
        db.commit()  # the failed source's rollback must not undo the test data
        real = timeseries_service.stored_in_windows
        calls = 0

        def lookup(*args: Any, **kwargs: Any) -> Any:
            nonlocal calls
            calls += 1
            if calls == 1:
                raise RuntimeError("lock timeout")
            return real(*args, **kwargs)

        with (
            patch.object(timeseries_service, "stored_in_windows", side_effect=lookup),
            patch.object(repair_condensed_series_task, "logger") as logger,
        ):
            done = _repair(db)

        assert done == Counter(restored=1, failed=1)
        logger.error.assert_called_once()
        assert isinstance(logger.error.call_args.kwargs["exc_info"], RuntimeError)
        values = sorted(row.value for row in (_row(db, sample) for sample in series) if row)
        assert values == [Decimal("1.5"), Decimal("15")]

    def test_a_spent_budget_stops_after_the_source_and_resumes_from_it(self, db: Session) -> None:
        sources = sorted((_source() for _ in range(2)), key=lambda source: source.id)
        for source in sources:
            _workout(source)
            _originals(db, source)
            _sample(db, source, SeriesType.active_energy, START, "15", window=600)

        assert repair_sources(db, None, 0, now=NOW) == (sources[0].id, Counter(restored=1), False)
        assert repair_sources(db, sources[0].id, 60, now=NOW) == (sources[1].id, Counter(restored=1), True)

    def test_a_run_stops_once_its_lock_is_lost(self, db: Session) -> None:
        sources = sorted((_source() for _ in range(2)), key=lambda source: source.id)

        assert repair_sources(db, None, 60, keep_alive=lambda: False, now=NOW) == (sources[0].id, Counter(), False)

    def test_a_restored_series_sent_again_is_dropped_at_ingest(self, db: Session) -> None:
        source = _source()
        _workout(source)
        _originals(db, source)
        _sample(db, source, SeriesType.active_energy, START, "15", window=600, external_id="SERIES")
        assert _repair(db) == Counter(restored=1)
        stored = stored_samples(db)
        load_healthkit_records(
            db, str(source.user_id), [healthkit_record(ACTIVE_ENERGY, START, 600, "15", record_id="SERIES")]
        )

        assert len(stored) == 10
        assert stored_samples(db) == stored


class TestRepairCondensedSeriesTask:
    def test_records_the_migration_once_every_source_is_done(self, db: Session) -> None:
        source = _source()
        _workout(source)
        _originals(db, source)
        _sample(db, source, SeriesType.active_energy, START, "15", window=600)

        with patch(f"{_TASK}.SessionLocal", return_value=_session(db)):
            assert repair_condensed_series() == {"finished": True, "failed": 0, "restored": 1, "deleted": 0, "kept": 0}
            assert repair_condensed_series() == {"skipped": "done"}

        assert DataMigrationRepository().is_completed(db, MIGRATION)

    def test_a_failed_source_leaves_the_migration_for_the_next_startup(self, db: Session) -> None:
        source = _source()
        _workout(source)
        _originals(db, source)
        _sample(db, source, SeriesType.active_energy, START, "15", window=600)
        db.commit()

        with (
            patch(f"{_TASK}.SessionLocal", return_value=_session(db)),
            patch.object(timeseries_service, "stored_in_windows", side_effect=RuntimeError("boom")),
        ):
            assert repair_condensed_series()["failed"] == 1

        assert not DataMigrationRepository().is_completed(db, MIGRATION)

    def test_an_unfinished_run_queues_the_next_from_its_cursor(self, db: Session) -> None:
        source = _source()

        with (
            patch(f"{_TASK}.SessionLocal", return_value=_session(db)),
            patch(f"{_TASK}._BUDGET_SECONDS", 0),
            patch.object(repair_condensed_series, "apply_async") as apply_async,
        ):
            assert repair_condensed_series()["finished"] is False

        assert apply_async.call_args.kwargs["kwargs"] == {"after": str(source.id), "failed": 0}

    def test_a_run_waits_out_one_already_in_progress(self, db: Session) -> None:
        get_redis_client().set("repair_condensed_series:lock", "1")

        assert repair_condensed_series() == {"skipped": "previous_run_in_progress"}


class TestScript:
    def test_queues_the_task_until_it_is_done(self, db: Session) -> None:
        with (
            patch.object(_script, "SessionLocal", return_value=_session(db)),
            patch.object(_script, "create_celery"),
            patch.object(_script.repair_condensed_series, "delay") as delay,
        ):
            _script.main(dry_run=False)
            DataMigrationRepository().mark_completed(db, MIGRATION)
            _script.main(dry_run=False)

        delay.assert_called_once()
