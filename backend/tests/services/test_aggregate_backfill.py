from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.integrations import redis_lock
from app.integrations.celery.tasks.aggregate_backfill_task import bound_statements, run_aggregate_backfill
from app.integrations.redis_client import get_redis_client
from app.integrations.rollup_queue import pop_dirty_days, requeue_dirty_days
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
from app.models.archival_setting import ArchivalSetting
from app.repositories import AggregateRepository
from app.repositories.aggregate_backfill_repository import AggregateBackfillRepository
from app.repositories.archival_repository import DataPointSeriesArchiveRepository
from app.repositories.data_migration_repository import DataMigrationRepository
from app.repositories.series_aggregate_repository import LOCAL_DAY
from app.repositories.series_rollup_repository import SeriesRollupRepository
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


@pytest.fixture(autouse=True)
def _archival_settings(db: Session) -> None:
    """The row the startup seeds; the rollup steps read where retention stopped from it."""
    db.merge(ArchivalSetting(id=1, rollup_enabled=True, delete_after_days=None))
    db.flush()


@pytest.fixture
def roll_up_history(monkeypatch: pytest.MonkeyPatch) -> None:
    """The history's rollup, off until a release turns it on."""
    monkeypatch.setattr("app.services.aggregate_backfill_service.ROLL_UP_HISTORY", True)


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
    def test_the_history_is_rolled_up_only_once_a_release_turns_it_on(
        self, db: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        DataPointSeriesFactory(mapping=DataSourceFactory(), recorded_at=AT)
        ours = db.query(SeriesAggregate).filter(SeriesAggregate.computed_by == ComputedBy.OPEN_WEARABLES)

        assert aggregate_backfill_service.run(db, budget_seconds=60)
        assert ours.count() == 0

        monkeypatch.setattr("app.services.aggregate_backfill_service.ROLL_UP_HISTORY", True)
        assert not aggregate_backfill_service.is_done(db)
        assert aggregate_backfill_service.run(db, budget_seconds=60)
        assert ours.count() == 1

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

    @pytest.mark.usefixtures("roll_up_history")
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


@pytest.mark.usefixtures("roll_up_history")
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

    def test_a_chunk_waits_for_a_scheduled_rollup_in_progress(self, db: Session) -> None:
        """Both write our day rows, so whichever read its samples first must not land last."""
        DataPointSeriesFactory(mapping=DataSourceFactory(), recorded_at=datetime(2025, 1, 10, 12, tzinfo=timezone.utc))
        get_redis_client().set("series_rollup:lock", "1")

        assert not aggregate_backfill_service.run(db, budget_seconds=60)
        assert self._ours(db) == []

        get_redis_client().delete("series_rollup:lock")
        assert aggregate_backfill_service.run(db, budget_seconds=60)
        assert self._ours(db) == [date(2025, 1, 10)]

    def test_a_run_rolls_up_the_days_live_writes_queued(self, db: Session) -> None:
        """Between two chunks the scheduled rollup, trying once every 15 minutes, hardly ever gets the lock."""
        source = DataSourceFactory()
        DataPointSeriesFactory(mapping=source, recorded_at=datetime(2025, 1, 10, 12, tzinfo=timezone.utc))
        requeue_dirty_days([(source.id, date(2025, 1, 10))])

        aggregate_backfill_service.run(db, budget_seconds=60)

        assert pop_dirty_days(10) == []

    def test_a_day_retention_already_emptied_keeps_its_row(self, db: Session) -> None:
        source = DataSourceFactory()
        noon = datetime(2025, 1, 10, 12, tzinfo=timezone.utc)
        samples = [
            DataPointSeriesFactory(mapping=source, recorded_at=noon + timedelta(minutes=n), value=Decimal(v))
            for n, v in ((0, "60"), (1, "80"))
        ]
        SeriesRollupRepository().roll_up(db, source.id, [date(2025, 1, 10)])
        for sample in samples:
            db.delete(sample)
        DataPointSeriesFactory(mapping=source, recorded_at=noon + timedelta(hours=1), value=Decimal("90"))
        db.get(ArchivalSetting, 1).deleted_before = date(2025, 2, 1)
        db.flush()

        aggregate_backfill_service.run(db, budget_seconds=60)

        (row,) = db.query(SeriesAggregate).filter(SeriesAggregate.computed_by == ComputedBy.OPEN_WEARABLES)
        assert row.avg == Decimal("70")

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


class TestDeleteCopiedSamples:
    def test_copied_values_go_and_a_genuine_sample_at_midnight_stays(self, db: Session) -> None:
        source = DataSourceFactory(provider=ProviderName.POLAR)
        midnight = datetime(2025, 6, 2, tzinfo=timezone.utc)
        _sample(db, source, SeriesType.heart_rate_variability_rmssd, midnight, "61")
        _sample(db, source, SeriesType.heart_rate_variability_rmssd, midnight + timedelta(days=1), "70")
        # The provider's own day value for the second night differs: that 00:00 sample is a genuine reading.
        provider_day(db, source, SeriesType.heart_rate_variability_rmssd, date(2025, 6, 3), avg=Decimal("64"))

        aggregate_backfill_service.run(db, budget_seconds=60)

        assert [(s.recorded_at, s.value) for s in db.query(SeriesSample)] == [
            (midnight + timedelta(days=1), Decimal("70"))
        ]
        assert (source.id, date(2025, 6, 2)) in pop_dirty_days(10)

    def test_a_failed_queue_keeps_the_samples_for_the_next_run(self, db: Session) -> None:
        """Once gone, the samples could not say which days to roll up again."""
        source = DataSourceFactory(provider=ProviderName.POLAR)
        _sample(db, source, SeriesType.heart_rate_variability_rmssd, datetime(2025, 6, 2, tzinfo=timezone.utc), "61")

        with (
            patch("app.integrations.rollup_queue.requeue_dirty_days", side_effect=RedisError),
            pytest.raises(RedisError),
        ):
            aggregate_backfill_service.run(db, budget_seconds=60)
        db.rollback()

        assert db.query(SeriesSample).count() == 1

    def test_the_delete_waits_for_a_scheduled_rollup_in_progress(self, db: Session) -> None:
        source = DataSourceFactory(provider=ProviderName.POLAR)
        _sample(db, source, SeriesType.heart_rate_variability_rmssd, datetime(2025, 6, 2, tzinfo=timezone.utc), "61")
        # Every step but the delete, which then runs on its own while the rollup holds the lock.
        DataMigrationRepository().mark_completed(db, "aggregate_backfill:delete_copied_samples")
        aggregate_backfill_service.run(db, budget_seconds=60)
        get_redis_client().set("series_rollup:lock", "1")

        assert not aggregate_backfill_service._delete_copied_samples(db, deadline=float("inf"))
        assert db.query(SeriesSample).count() == 1

    def test_a_sample_matching_another_statistic_of_the_providers_row_stays(self, db: Session) -> None:
        source = DataSourceFactory(provider=ProviderName.POLAR)
        midnight = datetime(2025, 6, 2, tzinfo=timezone.utc)
        _sample(db, source, SeriesType.heart_rate_variability_rmssd, midnight, "70")
        # The night's HRV is read from avg; the row's max came from elsewhere and proves nothing about the sample.
        provider_day(
            db, source, SeriesType.heart_rate_variability_rmssd, date(2025, 6, 2), avg=Decimal("64"), max=Decimal("70")
        )

        aggregate_backfill_service.run(db, budget_seconds=60)

        assert [s.value for s in db.query(SeriesSample)] == [Decimal("70")]

    def test_a_session_value_goes_only_when_its_sleep_also_carries_its_instant(self, db: Session) -> None:
        source = DataSourceFactory(provider=ProviderName.OURA)
        start = datetime(2025, 6, 1, 22, tzinfo=timezone.utc)
        EventRecordFactory(
            data_source=source, category="sleep", type="sleep", start_datetime=start, duration_seconds=8 * 3600
        )
        _sample(db, source, SeriesType.resting_heart_rate, start + timedelta(hours=8), "48")
        # Copied onto the same sleep, but its instant is not the sleep's end: the row cannot say when it was.
        _sample(db, source, SeriesType.respiratory_rate, start + timedelta(hours=3), "14")

        aggregate_backfill_service.run(db, budget_seconds=60)

        assert [(s.recorded_at, s.value) for s in db.query(SeriesSample)] == [
            (start + timedelta(hours=3), Decimal("14"))
        ]
        assert aggregate_backfill_service.is_done(db)

    def test_a_day_value_off_its_midnight_stays(self, db: Session) -> None:
        source = DataSourceFactory(provider=ProviderName.WHOOP)
        # A cycle total stored at the cycle's start, not at the day's midnight.
        _sample(db, source, SeriesType.steps, datetime(2025, 6, 1, 7, 30, tzinfo=timezone.utc), "9000")

        aggregate_backfill_service.run(db, budget_seconds=60)

        assert db.query(SeriesAggregate).filter(SeriesAggregate.computed_by == ComputedBy.PROVIDER).count() == 1
        assert db.query(SeriesSample).count() == 1

    def test_nothing_is_deleted_before_the_history_is_copied(self, db: Session) -> None:
        source = DataSourceFactory(provider=ProviderName.SUUNTO)
        _sample(
            db, source, SeriesType.steps, datetime(2025, 6, 1, 22, tzinfo=timezone.utc), "9000", is_daily_total=True
        )

        assert not aggregate_backfill_service._delete_copied_samples(db, deadline=float("inf"))
        assert db.query(SeriesSample).count() == 1
