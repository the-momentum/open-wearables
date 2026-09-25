"""Tests for data_type_coverage, written from the series and event write paths."""

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session

from app.models import DataPointSeries, DataTypeCoverage, EventRecord
from app.repositories.data_point_series_repository import DataPointSeriesRepository
from app.repositories.data_type_coverage_repository import data_type_coverage_repository
from app.repositories.event_record_repository import EventRecordRepository
from app.schemas.data_type_coverage import CoverageSpan
from app.schemas.enums import ProviderName, SeriesType
from app.schemas.model_crud.activities import EventRecordCreate, TimeSeriesSampleCreate
from app.schemas.sync_status import DataTypeKind
from tests.factories import DataSourceFactory, UserFactory

NOW = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)


def _sample(user_id: UUID, recorded_at: datetime, series_type: SeriesType) -> TimeSeriesSampleCreate:
    return TimeSeriesSampleCreate(
        id=uuid4(),
        user_id=user_id,
        source="oura",
        provider="oura",
        device_model="ring",
        recorded_at=recorded_at,
        value=60,
        series_type=series_type,
    )


def _event(user_id: UUID, start: datetime, end: datetime, category: str) -> EventRecordCreate:
    return EventRecordCreate(
        id=uuid4(),
        user_id=user_id,
        source="oura",
        provider="oura",
        source_name="Oura",
        category=category,
        start_datetime=start,
        end_datetime=end,
    )


class TestSeriesCoverage:
    @pytest.fixture
    def series_repo(self) -> DataPointSeriesRepository:
        return DataPointSeriesRepository(DataPointSeries)

    def test_bulk_create_records_span_per_series_type(
        self, db: Session, series_repo: DataPointSeriesRepository
    ) -> None:
        user = UserFactory()
        series_repo.bulk_create(
            db,
            [
                _sample(user.id, NOW, SeriesType.heart_rate),
                _sample(user.id, NOW + timedelta(hours=2), SeriesType.heart_rate),
                _sample(user.id, NOW + timedelta(hours=1), SeriesType.steps),
            ],
        )
        db.commit()

        rows = data_type_coverage_repository.list_for_user(db, user.id)

        assert [(r.provider, r.data_type, r.kind) for r in rows] == [
            ("oura", "heart_rate", DataTypeKind.SERIES),
            ("oura", "steps", DataTypeKind.SERIES),
        ]
        heart_rate = rows[0]
        assert heart_rate.coverage_start == NOW
        assert heart_rate.coverage_end == NOW + timedelta(hours=2)

    def test_later_batch_widens_range_in_both_directions(
        self, db: Session, series_repo: DataPointSeriesRepository
    ) -> None:
        user = UserFactory()
        series_repo.bulk_create(db, [_sample(user.id, NOW, SeriesType.heart_rate)])
        db.commit()

        # A backfill reaching into the past and a live sample after it, out of order.
        series_repo.bulk_create(db, [_sample(user.id, NOW + timedelta(days=1), SeriesType.heart_rate)])
        db.commit()
        series_repo.bulk_create(db, [_sample(user.id, NOW - timedelta(days=30), SeriesType.heart_rate)])
        db.commit()

        coverage = data_type_coverage_repository.get(db, user.id, "oura", "heart_rate")

        assert coverage is not None
        assert coverage.coverage_start == NOW - timedelta(days=30)
        assert coverage.coverage_end == NOW + timedelta(days=1)

    def test_resent_data_moves_last_written_at_only(self, db: Session, series_repo: DataPointSeriesRepository) -> None:
        user = UserFactory()
        series_repo.bulk_create(db, [_sample(user.id, NOW, SeriesType.heart_rate)])
        db.commit()
        first = data_type_coverage_repository.get(db, user.id, "oura", "heart_rate")
        assert first is not None
        first_written_at = first.last_written_at

        series_repo.bulk_create(db, [_sample(user.id, NOW, SeriesType.heart_rate)])
        db.commit()
        db.expire_all()

        coverage = data_type_coverage_repository.get(db, user.id, "oura", "heart_rate")
        assert coverage is not None
        assert coverage.coverage_start == NOW
        assert coverage.coverage_end == NOW
        assert coverage.last_written_at > first_written_at

    def test_several_batches_in_one_transaction_write_one_row(
        self, db: Session, series_repo: DataPointSeriesRepository
    ) -> None:
        user = UserFactory()
        series_repo.bulk_create(db, [_sample(user.id, NOW, SeriesType.heart_rate)])
        series_repo.bulk_create(db, [_sample(user.id, NOW + timedelta(hours=5), SeriesType.heart_rate)])
        db.commit()

        rows = data_type_coverage_repository.list_for_user(db, user.id)

        assert len(rows) == 1
        assert rows[0].coverage_start == NOW
        assert rows[0].coverage_end == NOW + timedelta(hours=5)


