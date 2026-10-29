import importlib
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy.orm import Session

from app.integrations.redis_client import get_redis_client
from app.integrations.rollup_queue import (
    DELETED_BEFORE_KEY,
    DIRTY_DAYS_KEY,
    IN_PROGRESS_KEY,
    pop_dirty_days,
    recover_dirty_days,
    requeue_dirty_days,
)
from app.models import (
    EventRecord,
    EventRecordAggregate,
    EventRecordDetail,
    SeriesAggregate,
    SeriesSample,
    SeriesTypeDefinition,
    WorkoutDetails,
)
from app.models.archival_setting import ArchivalSetting
from app.repositories import AggregateRepository, DataPointSeriesRepository, EventRecordDetailRepository
from app.repositories.event_record_repository import EventRecordRepository
from app.repositories.series_rollup_repository import SeriesRollupRepository, _runs
from app.schemas.enums import ComputedBy, PeriodKind, SeriesType, get_series_type_id
from app.schemas.model_crud.activities import (
    CalendarPeriod,
    EventRecordCreate,
    EventRecordDetailCreate,
    SessionValue,
    TimeSeriesSampleCreate,
)
from app.services.archival_service import archival_service
from tests.factories import (
    DataPointSeriesFactory,
    DataSourceFactory,
    EventRecordFactory,
    SeriesTypeDefinitionFactory,
    UserFactory,
)

# app.services exports the service instance under the module's name, so patch the module itself.
_ARCHIVAL_SERVICE = importlib.import_module("app.services.archival_service")

DAY = date(2099, 1, 1)


class TestCalendarPeriod:
    def test_a_date_without_offset_is_its_utc_day(self) -> None:
        period = CalendarPeriod.of_date(DAY)

        assert (period.start, period.end, period.zone_offset) == (
            datetime(2099, 1, 1, tzinfo=timezone.utc),
            datetime(2099, 1, 2, tzinfo=timezone.utc),
            "+00:00",
        )

    def test_a_date_with_offset_starts_at_local_midnight(self) -> None:
        period = CalendarPeriod.of_date("2099-01-01", "-05:00")

        assert period.start == datetime(2099, 1, 1, 5, tzinfo=timezone.utc)
        # What readers do in SQL: the UTC instant plus the offset gives the local date.
        assert (period.start.astimezone(timezone.utc) + timedelta(hours=-5)).date() == DAY

    def test_a_local_day_keeps_the_length_the_provider_reports(self) -> None:
        start = datetime(2099, 3, 28, 23, tzinfo=timezone.utc)

        period = CalendarPeriod.local_day(start, 82800, "+01:00")

        assert (period.end - period.start, period.zone_offset) == (timedelta(hours=23), "+01:00")

    def test_utc_spelled_z_is_the_zero_offset(self) -> None:
        # Whoop sends "Z" for a UTC cycle; the sample's ZoneOffset accepts it, so must the period.
        start = datetime(2099, 1, 1, tzinfo=timezone.utc)

        assert CalendarPeriod.local_day(start, zone_offset="Z").zone_offset == "+00:00"
        assert CalendarPeriod.of_date(DAY, "Z").start == start
        assert CalendarPeriod(start=start, end=start + timedelta(days=1), zone_offset="Z").zone_offset == "+00:00"


