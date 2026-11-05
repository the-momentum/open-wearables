import importlib.util
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import ModuleType
from uuid import uuid4

import pytest
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.integrations.rollup_queue import pop_dirty_days
from app.models import DataSource, SeriesSample, SeriesTypeDefinition, User
from app.schemas.enums import ProviderName, SeriesType, get_series_type_id
from tests.factories import (
    APPLE_WATCH_APP_ID,
    DataPointSeriesFactory,
    DataSourceFactory,
    EventRecordFactory,
    UserFactory,
)
from tests.fixtures.healthkit_records import ACTIVE_ENERGY, healthkit_record, load_healthkit_records

_SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "data_migrations" / "repair_condensed_series.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("repair_condensed_series", _SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_module = _load_module()
repair_condensed_series = _module.repair_condensed_series
migrate = _module._migrate

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


def _workout(source: DataSource, start: datetime = START) -> None:
    """An Apple workout of the source's user, from five minutes before start to an hour after it."""
    EventRecordFactory(
        data_source=source,
        category="workout",
        type_="running",
        start_datetime=start - timedelta(minutes=5),
        end_datetime=start + timedelta(hours=1),
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


def _row(db: Session, sample: SeriesSample) -> SeriesSample | None:
    identity = inspect(sample).identity  # the commit expired the sample, and a deleted one can't reload its id
    assert identity is not None
    db.expire_all()
    return db.get(SeriesSample, identity)


def _active_energy(db: Session) -> list[tuple[datetime, int | None, str | None, Decimal]]:
    db.expire_all()
    rows = (
        db.query(SeriesSample)
        .filter(SeriesSample.series_type_definition_id == get_series_type_id(SeriesType.active_energy))
        .order_by(SeriesSample.recorded_at)
        .all()
    )
    return [(row.recorded_at, row.window_seconds, row.external_id, row.value) for row in rows]


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

        assert repair_condensed_series(db, dry_run=False, now=NOW) == Counter(restored=1)
        repaired = _row(db, series)
        assert repaired is not None
        assert (repaired.value, repaired.window_seconds, repaired.external_id) == (Decimal(minute_value), None, None)

    def test_a_series_that_replaced_nothing_is_deleted(self, db: Session) -> None:
        source = _source()
        _workout(source)
        _originals(db, source, first_minute=0)  # 15 kcal
        series = _sample(db, source, SeriesType.active_energy, START - timedelta(seconds=30), "15", window=630)

        assert repair_condensed_series(db, dry_run=False, now=NOW) == Counter(deleted=1)
        assert _row(db, series) is None

    def test_a_heart_rate_series_is_deleted(self, db: Session) -> None:
        source = _source()
        _workout(source)
        for second in range(30, 300, 30):
            _sample(db, source, SeriesType.heart_rate, START + timedelta(seconds=second), "140")
        series = _sample(db, source, SeriesType.heart_rate, START, "144.5", window=300)

        assert repair_condensed_series(db, dry_run=False, now=NOW) == Counter(deleted=1)
        assert _row(db, series) is None

    def test_a_series_filed_under_another_model_is_matched_with_the_watch(self, db: Session) -> None:
        user = UserFactory()
        watch = _source(user)
        _workout(watch)
        _originals(db, watch, first_minute=0)
        series = _sample(db, _source(user, "iPhone15,2"), SeriesType.active_energy, START, "15", window=600)

        assert repair_condensed_series(db, dry_run=False, now=NOW) == Counter(deleted=1)
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
        oura = _source(user, "Oura Ring", app_id="com.ouraring.oura")
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

        assert repair_condensed_series(db, dry_run=False, now=NOW) == Counter(kept=1)
        assert [row.window_seconds for row in (_row(db, sample) for sample in untouched) if row] == [600] * 4

    def test_a_second_run_changes_nothing(self, db: Session) -> None:
        source = _source()
        _workout(source)
        _originals(db, source)
        _sample(db, source, SeriesType.active_energy, START, "15", window=600)
        repair_condensed_series(db, dry_run=False, now=NOW)

        assert repair_condensed_series(db, dry_run=False, now=NOW) == Counter()

    def test_queues_the_local_days_for_the_rollup(self, db: Session) -> None:
        source = _source()
        _workout(source)
        _originals(db, source)
        _sample(db, source, SeriesType.active_energy, START, "15", window=600)
        pop_dirty_days(100)

        repair_condensed_series(db, dry_run=False, now=NOW)

        assert pop_dirty_days(100) == [(source.id, date(2026, 7, 3))]

    def test_dry_run_changes_nothing(self, db: Session) -> None:
        source = _source()
        _workout(source)
        _originals(db, source)
        series = _sample(db, source, SeriesType.active_energy, START, "15", window=600)

        assert repair_condensed_series(db, dry_run=True, now=NOW) == Counter(restored=1)
        repaired = _row(db, series)
        assert repaired is not None
        assert repaired.value == Decimal("15")

    def test_leaves_a_series_outside_any_workout_alone(self, db: Session) -> None:
        source = _source()
        _workout(source, START - timedelta(hours=5))
        _originals(db, source)
        series = _sample(db, source, SeriesType.active_energy, START, "15", window=600)

        assert repair_condensed_series(db, dry_run=False, now=NOW) == Counter()
        assert _row(db, series) is not None

    def test_a_series_a_little_below_the_sum_is_deleted(self, db: Session) -> None:
        source = _source()
        _workout(source)
        _originals(db, source)  # 13.5 kcal
        series = _sample(db, source, SeriesType.active_energy, START, "13.4", window=600)

        assert repair_condensed_series(db, dry_run=False, now=NOW) == Counter(deleted=1)
        assert _row(db, series) is None

    def test_leaves_a_row_that_covers_one_sample_alone(self, db: Session) -> None:
        source = _source()
        _workout(source)
        _sample(db, source, SeriesType.active_energy, START + timedelta(minutes=1), "1.5")
        series = _sample(db, source, SeriesType.active_energy, START, "3", window=600)

        assert repair_condensed_series(db, dry_run=False, now=NOW) == Counter()
        assert _row(db, series) is not None

    def test_repairs_the_sources_of_two_users_in_one_run(self, db: Session) -> None:
        for _ in range(2):
            source = _source()
            _workout(source)
            _originals(db, source)
            _sample(db, source, SeriesType.active_energy, START, "15", window=600)

        assert repair_condensed_series(db, dry_run=False, now=NOW) == Counter(restored=2)

    def test_a_series_starting_just_before_its_workout_is_repaired(self, db: Session) -> None:
        source = _source()
        _workout(source, START + timedelta(minutes=5))  # starts at START
        _originals(db, source, first_minute=0)  # 15 kcal
        series = _sample(db, source, SeriesType.active_energy, START - timedelta(seconds=30), "15", window=630)

        assert repair_condensed_series(db, dry_run=False, now=NOW) == Counter(deleted=1)
        assert _row(db, series) is None

    def test_a_workout_stored_in_two_sources_counts_the_series_once(self, db: Session) -> None:
        user = UserFactory()
        watch = _source(user)
        xml = DataSourceFactory(user=user, provider=ProviderName.APPLE, source="apple_health_xml", source_app_id=None)
        _workout(watch)
        _workout(xml)
        _originals(db, watch)
        _sample(db, watch, SeriesType.active_energy, START, "15", window=600)

        assert repair_condensed_series(db, dry_run=False, now=NOW) == Counter(restored=1)

    def test_two_copies_of_one_series_in_sibling_sources_are_repaired_once(self, db: Session) -> None:
        user = UserFactory()
        watch = _source(user)
        phone = _source(user, model="iPhone15,2")
        _workout(watch)
        _originals(db, watch)
        for source in (watch, phone):  # copies of one HealthKit series share its UUID
            _sample(db, source, SeriesType.active_energy, START, "15", window=600, external_id="SERIES")

        assert repair_condensed_series(db, dry_run=False, now=NOW) == Counter(restored=1, deleted=1)
        assert sum(value for *_, value in _active_energy(db)) == Decimal("15")

    def test_a_series_inside_two_overlapping_workouts_is_repaired_once(self, db: Session) -> None:
        source = _source()
        _workout(source)  # START-5min .. START+1h
        EventRecordFactory(
            data_source=source,
            category="workout",
            type_="running",
            start_datetime=START + timedelta(minutes=10),
            end_datetime=START + timedelta(hours=2),
        )
        for minute in range(13, 22):  # inside both workouts; minute 12 was replaced
            _sample(db, source, SeriesType.active_energy, START + timedelta(minutes=minute), "1.5")
        _sample(db, source, SeriesType.active_energy, START + timedelta(minutes=12), "15", window=600)

        assert repair_condensed_series(db, dry_run=False, now=NOW) == Counter(restored=1)

    def test_the_migration_reports_whether_it_changed_anything(self, db: Session) -> None:
        assert migrate(db, dry_run=False) is True
        assert migrate(db, dry_run=True) is False

    def test_a_restored_series_sent_again_is_dropped_at_ingest(self, db: Session) -> None:
        source = _source()
        _workout(source)
        _originals(db, source)
        _sample(db, source, SeriesType.active_energy, START, "15", window=600, external_id="SERIES")
        assert repair_condensed_series(db, dry_run=False, now=NOW) == Counter(restored=1)
        stored = _active_energy(db)
        load_healthkit_records(
            db,
            str(source.user_id),
            [healthkit_record(ACTIVE_ENERGY, START, 600, "15", record_id="SERIES", hardware="Watch6,18")],
        )

        assert len(stored) == 10
        assert _active_energy(db) == stored
