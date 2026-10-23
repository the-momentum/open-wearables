from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.orm import Session

from app.integrations.celery.tasks.aggregate_backfill_task import run_aggregate_backfill
from app.integrations.redis_client import get_redis_client
from app.models import (
    DataPointSeriesArchive,
    EventRecordAggregate,
    SeriesAggregate,
    SeriesSample,
    SeriesTypeDefinition,
    WorkoutDetails,
)
from app.repositories import AggregateRepository
from app.repositories.data_migration_repository import DataMigrationRepository
from app.repositories.series_aggregate_repository import LOCAL_DAY
from app.schemas.enums import (
    AggregationMethod,
    ComputedBy,
    ProviderName,
    SeriesType,
    get_series_type_from_id,
    get_series_type_id,
)
from app.services.aggregate_backfill_service import aggregate_backfill_service
from tests.factories import (
    DataPointSeriesFactory,
    DataSourceFactory,
    EventRecordFactory,
    SeriesTypeDefinitionFactory,
    provider_day,
)

AT = datetime(2025, 6, 1, 8, tzinfo=timezone.utc)


def _legacy_workout(db: Session, provider: ProviderName, **columns: object) -> WorkoutDetails:
    """A workout saved before the stack: its details have no aggregate rows."""
    workout = EventRecordFactory(category="workout", data_source=DataSourceFactory(provider=provider))
    detail = WorkoutDetails(record_id=workout.id, **columns)
    db.add(detail)
    db.flush()
    return detail


def _session_rows(db: Session, detail: WorkoutDetails) -> dict[int, EventRecordAggregate]:
    return {
        row.series_type_definition_id: row
        for row in db.query(EventRecordAggregate).filter(EventRecordAggregate.record_id == detail.record_id)
    }


class TestBackfillSteps:
    def test_legacy_suunto_speed_turns_into_metres_per_second_once(self, db: Session) -> None:
        legacy = _legacy_workout(db, ProviderName.SUUNTO, average_speed=Decimal("36"), max_speed=Decimal("72"))

        assert aggregate_backfill_service.run(db, budget_seconds=60)
        aggregate_backfill_service.run(db, budget_seconds=60)

        db.refresh(legacy)
        assert (legacy.average_speed, legacy.max_speed) == (Decimal("10"), Decimal("20"))
        assert _session_rows(db, legacy)[get_series_type_id(SeriesType.speed)].avg == Decimal("10")

    def test_workout_details_become_provider_rows_and_keep_what_is_already_there(self, db: Session) -> None:
        garmin = _legacy_workout(
            db,
            ProviderName.GARMIN,
            heart_rate_min=95,
            heart_rate_avg=Decimal("148"),
            heart_rate_max=181,
            energy_burned=Decimal("512"),
        )
        oura = _legacy_workout(db, ProviderName.OURA, energy_burned=Decimal("300"))
        heart_rate = get_series_type_id(SeriesType.heart_rate)
        AggregateRepository(EventRecordAggregate).upsert(
            db,
            [
                {
                    "record_id": garmin.record_id,
                    "series_type_definition_id": heart_rate,
                    "computed_by": ComputedBy.PROVIDER,
                    "avg": Decimal("150"),
                    "count": 1,
                }
            ],
        )

        aggregate_backfill_service.run(db, budget_seconds=60)

        rows = _session_rows(db, garmin)
        assert (rows[heart_rate].min, rows[heart_rate].avg, rows[heart_rate].max) == (
            Decimal("95"),
            Decimal("150"),
            Decimal("181"),
        )
        assert rows[get_series_type_id(SeriesType.total_energy)].sum == Decimal("512")
        # Oura's workout energy has no established series yet: it stays in the column only.
        assert _session_rows(db, oura) == {}

    def test_only_legacy_garmin_epochs_get_their_width(self, db: Session) -> None:
        source = DataSourceFactory(provider=ProviderName.GARMIN)
        steps = SeriesTypeDefinitionFactory.get_or_create_steps()
        epoch = DataPointSeriesFactory(
            mapping=source, series_type=steps, recorded_at=AT, external_id=f"3952-{int(AT.timestamp()):x}"
        )
        other = DataPointSeriesFactory(
            mapping=source, series_type=steps, recorded_at=AT.replace(hour=9), external_id="x"
        )

        aggregate_backfill_service.run(db, budget_seconds=60)

        assert {s.id: s.window_seconds for s in db.query(SeriesSample)} == {epoch.id: 900, other.id: None}

    def test_archived_days_become_our_day_rows(self, db: Session) -> None:
        source = DataSourceFactory()
        heart_rate = get_series_type_id(SeriesType.heart_rate)
        day = datetime(2024, 1, 1, tzinfo=timezone.utc)
        for method, value in ((AggregationMethod.AVG, "62"), (AggregationMethod.MAX, "140")):
            db.add(
                DataPointSeriesArchive(
                    id=uuid4(),
                    data_source_id=source.id,
                    series_type_definition_id=heart_rate,
                    bucket_start_at=day,
                    aggregation_type=method,
                    value=Decimal(value),
                    sample_count=1440,
                )
            )
        db.flush()

        aggregate_backfill_service.run(db, budget_seconds=60)

        row = db.query(SeriesAggregate).one()
        assert (row.period_start, row.computed_by, row.avg, row.max, row.count) == (
            day,
            ComputedBy.OPEN_WEARABLES,
            Decimal("62"),
            Decimal("140"),
            1440,
        )

    def test_a_run_out_of_time_goes_on_where_it_stopped(self, db: Session) -> None:
        _legacy_workout(db, ProviderName.GARMIN, heart_rate_avg=Decimal("140"))

        assert not aggregate_backfill_service.run(db, budget_seconds=0)
        assert aggregate_backfill_service.run(db, budget_seconds=60)
        assert aggregate_backfill_service.is_done(db)