class TestAggregateRepository:
    def _row(self, source_id: object, computed_by: ComputedBy, day: date = DAY, **stats: Decimal) -> dict:
        period = CalendarPeriod.of_date(day)
        return {
            "data_source_id": source_id,
            "series_type_definition_id": get_series_type_id(SeriesType.steps),
            "period_kind": PeriodKind.DAY,
            "period_start": period.start,
            "period_end": period.end,
            "zone_offset": period.zone_offset,
            "computed_by": computed_by,
            "count": 1,
            **stats,
        }

    def test_the_same_period_is_refreshed_in_place(self, db: Session) -> None:
        source = DataSourceFactory()
        repo = AggregateRepository(SeriesAggregate)

        repo.upsert(db, [self._row(source.id, ComputedBy.PROVIDER, sum=Decimal("8000"))])
        repo.upsert(db, [self._row(source.id, ComputedBy.PROVIDER, sum=Decimal("8432"))])

        assert [(row.sum, row.avg) for row in db.query(SeriesAggregate)] == [(Decimal("8432"), None)]

    def test_a_statistic_past_the_old_column_is_kept_at_seven_places(self, db: Session) -> None:
        source = DataSourceFactory()
        repo = AggregateRepository(SeriesAggregate)

        repo.upsert(
            db,
            [self._row(source.id, ComputedBy.OPEN_WEARABLES, sum=Decimal("20412345.5"), avg=Decimal(2) / Decimal(3))],
        )

        assert [(row.sum, row.avg) for row in db.query(SeriesAggregate)] == [
            (Decimal("20412345.5"), Decimal("0.6666667"))
        ]

    def test_provider_and_own_values_for_one_day_stay_apart(self, db: Session) -> None:
        source = DataSourceFactory()

        AggregateRepository(SeriesAggregate).upsert(
            db,
            [
                self._row(source.id, ComputedBy.PROVIDER, sum=Decimal("8432")),
                self._row(source.id, ComputedBy.OPEN_WEARABLES, sum=Decimal("8100")),
            ],
        )

        assert {(row.computed_by, row.sum) for row in db.query(SeriesAggregate)} == {
            (ComputedBy.PROVIDER, Decimal("8432")),
            (ComputedBy.OPEN_WEARABLES, Decimal("8100")),
        }

    def test_rows_sharing_a_key_merge_their_statistics(self, db: Session) -> None:
        source = DataSourceFactory()

        AggregateRepository(SeriesAggregate).upsert(
            db,
            [
                self._row(source.id, ComputedBy.PROVIDER, min=Decimal("48")),
                self._row(source.id, ComputedBy.PROVIDER, max=Decimal("162")),
            ],
        )

        assert [(row.min, row.max) for row in db.query(SeriesAggregate)] == [(Decimal("48"), Decimal("162"))]

    def test_a_later_write_keeps_the_statistics_it_does_not_carry(self, db: Session) -> None:
        source = DataSourceFactory()
        repo = AggregateRepository(SeriesAggregate)

        repo.upsert(db, [self._row(source.id, ComputedBy.PROVIDER, min=Decimal("48"))])
        repo.upsert(db, [self._row(source.id, ComputedBy.PROVIDER, max=Decimal("162"))])

        assert [(row.min, row.max) for row in db.query(SeriesAggregate)] == [(Decimal("48"), Decimal("162"))]

    def test_a_write_past_postgres_bind_parameter_limit_lands_whole(self, db: Session) -> None:
        """5,000 rows of 14 columns would be 70,000 parameters in one statement; PostgreSQL takes 65,535."""
        source = DataSourceFactory()
        days = [DAY - timedelta(days=n) for n in range(5000)]

        written = AggregateRepository(SeriesAggregate).upsert(
            db, [self._row(source.id, ComputedBy.OPEN_WEARABLES, day, sum=Decimal(n)) for n, day in enumerate(days)]
        )

        assert written == db.query(SeriesAggregate).count() == 5000

    def test_insert_missing_counts_only_the_rows_it_added(self, db: Session) -> None:
        source = DataSourceFactory()
        repo = AggregateRepository(SeriesAggregate)
        repo.upsert(db, [self._row(source.id, ComputedBy.OPEN_WEARABLES, sum=Decimal("8000"))])

        inserted = repo.insert_missing(
            db,
            [
                self._row(source.id, ComputedBy.OPEN_WEARABLES, DAY - timedelta(days=n), sum=Decimal("1"))
                for n in range(3)
            ],
        )

        assert inserted == 2
        assert sorted(row.sum for row in db.query(SeriesAggregate)) == [Decimal("1"), Decimal("1"), Decimal("8000")]


class TestDayValuesMirroredFromSamples:
    def _sample(
        self, user_id: object, series_type: SeriesType, period: CalendarPeriod | None
    ) -> TimeSeriesSampleCreate:
        return TimeSeriesSampleCreate(
            id=uuid4(),
            user_id=user_id,
            source="garmin",
            recorded_at=datetime(2099, 1, 1, 12, tzinfo=timezone.utc),
            value=Decimal("47.5"),
            series_type=series_type,
            period=period,
        )

    def test_a_day_value_lands_in_the_column_its_series_is_read_from(self, db: Session) -> None:
        user = UserFactory()
        period = CalendarPeriod.of_date(DAY, "+02:00")

        DataPointSeriesRepository(SeriesSample).bulk_create(db, [self._sample(user.id, SeriesType.vo2_max, period)])

        sample = db.query(SeriesSample).one()
        aggregate = db.query(SeriesAggregate).one()
        assert aggregate.data_source_id == sample.data_source_id
        assert (aggregate.period_start, aggregate.zone_offset) == (period.start, "+02:00")
        assert (aggregate.avg, aggregate.sum, aggregate.computed_by, aggregate.count) == (
            Decimal("47.5"),
            None,
            ComputedBy.PROVIDER,
            1,
        )

    def test_a_sample_without_a_period_writes_no_aggregate(self, db: Session) -> None:
        user = UserFactory()

        DataPointSeriesRepository(SeriesSample).bulk_create(db, [self._sample(user.id, SeriesType.steps, None)])

        assert db.query(SeriesAggregate).count() == 0

    def test_a_duplicate_single_create_still_mirrors_its_period(self, db: Session) -> None:
        source = DataSourceFactory()
        sample = TimeSeriesSampleCreate(
            id=uuid4(),
            user_id=source.user_id,
            source=source.source,
            recorded_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
            value=Decimal("8432"),
            series_type=SeriesType.steps,
            period=CalendarPeriod.of_date(DAY),
        )
        repo = DataPointSeriesRepository(SeriesSample)

        repo.create(db, sample)
        repo.create(db, sample.model_copy(update={"id": uuid4(), "value": Decimal("8500")}))

        assert db.query(SeriesSample).count() == 1
        assert [row.sum for row in db.query(SeriesAggregate)] == [Decimal("8500")]

    def test_a_single_create_mirrors_its_period_too(self, db: Session) -> None:
        user = UserFactory()

        DataPointSeriesRepository(SeriesSample).create(
            db, self._sample(user.id, SeriesType.steps, CalendarPeriod.of_date(DAY))
        )

        assert [row.sum for row in db.query(SeriesAggregate)] == [Decimal("47.5")]


