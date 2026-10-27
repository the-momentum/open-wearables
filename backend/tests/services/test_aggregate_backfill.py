from datetime import datetime, timezone
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
    WorkoutDetails,
)
from app.repositories import AggregateRepository
from app.repositories.aggregate_backfill_repository import AggregateBackfillRepository
from app.repositories.archival_repository import DataPointSeriesArchiveRepository
from app.repositories.data_migration_repository import DataMigrationRepository
from app.schemas.enums import AggregationMethod, ComputedBy, ProviderName, SeriesType, get_series_type_id
from app.services.aggregate_backfill_service import aggregate_backfill_service
from tests.factories import DataPointSeriesFactory, DataSourceFactory, EventRecordFactory, SeriesTypeDefinitionFactory

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
