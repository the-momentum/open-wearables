from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.orm import Session

from app.integrations.celery.tasks.aggregate_backfill_task import run_aggregate_backfill
from app.integrations.redis_client import get_redis_client
from app.models import DataPointSeriesArchive, EventRecordAggregate, SeriesAggregate, SeriesSample, WorkoutDetails
from app.repositories import AggregateRepository
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


class TestBackfillTask:
    def test_a_run_waits_out_one_already_in_progress(self, db: Session) -> None:
        get_redis_client().set("aggregate_backfill:lock", "1")

        assert run_aggregate_backfill() == {"skipped": "previous_run_in_progress"}