class TestSessionValuesMirrored:
    def test_a_session_value_lands_on_its_event_in_the_named_statistic(self, db: Session) -> None:
        source = DataSourceFactory()
        sleep = EventRecordFactory(category="sleep", data_source=source)
        sample = TimeSeriesSampleCreate(
            id=uuid4(),
            user_id=source.user_id,
            source="suunto",
            recorded_at=datetime(2099, 1, 1, 7, tzinfo=timezone.utc),
            value=Decimal("98"),
            series_type=SeriesType.oxygen_saturation,
            session=SessionValue(record_id=sleep.id, stat="max"),
        )

        DataPointSeriesRepository(SeriesSample).bulk_create(db, [sample])

        row = db.query(EventRecordAggregate).one()
        assert (row.record_id, row.series_type_definition_id) == (
            sleep.id,
            get_series_type_id(SeriesType.oxygen_saturation),
        )
        assert (row.max, row.avg, row.computed_by) == (Decimal("98"), None, ComputedBy.PROVIDER)

    def test_workout_statistics_are_mirrored_one_row_per_series(self, db: Session) -> None:
        workout = EventRecordFactory(category="workout")
        detail = EventRecordDetailCreate(
            record_id=workout.id,
            heart_rate_min=95,
            heart_rate_avg=Decimal("148"),
            heart_rate_max=181,
            energy_burned=Decimal("512"),
            energy_series=SeriesType.total_energy,
            distance=Decimal("10450"),
            total_elevation_gain=Decimal("120"),
        )

        EventRecordDetailRepository(EventRecordDetail).bulk_create(db, [detail])

        rows = {row.series_type_definition_id: row for row in db.query(EventRecordAggregate)}
        heart_rate = rows[get_series_type_id(SeriesType.heart_rate)]
        assert (heart_rate.min, heart_rate.avg, heart_rate.max) == (Decimal("95"), Decimal("148"), Decimal("181"))
        assert rows[get_series_type_id(SeriesType.distance)].sum == Decimal("10450")
        assert rows[get_series_type_id(SeriesType.elevation_gain)].sum == Decimal("120")
        assert rows[get_series_type_id(SeriesType.total_energy)].sum == Decimal("512")
        assert db.query(WorkoutDetails).one().energy_burned == Decimal("512")

    def test_a_sessions_extremes_in_one_write_keep_the_more_extreme(self, db: Session) -> None:
        workout = EventRecordFactory(category="workout")
        hr = get_series_type_id(SeriesType.heart_rate)
        rows = [
            {
                "record_id": workout.id,
                "series_type_definition_id": hr,
                "computed_by": ComputedBy.PROVIDER,
                "min": Decimal(min_),
                "max": Decimal(max_),
                "count": 1,
            }
            for min_, max_ in (("40", "150"), ("50", "140"))
        ]

        AggregateRepository(EventRecordAggregate).upsert(db, rows)

        row = db.query(EventRecordAggregate).one()
        assert (row.min, row.max) == (Decimal("40"), Decimal("150"))

    def test_a_sessions_extremes_add_up_across_writes(self, db: Session) -> None:
        """A night's lowest heart rate reported per segment, a workout's max cadence next to its mean."""
        workout = EventRecordFactory(category="workout")
        repo = AggregateRepository(EventRecordAggregate)
        row = {
            "record_id": workout.id,
            "series_type_definition_id": get_series_type_id(SeriesType.heart_rate),
            "computed_by": ComputedBy.PROVIDER,
            "count": 1,
        }

        repo.upsert(db, [row | {"min": Decimal("50"), "max": Decimal("170"), "avg": Decimal("120")}])
        repo.upsert(db, [row | {"min": Decimal("55"), "max": Decimal("180"), "avg": Decimal("130")}])

        stored = db.query(EventRecordAggregate).one()
        assert (stored.min, stored.max, stored.avg) == (Decimal("50"), Decimal("180"), Decimal("130"))

    def test_a_session_value_whose_record_is_gone_is_kept_as_a_sample(self, db: Session) -> None:
        """A sleep merged away between the lookup and the write must not fail the whole batch."""
        source = DataSourceFactory()
        sample = TimeSeriesSampleCreate(
            id=uuid4(),
            user_id=source.user_id,
            source="oura",
            recorded_at=datetime(2099, 1, 1, 7, tzinfo=timezone.utc),
            value=Decimal("48"),
            series_type=SeriesType.resting_heart_rate,
            session=SessionValue(record_id=uuid4()),
        )

        DataPointSeriesRepository(SeriesSample).bulk_create(db, [sample])

        assert db.query(SeriesSample).count() == 1
        assert db.query(EventRecordAggregate).count() == 0

    def test_a_detail_written_twice_keeps_both_writes_statistics(self, db: Session) -> None:
        """The second create() returns the stored detail and still merges its statistics into the session row."""
        workout = EventRecordFactory(category="workout")
        repo = EventRecordDetailRepository(EventRecordDetail)

        repo.create(db, EventRecordDetailCreate(record_id=workout.id, average_cadence=Decimal("82")))
        repo.create(db, EventRecordDetailCreate(record_id=workout.id, heart_rate_max=181))

        rows = {row.series_type_definition_id: row for row in db.query(EventRecordAggregate)}
        assert rows[get_series_type_id(SeriesType.cadence)].avg == Decimal("82")
        assert rows[get_series_type_id(SeriesType.heart_rate)].max == Decimal("181")

    def test_workout_energy_without_a_known_series_is_not_mirrored(self, db: Session) -> None:
        workout = EventRecordFactory(category="workout")
        detail = EventRecordDetailCreate(record_id=workout.id, energy_burned=Decimal("512"))

        EventRecordDetailRepository(EventRecordDetail).bulk_create(db, [detail])

        assert db.query(EventRecordAggregate).count() == 0
        assert db.query(WorkoutDetails).one().energy_burned == Decimal("512")