class TestBackfillTask:
    def test_a_run_waits_out_one_already_in_progress(self, db: Session) -> None:
        get_redis_client().set("aggregate_backfill:lock", "1")

        assert run_aggregate_backfill() == {"skipped": "previous_run_in_progress"}


def _series(db: Session, series_type: SeriesType) -> SeriesTypeDefinition:
    definition = db.get(SeriesTypeDefinition, get_series_type_id(series_type))
    assert definition is not None
    return definition


def _sample(db: Session, source: object, series_type: SeriesType, at: datetime, value: str, **fields: object) -> None:
    DataPointSeriesFactory(
        mapping=source, series_type=_series(db, series_type), recorded_at=at, value=Decimal(value), **fields
    )


def _days(db: Session) -> list[tuple[str, date, str, Decimal | None, Decimal | None]]:
    rows = db.query(SeriesAggregate, LOCAL_DAY).filter(SeriesAggregate.computed_by == ComputedBy.PROVIDER)
    return sorted(
        (get_series_type_from_id(row.series_type_definition_id).value, day, row.zone_offset, row.sum, row.avg)
        for row, day in rows
    )


class TestHistoryValues:
    def test_garmin_daily_totals_and_nightly_hrv_but_not_their_samples(self, db: Session) -> None:
        source = DataSourceFactory(provider=ProviderName.GARMIN)
        midnight = datetime(2025, 6, 1, 22, tzinfo=timezone.utc)  # 2025-06-02 00:00 at +02:00
        _sample(db, source, SeriesType.steps, midnight, "8432", zone_offset="+02:00", is_daily_total=True)
        _sample(
            db,
            source,
            SeriesType.steps,
            midnight + timedelta(minutes=15),
            "120",
            zone_offset="+02:00",
            is_daily_total=False,
        )
        _sample(db, source, SeriesType.resting_heart_rate, midnight, "52", zone_offset="+02:00")
        _sample(
            db,
            source,
            SeriesType.heart_rate_variability_rmssd,
            midnight,
            "84",
            zone_offset="+02:00",
            external_id="hrv-1",
        )
        _sample(
            db,
            source,
            SeriesType.heart_rate_variability_rmssd,
            midnight + timedelta(minutes=5),
            "70",
            zone_offset="+02:00",
            external_id="hrv-1:300",
        )

        aggregate_backfill_service.run(db, budget_seconds=60)

        assert _days(db) == [
            ("heart_rate_variability_rmssd", date(2025, 6, 2), "+02:00", None, Decimal("84")),
            ("resting_heart_rate", date(2025, 6, 2), "+02:00", None, Decimal("52")),
            ("steps", date(2025, 6, 2), "+02:00", Decimal("8432"), None),
        ]

    def test_garmin_nightly_hrv_lands_on_the_morning_it_was_woken_up_to(self, db: Session) -> None:
        """Garmin stored lastNightAvg at the sleep's start; the night belongs to its calendar date, the next day."""
        source = DataSourceFactory(provider=ProviderName.GARMIN)
        bedtime = datetime(2025, 6, 1, 21, tzinfo=timezone.utc)  # 23:00 on 2025-06-01 at +02:00
        _sample(
            db,
            source,
            SeriesType.heart_rate_variability_rmssd,
            bedtime,
            "84",
            zone_offset="+02:00",
            external_id="hrv-1",
        )

        aggregate_backfill_service.run(db, budget_seconds=60)

        assert _days(db) == [("heart_rate_variability_rmssd", date(2025, 6, 2), "+02:00", None, Decimal("84"))]

    def test_suunto_days_recover_the_offset_they_lost(self, db: Session) -> None:
        source = DataSourceFactory(provider=ProviderName.SUUNTO)
        _sample(
            db, source, SeriesType.steps, datetime(2025, 6, 1, 22, tzinfo=timezone.utc), "9000", is_daily_total=True
        )

        aggregate_backfill_service.run(db, budget_seconds=60)

        assert _days(db) == [("steps", date(2025, 6, 2), "+02:00", Decimal("9000"), None)]

    def test_suunto_days_at_plus_thirteen_recover_their_offset_too(self, db: Session) -> None:
        source = DataSourceFactory(provider=ProviderName.SUUNTO)
        # 2025-01-02 00:00 in New Zealand's summer (+13:00)
        _sample(
            db, source, SeriesType.steps, datetime(2025, 1, 1, 11, tzinfo=timezone.utc), "9000", is_daily_total=True
        )

        aggregate_backfill_service.run(db, budget_seconds=60)

        assert _days(db) == [("steps", date(2025, 1, 2), "+13:00", Decimal("9000"), None)]

    def test_a_day_sent_more_than_once_is_its_latest_value(self, db: Session) -> None:
        source = DataSourceFactory(provider=ProviderName.GARMIN)
        midnight = datetime(2025, 6, 1, 22, tzinfo=timezone.utc)  # 2025-06-02 00:00 at +02:00
        _sample(
            db,
            source,
            SeriesType.steps,
            midnight + timedelta(hours=12),
            "9500",
            zone_offset="+02:00",
            is_daily_total=True,
        )
        _sample(db, source, SeriesType.steps, midnight, "8432", zone_offset="+02:00", is_daily_total=True)

        aggregate_backfill_service.run(db, budget_seconds=60)

        assert _days(db) == [("steps", date(2025, 6, 2), "+02:00", Decimal("9500"), None)]

    def test_polar_nightly_values_are_the_ones_at_utc_midnight(self, db: Session) -> None:
        source = DataSourceFactory(provider=ProviderName.POLAR)
        _sample(db, source, SeriesType.heart_rate_variability_rmssd, datetime(2025, 6, 2, tzinfo=timezone.utc), "61")
        _sample(db, source, SeriesType.heart_rate_variability_rmssd, datetime(2025, 6, 2, 3, tzinfo=timezone.utc), "55")

        aggregate_backfill_service.run(db, budget_seconds=60)

        assert _days(db) == [("heart_rate_variability_rmssd", date(2025, 6, 2), "+00:00", None, Decimal("61"))]

    def test_a_day_the_provider_already_holds_at_another_offset_is_kept(self, db: Session) -> None:
        source = DataSourceFactory(provider=ProviderName.GARMIN)
        provider_day(db, source, SeriesType.vo2_max, date(2025, 6, 2), avg=Decimal("48"))
        _sample(db, source, SeriesType.vo2_max, datetime(2025, 6, 2, tzinfo=timezone.utc), "47")

        aggregate_backfill_service.run(db, budget_seconds=60)

        assert [row[4] for row in _days(db)] == [Decimal("48")]

    def test_nightly_values_land_on_their_sleep(self, db: Session) -> None:
        oura = DataSourceFactory(provider=ProviderName.OURA)
        suunto = DataSourceFactory(provider=ProviderName.SUUNTO)
        whoop = DataSourceFactory(provider=ProviderName.WHOOP)
        start, end = datetime(2025, 6, 1, 22, tzinfo=timezone.utc), datetime(2025, 6, 2, 6, tzinfo=timezone.utc)
        sleeps = {
            source.provider: EventRecordFactory(
                data_source=source,
                category="sleep",
                type="sleep",
                start_datetime=start,
                end_datetime=end,
                duration_seconds=8 * 3600,
            )
            for source in (oura, suunto, whoop)
        }
        _sample(db, oura, SeriesType.resting_heart_rate, start, "48")
        _sample(db, suunto, SeriesType.oxygen_saturation, end, "98", is_daily_total=True)
        _sample(db, whoop, SeriesType.heart_rate_variability_rmssd, end + timedelta(hours=1), "61")

        aggregate_backfill_service.run(db, budget_seconds=60)

        rows = {row.record_id: row for row in db.query(EventRecordAggregate)}
        assert rows[sleeps[ProviderName.OURA].id].avg == Decimal("48")
        assert (rows[sleeps[ProviderName.SUUNTO].id].max, rows[sleeps[ProviderName.SUUNTO].id].avg) == (
            Decimal("98"),
            None,
        )
        assert rows[sleeps[ProviderName.WHOOP].id].avg == Decimal("61")

    def test_sdk_workout_statistics_land_on_the_workout_they_closed(self, db: Session) -> None:
        source = DataSourceFactory(provider=ProviderName.APPLE)
        workout = EventRecordFactory(data_source=source, start_datetime=AT, duration_seconds=1800)
        _sample(db, source, SeriesType.cadence, workout.end_datetime, "82")
        _sample(db, source, SeriesType.cadence, AT + timedelta(minutes=10), "90")
        # A genuine record that happens to end with the workout carries its own id: not a statistic.
        _sample(db, source, SeriesType.vo2_max, workout.end_datetime, "41", external_id="hk-uuid")

        aggregate_backfill_service.run(db, budget_seconds=60)

        rows = {
            r.computed_by: r
            for r in db.query(EventRecordAggregate).filter(
                EventRecordAggregate.record_id == workout.id,
                EventRecordAggregate.series_type_definition_id == get_series_type_id(SeriesType.cadence),
            )
        }
        assert rows[ComputedBy.PROVIDER].avg == Decimal("82")
        # Ours, rolled up from the workout's samples, sits beside it: 82 at the end and 90 inside.
        assert rows[ComputedBy.OPEN_WEARABLES].avg == Decimal("86")


