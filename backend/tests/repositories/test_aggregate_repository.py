from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models import EventRecordAggregate, EventRecordDetail, SeriesAggregate, SeriesSample, WorkoutDetails
from app.repositories import AggregateRepository, DataPointSeriesRepository, EventRecordDetailRepository
from app.schemas.enums import ComputedBy, PeriodKind, SeriesType, get_series_type_id
from app.schemas.model_crud.activities import (
    CalendarPeriod,
    EventRecordDetailCreate,
    SessionValue,
    TimeSeriesSampleCreate,
)
from tests.factories import DataSourceFactory, EventRecordFactory, UserFactory

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
    def _row(self, source_id: object, computed_by: ComputedBy, **stats: Decimal) -> dict:
        period = CalendarPeriod.of_date(DAY)
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

    def test_workout_energy_without_a_known_series_is_not_mirrored(self, db: Session) -> None:
        workout = EventRecordFactory(category="workout")
        detail = EventRecordDetailCreate(record_id=workout.id, energy_burned=Decimal("512"))

        EventRecordDetailRepository(EventRecordDetail).bulk_create(db, [detail])

        assert db.query(EventRecordAggregate).count() == 0
        assert db.query(WorkoutDetails).one().energy_burned == Decimal("512")