class TestRollupQueue:
    def test_a_write_queues_the_local_day_of_each_sample_once_committed(self, db: Session) -> None:
        user = UserFactory()
        late_evening = TimeSeriesSampleCreate(
            id=uuid4(),
            user_id=user.id,
            source="garmin",
            recorded_at=datetime(2099, 1, 1, 23, 30, tzinfo=timezone.utc),
            zone_offset="+02:00",
            value=Decimal("70"),
            series_type=SeriesType.heart_rate,
        )

        DataPointSeriesRepository(SeriesSample).bulk_create(db, [late_evening])
        assert get_redis_client().zcard(DIRTY_DAYS_KEY) == 0
        db.commit()

        source_id = db.query(SeriesSample).one().data_source_id
        assert pop_dirty_days(10) == [(source_id, date(2099, 1, 2))]

    @pytest.mark.parametrize(
        ("hours", "days"),
        [(8, {date(2099, 1, 1), date(2099, 1, 2)}), (28 * 24, {date(2099, 1, 1), date(2099, 1, 29)})],
    )
    def test_an_event_queues_the_local_days_it_starts_and_ends_on(
        self, db: Session, hours: int, days: set[date]
    ) -> None:
        source = DataSourceFactory()
        creator = EventRecordCreate(
            id=uuid4(),
            user_id=source.user_id,
            source=source.source,
            category="sleep",
            type="sleep",
            source_name="Apple Watch",
            duration_seconds=hours * 3600,
            start_datetime=datetime(2099, 1, 1, 22, tzinfo=timezone.utc),
            end_datetime=datetime(2099, 1, 1, 22, tzinfo=timezone.utc) + timedelta(hours=hours),
            zone_offset="+00:00",
            device_model=source.device_model,
        )

        EventRecordRepository(EventRecord).create(db, creator)

        assert {day for _, day in pop_dirty_days(100)} == days


class TestDirtyDaysNewestFirst:
    def test_a_run_takes_the_newest_days_first(self) -> None:
        source = uuid4()
        requeue_dirty_days([(source, DAY + timedelta(days=n)) for n in (3, 0, 9, 5)])

        assert [day for _, day in pop_dirty_days(2)] == [DAY + timedelta(days=9), DAY + timedelta(days=5)]
        assert sorted(day for _, day in pop_dirty_days(10)) == [DAY, DAY + timedelta(days=3)]


class TestDirtyDaysSurviveAKill:
    def test_days_a_dead_run_took_come_back_on_the_next_run(self, db: Session) -> None:
        source_id = uuid4()
        requeue_dirty_days([(source_id, DAY), (source_id, DAY + timedelta(days=1))])
        taken = pop_dirty_days(10)
        # The run dies here: nothing finishes the days, the queue itself is empty.
        assert (len(taken), pop_dirty_days(10)) == (2, [])

        assert recover_dirty_days() == 2
        assert sorted(day for _, day in pop_dirty_days(10)) == [DAY, DAY + timedelta(days=1)]