class TestHistoryRollup:
    def _ours(self, db: Session) -> list[date]:
        rows = db.query(LOCAL_DAY).filter(SeriesAggregate.computed_by == ComputedBy.OPEN_WEARABLES)
        return sorted(day for (day,) in rows)

    def test_every_day_with_samples_gets_our_row_newest_first(self, db: Session) -> None:
        source = DataSourceFactory()
        today = datetime.now(timezone.utc).replace(hour=12, minute=0, second=0, microsecond=0)
        for days_ago in (1, 45, 400):
            DataPointSeriesFactory(mapping=source, recorded_at=today - timedelta(days=days_ago), value=Decimal("60"))

        aggregate_backfill_service.run(db, budget_seconds=60)

        assert self._ours(db) == sorted((today - timedelta(days=n)).date() for n in (1, 45, 400))

    def test_a_source_left_halfway_goes_on_from_its_last_chunk(self, db: Session) -> None:
        source = DataSourceFactory()
        for day in (date(2025, 1, 10), date(2025, 3, 10)):
            DataPointSeriesFactory(
                mapping=source, recorded_at=datetime.combine(day, datetime.min.time(), timezone.utc).replace(hour=12)
            )
        # A previous run rolled up this source from 2025-03-01 on, then ran out of time.
        get_redis_client().set("aggregate_backfill:cursor:rollup_all:day", f"{source.id}|2025-03-01")
        DataMigrationRepository().mark_completed(db, "aggregate_backfill:rollup_recent")

        aggregate_backfill_service.run(db, budget_seconds=60)

        assert self._ours(db) == [date(2025, 1, 10)]