class TestEventCoverage:
    @pytest.fixture
    def event_repo(self) -> EventRecordRepository:
        return EventRecordRepository(EventRecord)

    def test_bulk_create_records_span_per_category(self, db: Session, event_repo: EventRecordRepository) -> None:
        user = UserFactory()
        event_repo.bulk_create(
            db,
            [
                _event(user.id, NOW, NOW + timedelta(hours=1), "workout"),
                _event(user.id, NOW - timedelta(hours=9), NOW - timedelta(hours=1), "sleep"),
            ],
        )
        db.commit()

        rows = data_type_coverage_repository.list_for_user(db, user.id)

        assert [(r.data_type, r.kind) for r in rows] == [
            ("sleep", DataTypeKind.EVENT),
            ("workout", DataTypeKind.EVENT),
        ]
        sleep = rows[0]
        assert sleep.coverage_start == NOW - timedelta(hours=9)
        assert sleep.coverage_end == NOW - timedelta(hours=1)

    def test_create_and_flush_records_coverage_without_committing(
        self, db: Session, event_repo: EventRecordRepository
    ) -> None:
        user = UserFactory()
        event_repo.create_and_flush(db, _event(user.id, NOW, NOW + timedelta(hours=1), "workout"))

        coverage = data_type_coverage_repository.get(db, user.id, "oura", "workout")
        assert coverage is not None
        assert coverage.coverage_end == NOW + timedelta(hours=1)

    def test_series_and_events_coexist_under_their_own_kind(
        self, db: Session, event_repo: EventRecordRepository
    ) -> None:
        user = UserFactory()
        DataPointSeriesRepository(DataPointSeries).bulk_create(db, [_sample(user.id, NOW, SeriesType.heart_rate)])
        event_repo.bulk_create(db, [_event(user.id, NOW, NOW + timedelta(hours=1), "workout")])
        db.commit()

        rows = data_type_coverage_repository.list_for_user(db, user.id)

        assert {(r.data_type, r.kind) for r in rows} == {
            ("heart_rate", DataTypeKind.SERIES),
            ("workout", DataTypeKind.EVENT),
        }


def test_rollback_takes_coverage_with_it(db: Session) -> None:
    """A transaction that never landed must not leave coverage claiming its data."""
    user = UserFactory()
    db.commit()

    data_type_coverage_repository.record(
        db,
        [CoverageSpan(user.id, "oura", "heart_rate", DataTypeKind.SERIES, NOW, NOW)],
    )
    db.rollback()

    assert db.query(DataTypeCoverage).filter_by(user_id=user.id).count() == 0


def test_event_categories_do_not_collide_with_series_slugs() -> None:
    """Coverage is keyed by data_type alone, so the two vocabularies must stay disjoint.

    A category that is also a SeriesType slug would merge a series and an event into one
    row, widening the span across both and flip-flopping kind between writers.
    """
    categories = {"activity", "menstrual_cycle", "sleep", "workout"}

    assert categories & {series.value for series in SeriesType} == set()


def test_coverage_follows_the_referenced_data_source_not_the_payload(db: Session) -> None:
    """A creator carrying data_source_id has already chosen its source; its provider wins.

    Otherwise coverage files under whatever the payload happens to say — "unknown" when it
    says nothing — while the record itself files under the source's real provider.
    """
    user = UserFactory()
    data_source = DataSourceFactory(user=user, provider=ProviderName.GARMIN, source="garmin_connect")
    db.commit()

    record = EventRecordCreate(
        id=uuid4(),
        user_id=user.id,
        data_source_id=data_source.id,
        source_name="Garmin",
        category="workout",
        start_datetime=NOW,
        end_datetime=NOW + timedelta(hours=1),
    )
    EventRecordRepository(EventRecord).create_and_flush(db, record)
    db.commit()

    assert data_type_coverage_repository.get(db, user.id, "unknown", "workout") is None
    coverage = data_type_coverage_repository.get(db, user.id, "garmin", "workout")
    assert coverage is not None
    assert coverage.coverage_end == NOW + timedelta(hours=1)