class TestSeriesRollup:
    def _sample(
        self, source: object, series_type: SeriesTypeDefinition, at: datetime, value: str, **fields: object
    ) -> None:
        DataPointSeriesFactory(mapping=source, series_type=series_type, recorded_at=at, value=Decimal(value), **fields)

    def _day_rows(self, db: Session) -> dict[int, SeriesAggregate]:
        return {
            row.series_type_definition_id: row
            for row in db.query(SeriesAggregate).filter(SeriesAggregate.computed_by == ComputedBy.OPEN_WEARABLES)
        }

    def test_a_day_is_rolled_up_from_its_samples_at_their_local_offset(self, db: Session) -> None:
        source = DataSourceFactory()
        heart_rate = SeriesTypeDefinitionFactory.get_or_create_heart_rate()
        steps = SeriesTypeDefinitionFactory.get_or_create_steps()
        self._sample(
            source, heart_rate, datetime(2098, 12, 31, 23, 30, tzinfo=timezone.utc), "50", zone_offset="+02:00"
        )
        self._sample(source, heart_rate, datetime(2099, 1, 1, 12, tzinfo=timezone.utc), "90", zone_offset="+02:00")
        self._sample(source, heart_rate, datetime(2099, 1, 1, 22, 30, tzinfo=timezone.utc), "60", zone_offset="+02:00")
        self._sample(source, steps, datetime(2099, 1, 1, 10, tzinfo=timezone.utc), "300", zone_offset="+02:00")
        self._sample(source, steps, datetime(2099, 1, 1, 11, tzinfo=timezone.utc), "500", zone_offset="+02:00")
        self._sample(
            source,
            steps,
            datetime(2099, 1, 1, 0, tzinfo=timezone.utc),
            "9000",
            zone_offset="+02:00",
            is_daily_total=True,
        )

        SeriesRollupRepository().roll_up(db, source.id, [DAY])

        rows = self._day_rows(db)
        hr, step = rows[heart_rate.id], rows[steps.id]
        # 23:30 UTC on Dec 31 is 01:30 on Jan 1 at +02:00; 22:30 UTC on Jan 1 is already Jan 2.
        assert (hr.min, hr.max, hr.last, hr.count, hr.sum) == (Decimal("50"), Decimal("90"), Decimal("90"), 2, None)
        assert (hr.period_start, hr.zone_offset) == (CalendarPeriod.of_date(DAY, "+02:00").start, "+02:00")
        # The provider's daily total is not one of the samples.
        assert (step.sum, step.count) == (Decimal("800"), 2)

    def test_a_day_rolled_up_again_recomputes_the_series_with_samples_and_keeps_the_rest(self, db: Session) -> None:
        source = DataSourceFactory()
        steps = SeriesTypeDefinitionFactory.get_or_create_steps()
        heart_rate = SeriesTypeDefinitionFactory.get_or_create_heart_rate()
        self._sample(source, steps, datetime(2099, 1, 1, 10, tzinfo=timezone.utc), "300")
        self._sample(source, heart_rate, datetime(2099, 1, 1, 9, tzinfo=timezone.utc), "60")
        repo = SeriesRollupRepository()
        repo.roll_up(db, source.id, [DAY])
        # Retention deleted the day before its rows were frozen; one heart-rate sample arrives late.
        db.query(SeriesSample).delete()
        self._sample(source, heart_rate, datetime(2099, 1, 1, 9, tzinfo=timezone.utc), "80")

        repo.roll_up(db, source.id, [DAY])

        rows = self._day_rows(db)
        assert (rows[steps.id].sum, rows[heart_rate.id].avg, rows[heart_rate.id].count) == (
            Decimal("300"),
            Decimal("80"),
            1,
        )

    def test_a_session_rolled_up_again_recomputes_only_the_series_with_samples(self, db: Session) -> None:
        source = DataSourceFactory()
        heart_rate = SeriesTypeDefinitionFactory.get_or_create_heart_rate()
        steps = SeriesTypeDefinitionFactory.get_or_create_steps()
        start = datetime(2099, 1, 1, 10, tzinfo=timezone.utc)
        EventRecordFactory(data_source=source, start_datetime=start, duration_seconds=1800)
        self._sample(source, heart_rate, start + timedelta(minutes=5), "120")
        self._sample(source, heart_rate, start + timedelta(minutes=25), "160")
        self._sample(source, steps, start + timedelta(minutes=10), "40")
        repo = SeriesRollupRepository()
        repo.roll_up(db, source.id, [DAY])
        db.query(SeriesSample).filter(SeriesSample.value == Decimal("160")).delete()
        db.query(SeriesSample).filter(SeriesSample.series_type_definition_id == steps.id).delete()

        repo.roll_up(db, source.id, [DAY])

        rows = {row.series_type_definition_id: row for row in db.query(EventRecordAggregate)}
        assert (rows[heart_rate.id].max, rows[heart_rate.id].count, rows[steps.id].sum) == (
            Decimal("120"),
            1,
            Decimal("40"),
        )

    def test_a_workout_gets_its_own_statistics_from_the_samples_inside_it(self, db: Session) -> None:
        source = DataSourceFactory()
        heart_rate = SeriesTypeDefinitionFactory.get_or_create_heart_rate()
        start = datetime(2099, 1, 1, 10, tzinfo=timezone.utc)
        workout = EventRecordFactory(data_source=source, start_datetime=start, duration_seconds=1800)
        self._sample(source, heart_rate, start + timedelta(minutes=5), "120")
        self._sample(source, heart_rate, start + timedelta(minutes=25), "160")
        self._sample(source, heart_rate, start + timedelta(hours=2), "70")

        SeriesRollupRepository().roll_up(db, source.id, [DAY])

        row = db.query(EventRecordAggregate).one()
        assert (row.record_id, row.computed_by) == (workout.id, ComputedBy.OPEN_WEARABLES)
        assert (row.avg, row.min, row.max, row.count) == (Decimal("140"), Decimal("120"), Decimal("160"), 2)

    def test_a_day_whose_samples_are_gone_only_gains_the_rows_it_lacks(self, db: Session) -> None:
        source = DataSourceFactory()
        steps = SeriesTypeDefinitionFactory.get_or_create_steps()
        self._sample(source, steps, datetime(2099, 1, 1, 10, tzinfo=timezone.utc), "300")
        repo = SeriesRollupRepository()
        repo.roll_up(db, source.id, [DAY])
        # Retention deleted the day; one heart-rate sample arrives late.
        db.query(SeriesSample).delete()
        self._sample(
            source,
            SeriesTypeDefinitionFactory.get_or_create_heart_rate(),
            datetime(2099, 1, 1, 9, tzinfo=timezone.utc),
            "60",
        )

        repo.roll_up(db, source.id, [DAY], frozen_before=DAY + timedelta(days=1))

        rows = self._day_rows(db)
        assert (rows[steps.id].sum, rows[get_series_type_id(SeriesType.heart_rate)].avg) == (
            Decimal("300"),
            Decimal("60"),
        )

    def test_a_session_started_on_a_deleted_day_keeps_its_rows(self, db: Session) -> None:
        source = DataSourceFactory()
        heart_rate = SeriesTypeDefinitionFactory.get_or_create_heart_rate()
        start = datetime(2098, 12, 31, 22, tzinfo=timezone.utc)
        EventRecordFactory(data_source=source, start_datetime=start, duration_seconds=4 * 3600)
        self._sample(source, heart_rate, start + timedelta(hours=1), "120")
        repo = SeriesRollupRepository()
        repo.roll_up(db, source.id, [start.date()])
        # Retention deleted Dec 31; the next day's rollup still reaches the workout through its 14-hour window.
        db.query(SeriesSample).delete()
        self._sample(source, heart_rate, datetime(2099, 1, 1, 12, tzinfo=timezone.utc), "70")

        repo.roll_up(db, source.id, [DAY], frozen_before=DAY)

        assert [row.avg for row in db.query(EventRecordAggregate)] == [Decimal("120")]


