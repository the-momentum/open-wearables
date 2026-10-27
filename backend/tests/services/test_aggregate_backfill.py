from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.integrations import redis_lock
from app.integrations.celery.tasks.aggregate_backfill_task import bound_statements, run_aggregate_backfill
from app.integrations.redis_client import get_redis_client
from app.models import (
    DataPointSeriesArchive,
    DataSource,
    EventRecord,
    EventRecordAggregate,
    SeriesAggregate,
    SeriesSample,
    SeriesTypeDefinition,
    WorkoutDetails,
)
from app.repositories import AggregateRepository
from app.repositories.aggregate_backfill_repository import AggregateBackfillRepository
from app.repositories.archival_repository import DataPointSeriesArchiveRepository
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

    def test_big_sources_go_a_batch_at_a_time(self, db: Session) -> None:
        """No statement covers a whole source: Suunto speeds and Garmin epochs go a batch at a time."""
        suunto = DataSourceFactory(provider=ProviderName.SUUNTO)
        workouts = [
            EventRecordFactory(category="workout", data_source=suunto, start_datetime=AT + timedelta(days=n))
            for n in range(3)
        ]
        db.add_all([WorkoutDetails(record_id=w.id, average_speed=Decimal("36")) for w in workouts])
        garmin = DataSourceFactory(provider=ProviderName.GARMIN)
        steps = SeriesTypeDefinitionFactory.get_or_create_steps()
        instants = [AT + timedelta(minutes=15 * n) for n in range(3)]
        for at in instants:
            DataPointSeriesFactory(
                mapping=garmin, series_type=steps, recorded_at=at, external_id=f"3952-{int(at.timestamp()):x}"
            )
        db.flush()

        with patch("app.repositories.aggregate_backfill_repository.UPDATE_BATCH_SIZE", 1):
            assert aggregate_backfill_service.run(db, budget_seconds=60)
            aggregate_backfill_service.run(db, budget_seconds=60)

        assert {db.get(WorkoutDetails, w.id).average_speed for w in workouts} == {Decimal("10")}
        assert {s.window_seconds for s in db.query(SeriesSample)} == {900}

    def test_a_source_left_halfway_goes_on_from_its_last_window(self, db: Session) -> None:
        source = DataSourceFactory(provider=ProviderName.GARMIN)
        now = datetime.now(timezone.utc)
        workouts = [
            EventRecordFactory(category="workout", data_source=source, start_datetime=now - timedelta(days=days))
            for days in (10, 2 * 365 + 10, 4 * 365 + 10)
        ]
        db.add_all([WorkoutDetails(record_id=w.id, heart_rate_avg=Decimal("140")) for w in workouts])
        db.flush()
        # A previous run mirrored this source's workouts from a year ago on, then ran out of time.
        cutoff = (now - timedelta(days=365)).date()
        get_redis_client().set("aggregate_backfill:cursor:workout_details:window", f"{source.id}|{cutoff}")
        DataMigrationRepository().mark_completed(db, "aggregate_backfill:suunto_speed")

        aggregate_backfill_service.run(db, budget_seconds=60)

        mirrored = {r.record_id for r in db.query(EventRecordAggregate)}
        assert mirrored == {workouts[1].id, workouts[2].id}

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

    def test_a_run_that_lost_its_lock_stops(self, db: Session) -> None:
        _legacy_workout(db, ProviderName.GARMIN, heart_rate_avg=Decimal("140"))

        assert not aggregate_backfill_service.run(db, budget_seconds=60, keep_alive=lambda: False)
        assert not aggregate_backfill_service.is_done(db)

    def test_a_source_that_keeps_failing_is_skipped_and_kept_from_retention(self, db: Session) -> None:
        broken = _legacy_workout(db, ProviderName.GARMIN, heart_rate_avg=Decimal("140"))
        fine = _legacy_workout(db, ProviderName.GARMIN, heart_rate_avg=Decimal("150"))
        broken_source = db.get(DataSource, db.get(EventRecord, broken.record_id).data_source_id)
        DataPointSeriesFactory(data_source=broken_source, recorded_at=AT)
        db.add(
            DataPointSeriesArchive(
                id=uuid4(),
                data_source_id=broken_source.id,
                series_type_definition_id=get_series_type_id(SeriesType.heart_rate),
                bucket_start_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
                aggregation_type=AggregationMethod.AVG,
                value=Decimal("62"),
                sample_count=1440,
            )
        )
        db.flush()
        mirror = AggregateBackfillRepository.mirror_workout_details

        def fail_on_broken(self: AggregateBackfillRepository, db: Session, source_id: UUID, *args: object) -> None:
            if source_id == broken_source.id:
                raise OperationalError("statement", {}, Exception("canceling statement due to statement timeout"))
            mirror(self, db, source_id, *args)

        with patch.object(AggregateBackfillRepository, "mirror_workout_details", fail_on_broken):
            assert aggregate_backfill_service.run(db, budget_seconds=60)

        assert _session_rows(db, fine)
        assert not _session_rows(db, broken)
        later = datetime(2030, 1, 1, tzinfo=timezone.utc)
        retention = DataPointSeriesArchiveRepository()
        assert retention.sources_with_samples_before(db, later, UUID(int=0), 50) == []
        assert retention.delete_archive_before(db, later.date(), 50) == 0