class TestRollupRuns:
    def test_contiguous_days_are_scanned_a_month_at_a_time(self) -> None:
        days = [date(2099, 1, 1) + timedelta(days=n) for n in range(70)]

        runs = list(_runs(days))

        assert [len(run) for run in runs] == [31, 31, 8]
        assert runs[0][-1] + timedelta(days=1) == runs[1][0]

    def test_a_gap_over_a_week_starts_a_new_scan(self) -> None:
        assert list(_runs([date(2099, 1, 1), date(2099, 1, 5), date(2099, 1, 20)])) == [
            [date(2099, 1, 1), date(2099, 1, 5)],
            [date(2099, 1, 20)],
        ]


class TestDailyLifecycleJob:
    def _settings(self, db: Session, rollup_enabled: bool, delete_after_days: int | None) -> None:
        setting = db.get(ArchivalSetting, 1) or ArchivalSetting(id=1)
        setting.rollup_enabled, setting.delete_after_days = rollup_enabled, delete_after_days
        db.add(setting)
        db.commit()

    def test_the_job_rolls_up_queued_days(self, db: Session) -> None:
        self._settings(db, rollup_enabled=True, delete_after_days=None)
        source = DataSourceFactory()
        DataPointSeriesFactory(mapping=source, recorded_at=datetime(2099, 1, 1, 12, tzinfo=timezone.utc))
        requeue_dirty_days([(source.id, DAY)])

        summary = archival_service.run_daily_archival(db)

        assert summary["rolled_up_days"] == 1
        assert db.query(SeriesAggregate).filter(SeriesAggregate.computed_by == ComputedBy.OPEN_WEARABLES).count() == 1
        assert pop_dirty_days(10) == []

    def test_a_finished_run_leaves_nothing_in_progress(self, db: Session) -> None:
        self._settings(db, rollup_enabled=True, delete_after_days=None)
        source = DataSourceFactory()
        DataPointSeriesFactory(mapping=source, recorded_at=datetime(2099, 1, 1, 12, tzinfo=timezone.utc))
        requeue_dirty_days([(source.id, DAY)])

        archival_service.run_daily_archival(db)

        assert (get_redis_client().scard(IN_PROGRESS_KEY), pop_dirty_days(10)) == (0, [])

    def test_with_rollup_off_the_queue_is_dropped(self, db: Session) -> None:
        self._settings(db, rollup_enabled=False, delete_after_days=None)
        requeue_dirty_days([(uuid4(), DAY)])

        archival_service.run_daily_archival(db)

        assert db.query(SeriesAggregate).count() == 0
        assert pop_dirty_days(10) == []

    def test_retention_rolls_old_days_up_before_deleting_them_whole(self, db: Session) -> None:
        self._settings(db, rollup_enabled=True, delete_after_days=30)
        source = DataSourceFactory()
        cutoff = date.today() - timedelta(days=30)
        old = datetime.combine(cutoff - timedelta(days=2), datetime.min.time(), timezone.utc) + timedelta(hours=12)
        # Local day = the cutoff at +02:00, though its UTC date is the day before: it stays.
        kept = datetime.combine(cutoff, datetime.min.time(), timezone.utc) - timedelta(hours=1)
        DataPointSeriesFactory(mapping=source, recorded_at=old, zone_offset="+02:00")
        DataPointSeriesFactory(mapping=source, recorded_at=kept, zone_offset="+02:00")

        summary = archival_service.run_daily_archival(db)

        assert summary["deleted_live_rows"] == 1
        assert [sample.recorded_at for sample in db.query(SeriesSample)] == [kept]
        day_row = db.query(SeriesAggregate).filter(SeriesAggregate.computed_by == ComputedBy.OPEN_WEARABLES).one()
        assert day_row.period_start == CalendarPeriod.of_date(cutoff - timedelta(days=2), "+02:00").start
        assert db.get(ArchivalSetting, 1).deleted_before == cutoff

    def test_a_late_sample_on_a_deleted_day_does_not_wipe_its_rows(self, db: Session) -> None:
        self._settings(db, rollup_enabled=True, delete_after_days=30)
        cutoff = date.today() - timedelta(days=30)
        source = DataSourceFactory()
        old_day = cutoff - timedelta(days=10)
        steps = SeriesTypeDefinitionFactory.get_or_create_steps()
        DataPointSeriesFactory(
            mapping=source, series_type=steps, recorded_at=datetime.combine(old_day, datetime.min.time(), timezone.utc)
        )
        archival_service.run_daily_archival(db)
        # The day is deleted and frozen; a heart-rate reading for it arrives late.
        DataPointSeriesFactory(
            mapping=source,
            series_type=SeriesTypeDefinitionFactory.get_or_create_heart_rate(),
            recorded_at=datetime.combine(old_day, datetime.min.time(), timezone.utc) + timedelta(hours=9),
        )

        archival_service.run_daily_archival(db)

        ours = db.query(SeriesAggregate).filter(SeriesAggregate.computed_by == ComputedBy.OPEN_WEARABLES)
        assert {row.series_type_definition_id for row in ours} == {steps.id, get_series_type_id(SeriesType.heart_rate)}
        assert db.query(SeriesSample).count() == 0

    def test_one_failing_source_does_not_hold_the_queue(self, db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
        self._settings(db, rollup_enabled=True, delete_after_days=None)
        good, bad = DataSourceFactory(), DataSourceFactory()
        DataPointSeriesFactory(mapping=good, recorded_at=datetime(2099, 1, 1, 12, tzinfo=timezone.utc))
        requeue_dirty_days([(good.id, DAY), (bad.id, DAY)])
        # The failed batch is rolled back; committed first, the fixtures survive it as real data would.
        db.commit()
        roll_up = archival_service.rollup_repo.roll_up

        def failing(db_session: Session, source_id: object, *args: object, **kwargs: object) -> int:
            if source_id == bad.id:
                raise RuntimeError("bad offset")
            return roll_up(db_session, source_id, *args, **kwargs)

        monkeypatch.setattr(archival_service.rollup_repo, "roll_up", failing)

        summary = archival_service.run_daily_archival(db)

        assert summary["rolled_up_days"] == 1
        assert db.query(SeriesAggregate).filter(SeriesAggregate.data_source_id == good.id).count() == 1
        assert pop_dirty_days(10) == []

    def test_retention_deletes_whole_days_a_few_at_a_time(self, db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(_ARCHIVAL_SERVICE, "DELETE_DAYS_PER_BATCH", 1)
        self._settings(db, rollup_enabled=True, delete_after_days=30)
        source = DataSourceFactory()
        cutoff = date.today() - timedelta(days=30)
        for days_ago in (3, 2, 1):
            for hour in (6, 18):
                DataPointSeriesFactory(
                    mapping=source,
                    recorded_at=datetime.combine(cutoff - timedelta(days=days_ago), datetime.min.time(), timezone.utc)
                    + timedelta(hours=hour),
                )

        summary = archival_service.run_daily_archival(db)

        assert summary["deleted_live_rows"] == 6
        assert db.query(SeriesSample).count() == 0
        assert db.query(SeriesAggregate).filter(SeriesAggregate.computed_by == ComputedBy.OPEN_WEARABLES).count() == 3

    def test_a_session_across_two_retention_batches_keeps_all_its_samples(
        self, db: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The second batch rolls up what is left of a sleep that began in the first: it must not overwrite the
        sleep's rows with its second half."""
        monkeypatch.setattr(_ARCHIVAL_SERVICE, "DELETE_DAYS_PER_BATCH", 1)
        self._settings(db, rollup_enabled=True, delete_after_days=30)
        source = DataSourceFactory()
        night = date.today() - timedelta(days=40)
        start = datetime.combine(night, datetime.min.time(), timezone.utc) + timedelta(hours=22)
        sleep = EventRecordFactory(data_source=source, start_datetime=start, duration_seconds=8 * 3600)
        for hours, value in ((1, "50"), (5, "70")):
            DataPointSeriesFactory(mapping=source, recorded_at=start + timedelta(hours=hours), value=Decimal(value))

        archival_service.run_daily_archival(db)

        row = db.query(EventRecordAggregate).filter(EventRecordAggregate.record_id == sleep.id).one()
        assert (row.avg, row.count, db.query(SeriesSample).count()) == (Decimal("60"), 2, 0)

    def test_one_failing_source_does_not_hold_retention(self, db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
        self._settings(db, rollup_enabled=True, delete_after_days=30)
        good, bad = DataSourceFactory(), DataSourceFactory()
        old = datetime.now(timezone.utc) - timedelta(days=60)
        for source in (good, bad):
            DataPointSeriesFactory(mapping=source, recorded_at=old)
        db.commit()
        roll_up = archival_service.rollup_repo.roll_up

        def failing(db_session: Session, source_id: object, *args: object, **kwargs: object) -> int:
            if source_id == bad.id:
                raise RuntimeError("bad offset")
            return roll_up(db_session, source_id, *args, **kwargs)

        monkeypatch.setattr(archival_service.rollup_repo, "roll_up", failing)

        archival_service.run_daily_archival(db)

        assert [sample.data_source_id for sample in db.query(SeriesSample)] == [bad.id]
        # Not every old day is gone, so none is frozen yet.
        assert db.get(ArchivalSetting, 1).deleted_before is None

    def test_retention_goes_through_every_source_page(self, db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(_ARCHIVAL_SERVICE, "RETENTION_SOURCES_PER_QUERY", 1)
        self._settings(db, rollup_enabled=False, delete_after_days=30)
        for _ in range(3):
            DataPointSeriesFactory(
                mapping=DataSourceFactory(), recorded_at=datetime.now(timezone.utc) - timedelta(days=60)
            )

        summary = archival_service.run_daily_archival(db)

        assert (summary["deleted_live_rows"], db.query(SeriesSample).count()) == (3, 0)
        assert db.get(ArchivalSetting, 1).deleted_before == date.today() - timedelta(days=30)

    def test_a_run_past_its_soft_time_limit_puts_its_batch_back(
        self, db: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._settings(db, rollup_enabled=True, delete_after_days=None)
        source = DataSourceFactory()
        requeue_dirty_days([(source.id, DAY)])

        def killed(*args: object, **kwargs: object) -> int:
            raise SoftTimeLimitExceeded()

        monkeypatch.setattr(archival_service.rollup_repo, "roll_up", killed)

        with pytest.raises(SoftTimeLimitExceeded):
            archival_service.run_daily_archival(db)

        assert (get_redis_client().scard(IN_PROGRESS_KEY), pop_dirty_days(10)) == (0, [(source.id, DAY)])

    def test_a_run_out_of_time_puts_back_the_days_it_did_not_reach(
        self, db: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(_ARCHIVAL_SERVICE, "ROLLUP_DAYS_PER_COMMIT", 1)
        self._settings(db, rollup_enabled=True, delete_after_days=None)
        source = DataSourceFactory()
        days = [DAY, DAY + timedelta(days=1), DAY + timedelta(days=2)]
        requeue_dirty_days([(source.id, day) for day in days])
        roll_up = archival_service.rollup_repo.roll_up
        later = _ARCHIVAL_SERVICE.time.monotonic() + 10_000

        def one_day_then_out_of_time(*args: object, **kwargs: object) -> int:
            monkeypatch.setattr(_ARCHIVAL_SERVICE.time, "monotonic", lambda: later)
            return roll_up(*args, **kwargs)

        monkeypatch.setattr(archival_service.rollup_repo, "roll_up", one_day_then_out_of_time)

        summary = archival_service.run_daily_archival(db)

        assert (summary["rolled_up_days"], get_redis_client().scard(IN_PROGRESS_KEY)) == (1, 0)
        assert sorted(day for _, day in pop_dirty_days(10)) == days[1:]

    def test_a_late_sample_on_a_day_an_unfinished_run_deleted_keeps_its_rows(
        self, db: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The run stops after deleting day X, before deleted_before moves; a heart-rate sample for X arrives
        late. The next run must not recompute X's heart-rate row from that one sample."""
        monkeypatch.setattr(_ARCHIVAL_SERVICE, "DELETE_DAYS_PER_BATCH", 1)
        self._settings(db, rollup_enabled=True, delete_after_days=30)
        source = DataSourceFactory()
        heart_rate = SeriesTypeDefinitionFactory.get_or_create_heart_rate()
        day = date.today() - timedelta(days=40)
        noon = datetime.combine(day, datetime.min.time(), timezone.utc) + timedelta(hours=12)
        DataPointSeriesFactory(mapping=source, series_type=heart_rate, recorded_at=noon, value=Decimal("60"))
        DataPointSeriesFactory(mapping=source, series_type=heart_rate, recorded_at=noon + timedelta(days=5))
        db.commit()
        monkeypatch.setattr(_ARCHIVAL_SERVICE, "MAX_ROWS_PER_RUN", 1)
        archival_service.run_daily_archival(db)
        assert db.get(ArchivalSetting, 1).deleted_before is None
        DataPointSeriesFactory(
            mapping=source, series_type=heart_rate, recorded_at=noon + timedelta(hours=1), value=Decimal("90")
        )
        db.commit()
        monkeypatch.setattr(_ARCHIVAL_SERVICE, "MAX_ROWS_PER_RUN", 500_000)

        archival_service.run_daily_archival(db)

        row = db.query(SeriesAggregate).filter(SeriesAggregate.period_start == CalendarPeriod.of_date(day).start).one()
        assert (row.avg, db.get(ArchivalSetting, 1).deleted_before) == (
            Decimal("60"),
            date.today() - timedelta(days=30),
        )
        assert get_redis_client().exists(DELETED_BEFORE_KEY) == 0

    def test_a_failing_queue_does_not_hold_retention_back(self, db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
        self._settings(db, rollup_enabled=True, delete_after_days=30)
        DataPointSeriesFactory(recorded_at=datetime.now(timezone.utc) - timedelta(days=60))
        db.commit()

        def broken(*args: object, **kwargs: object) -> int:
            raise RuntimeError("redis down")

        monkeypatch.setattr(archival_service, "_roll_up_queued_days", broken)

        summary = archival_service.run_daily_archival(db)

        assert (summary["deleted_live_rows"], db.query(SeriesSample).count()) == (1, 0)

    def test_retention_without_rollup_only_deletes(self, db: Session) -> None:
        self._settings(db, rollup_enabled=False, delete_after_days=30)
        DataPointSeriesFactory(recorded_at=datetime.now(timezone.utc) - timedelta(days=60))

        archival_service.run_daily_archival(db)

        assert db.query(SeriesSample).count() == 0
        assert db.query(SeriesAggregate).count() == 0