class TestBackfillTask:
    def test_a_run_waits_out_one_already_in_progress(self, db: Session) -> None:
        get_redis_client().set("aggregate_backfill:lock", "1")

        assert run_aggregate_backfill() == {"skipped": "previous_run_in_progress"}

    def test_a_run_waits_for_the_data_source_merge(self, db: Session) -> None:
        """The merge moves samples between sources, behind a cursor that may have passed them."""
        _legacy_workout(db, ProviderName.GARMIN, heart_rate_avg=Decimal("140"))
        session = MagicMock()
        session.__enter__.return_value = db

        with patch("app.integrations.celery.tasks.aggregate_backfill_task.SessionLocal", return_value=session):
            assert run_aggregate_backfill() == {"skipped": "waiting_for_data_source_merge"}

            DataMigrationRepository().mark_completed(db, "merge_duplicate_data_sources")
            assert run_aggregate_backfill() == {"done": True}

    def test_a_lock_is_released_and_extended_only_by_its_holder(self, db: Session) -> None:
        token = redis_lock.acquire("aggregate_backfill:lock", 60)
        assert token
        assert redis_lock.acquire("aggregate_backfill:lock", 60) is None

        redis_lock.release("aggregate_backfill:lock", "someone-else")
        assert not redis_lock.extend("aggregate_backfill:lock", "someone-else", 600)
        assert get_redis_client().get("aggregate_backfill:lock") == token

        redis_lock.release("aggregate_backfill:lock", token)
        assert get_redis_client().get("aggregate_backfill:lock") is None

    def test_its_statements_are_cut_off_before_the_lock_runs_out(self, db: Session) -> None:
        bound_statements(db)
        db.commit()

        assert db.execute(text("SHOW statement_timeout")).scalar() == "5min"


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

    def test_a_source_left_halfway_goes_on_from_its_last_window(self, db: Session) -> None:
        source = DataSourceFactory(provider=ProviderName.GARMIN)
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        for days_ago in (100, 3 * 365):
            _sample(db, source, SeriesType.resting_heart_rate, today - timedelta(days=days_ago), "50")
        # A previous run copied this source's history from a year ago on, then ran out of time.
        cutoff = (today - timedelta(days=365)).date()
        get_redis_client().set("aggregate_backfill:cursor:history_all:window", f"{source.id}|{cutoff}")

        aggregate_backfill_service.run(db, budget_seconds=60)

        assert [day for _, day, *_ in _days(db)] == [(today - timedelta(days=3 * 365)).date()]

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

    def test_an_xml_import_at_a_workouts_end_is_a_genuine_record(self, db: Session) -> None:
        source = DataSourceFactory(provider=ProviderName.APPLE, source="apple_health_xml")
        workout = EventRecordFactory(data_source=source, start_datetime=AT, duration_seconds=1800)
        _sample(db, source, SeriesType.vo2_max, workout.end_datetime, "41")

        aggregate_backfill_service.run(db, budget_seconds=60)

        assert not db.query(EventRecordAggregate).filter(EventRecordAggregate.computed_by == ComputedBy.PROVIDER).all()

    def test_sdk_workout_statistics_land_on_the_workout_they_closed(self, db: Session) -> None:
        source = DataSourceFactory(provider=ProviderName.APPLE)
        workout = EventRecordFactory(data_source=source, start_datetime=AT, duration_seconds=1800)
        _sample(db, source, SeriesType.cadence, workout.end_datetime, "82")
        _sample(db, source, SeriesType.cadence, AT + timedelta(minutes=10), "90")
        # A genuine record that happens to end with the workout carries its own id: not a statistic.
        _sample(db, source, SeriesType.vo2_max, workout.end_datetime, "41", external_id="hk-uuid")

        aggregate_backfill_service.run(db, budget_seconds=60)

        (row,) = db.query(EventRecordAggregate).filter(EventRecordAggregate.record_id == workout.id)
        assert (row.avg, row.computed_by) == (Decimal("82"), ComputedBy.PROVIDER)
