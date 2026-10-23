"""Tests for data_type_coverage, written from the series and event write paths."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.integrations.celery.tasks.backfill_data_type_coverage_task import backfill_data_type_coverage
from app.models import DataPointSeriesArchive, DataTypeCoverage, EventRecord, SeriesSample
from app.repositories.archival_repository import BatchedRun
from app.repositories.data_point_series_repository import DataPointSeriesRepository
from app.repositories.data_source_repository import DataSourceRepository
from app.repositories.data_type_coverage_repository import data_type_coverage_repository
from app.repositories.event_record_repository import EventRecordRepository
from app.schemas.data_type_coverage import CoverageSpan
from app.schemas.enums import AggregationMethod, ProviderName, SeriesType
from app.schemas.model_crud.activities import EventRecordCreate, TimeSeriesSampleCreate
from app.schemas.sync_status import DataTypeKind
from app.services.archival_service import archival_service
from app.services.event_record_service import event_record_service
from tests.factories import (
    DataPointSeriesFactory,
    DataSourceFactory,
    EventRecordFactory,
    SeriesTypeDefinitionFactory,
    UserFactory,
)

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


def _event(
    user_id: UUID, start: datetime, end: datetime, category: str, external_id: str | None = None
) -> EventRecordCreate:
    return EventRecordCreate(
        id=uuid4(),
        user_id=user_id,
        source="oura",
        provider="oura",
        source_name="Oura",
        category=category,
        start_datetime=start,
        end_datetime=end,
        external_id=external_id,
    )


class TestSeriesCoverage:
    @pytest.fixture
    def series_repo(self) -> DataPointSeriesRepository:
        return DataPointSeriesRepository(SeriesSample)

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

        coverage = data_type_coverage_repository.get(db, user.id, "oura", "heart_rate", DataTypeKind.SERIES)

        assert coverage is not None
        assert coverage.coverage_start == NOW - timedelta(days=30)
        assert coverage.coverage_end == NOW + timedelta(days=1)

    def test_resent_data_moves_last_written_at_only(self, db: Session, series_repo: DataPointSeriesRepository) -> None:
        user = UserFactory()
        series_repo.bulk_create(db, [_sample(user.id, NOW, SeriesType.heart_rate)])
        db.commit()
        first = data_type_coverage_repository.get(db, user.id, "oura", "heart_rate", DataTypeKind.SERIES)
        assert first is not None
        first_written_at = first.last_written_at

        series_repo.bulk_create(db, [_sample(user.id, NOW, SeriesType.heart_rate)])
        db.commit()
        db.expire_all()

        coverage = data_type_coverage_repository.get(db, user.id, "oura", "heart_rate", DataTypeKind.SERIES)
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

        coverage = data_type_coverage_repository.get(db, user.id, "oura", "workout", DataTypeKind.EVENT)
        assert coverage is not None
        assert coverage.coverage_end == NOW + timedelta(hours=1)

    def test_series_and_events_coexist_under_their_own_kind(
        self, db: Session, event_repo: EventRecordRepository
    ) -> None:
        user = UserFactory()
        DataPointSeriesRepository(SeriesSample).bulk_create(db, [_sample(user.id, NOW, SeriesType.heart_rate)])
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


def test_a_series_and_an_event_sharing_a_name_keep_separate_spans(db: Session) -> None:
    user = UserFactory()
    data_type_coverage_repository.record(
        db,
        [
            CoverageSpan(user.id, "apple", "mindfulness", DataTypeKind.SERIES, NOW - timedelta(days=600), NOW),
            CoverageSpan(user.id, "apple", "mindfulness", DataTypeKind.EVENT, NOW - timedelta(days=30), NOW),
        ],
    )
    db.commit()

    event = data_type_coverage_repository.get(db, user.id, "apple", "mindfulness", DataTypeKind.EVENT)
    assert event is not None
    assert event.coverage_start == NOW - timedelta(days=30)
    assert len(data_type_coverage_repository.list_for_user(db, user.id)) == 2


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

    assert data_type_coverage_repository.get(db, user.id, "unknown", "workout", DataTypeKind.EVENT) is None
    coverage = data_type_coverage_repository.get(db, user.id, "garmin", "workout", DataTypeKind.EVENT)
    assert coverage is not None
    assert coverage.coverage_end == NOW + timedelta(hours=1)


class TestCoverageFollowsRemovals:
    """Coverage is what we hold, so removing data narrows it."""

    @pytest.fixture
    def event_repo(self) -> EventRecordRepository:
        return EventRecordRepository(EventRecord)

    def _span(
        self, db: Session, user_id: UUID, data_type: str, kind: DataTypeKind = DataTypeKind.EVENT
    ) -> tuple[datetime, datetime] | None:
        db.expire_all()
        row = data_type_coverage_repository.get(db, user_id, "oura", data_type, kind)
        return (row.coverage_start, row.coverage_end) if row else None

    def test_deleting_the_latest_event_moves_the_end_back(self, db: Session, event_repo: EventRecordRepository) -> None:
        user = UserFactory()
        early, late = (
            _event(user.id, NOW - timedelta(days=2), NOW - timedelta(days=2) + timedelta(hours=1), "workout"),
            _event(user.id, NOW, NOW + timedelta(hours=1), "workout"),
        )
        event_repo.bulk_create(db, [early, late])
        db.commit()

        assert event_record_service.delete_event_record(db, user.id, late.id, "workout")

        assert self._span(db, user.id, "workout") == (early.start_datetime, early.end_datetime)

    def test_deleting_the_last_event_of_a_category_forgets_it(
        self, db: Session, event_repo: EventRecordRepository
    ) -> None:
        user = UserFactory()
        event_repo.bulk_create(
            db,
            [
                _event(user.id, NOW, NOW + timedelta(hours=1), "workout", external_id="w1"),
                _event(user.id, NOW - timedelta(hours=9), NOW - timedelta(hours=1), "sleep"),
            ],
        )
        db.commit()

        assert event_repo.delete_by_external_id(db, user.id, "w1", provider="oura") == 1

        assert self._span(db, user.id, "workout") is None
        assert self._span(db, user.id, "sleep") == (NOW - timedelta(hours=9), NOW - timedelta(hours=1))

    def test_removals_without_coverage_yet_change_nothing(self, db: Session, event_repo: EventRecordRepository) -> None:
        """Before the backfill runs, older data has no coverage row to narrow."""
        user = UserFactory()
        workout = _event(user.id, NOW, NOW + timedelta(hours=1), "workout")
        event_repo.bulk_create(db, [workout])
        db.query(DataTypeCoverage).delete()
        db.commit()

        assert event_record_service.delete_event_record(db, user.id, workout.id, "workout")
        DataSourceRepository().delete_user_provider_data(db, user.id, ProviderName.OURA)
        data_type_coverage_repository.trim_series_before(db, NOW.date())

        assert data_type_coverage_repository.list_for_user(db, user.id) == []

    @pytest.mark.parametrize("narrow", ["refresh_events", "delete_for_provider"])
    def test_narrowing_holds_the_lock_the_backfill_shares(self, db: Session, narrow: str) -> None:
        """Held until commit, so a backfill batch that read the data before it went cannot widen it back."""
        user = UserFactory()
        if narrow == "refresh_events":
            data_type_coverage_repository.refresh_events(db, [(user.id, "oura", "workout")])
        else:
            data_type_coverage_repository.delete_for_provider(db, user.id, "oura")

        held = (
            db.execute(
                text(
                    "SELECT mode FROM pg_locks WHERE locktype = 'advisory' AND pid = pg_backend_pid()"
                    " AND objid = (hashtextextended('data_type_coverage:narrowing', 0) & 4294967295)::oid"
                )
            )
            .scalars()
            .all()
        )
        assert held == ["ExclusiveLock"]

    def test_purging_a_provider_forgets_its_coverage(self, db: Session, event_repo: EventRecordRepository) -> None:
        user = UserFactory()
        DataPointSeriesRepository(SeriesSample).bulk_create(db, [_sample(user.id, NOW, SeriesType.heart_rate)])
        event_repo.bulk_create(db, [_event(user.id, NOW, NOW + timedelta(hours=1), "workout")])
        db.commit()

        DataSourceRepository().delete_user_provider_data(db, user.id, ProviderName.OURA)

        assert data_type_coverage_repository.list_for_user(db, user.id) == []

    def test_retention_moves_series_up_to_the_cutoff(self, db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("app.repositories.data_type_coverage_repository._TRIM_BATCH_SIZE", 1)
        user = UserFactory()
        cutoff = datetime(2026, 5, 1, tzinfo=timezone.utc)
        data_type_coverage_repository.record(
            db,
            [
                CoverageSpan(user.id, "oura", "heart_rate", DataTypeKind.SERIES, cutoff - timedelta(days=9), NOW),
                CoverageSpan(
                    user.id,
                    "oura",
                    "steps",
                    DataTypeKind.SERIES,
                    cutoff - timedelta(days=9),
                    cutoff - timedelta(days=1),
                ),
                CoverageSpan(user.id, "oura", "workout", DataTypeKind.EVENT, cutoff - timedelta(days=9), NOW),
            ],
        )
        db.commit()

        data_type_coverage_repository.trim_series_before(db, cutoff.date())

        assert self._span(db, user.id, "heart_rate", DataTypeKind.SERIES) == (cutoff, NOW)
        assert self._span(db, user.id, "steps", DataTypeKind.SERIES) is None
        # Events are never retention-deleted.
        assert self._span(db, user.id, "workout") == (cutoff - timedelta(days=9), NOW)

    def test_retention_cutoff_day_starts_in_the_session_time_zone(self, db: Session) -> None:
        """Retention compares recorded_at::date, so the cutoff day starts where the session says."""
        user = UserFactory()
        data_type_coverage_repository.record(
            db, [CoverageSpan(user.id, "oura", "heart_rate", DataTypeKind.SERIES, NOW - timedelta(days=90), NOW)]
        )
        db.commit()
        db.execute(text("SET TIME ZONE 'Europe/Warsaw'"))

        data_type_coverage_repository.trim_series_before(db, date(2026, 5, 1))

        db.execute(text("SET TIME ZONE 'UTC'"))
        assert self._span(db, user.id, "heart_rate", DataTypeKind.SERIES) == (
            datetime(2026, 4, 30, 22, tzinfo=timezone.utc),
            NOW,
        )

    @pytest.mark.parametrize(("complete", "trimmed"), [(True, True), (False, False)])
    def test_retention_trims_only_once_nothing_older_is_left(self, complete: bool, trimmed: bool) -> None:
        setting = MagicMock(rollup_enabled=False, delete_after_days=30, deleted_before=None)
        with (
            patch.object(archival_service.settings_repo, "get", return_value=setting),
            patch.object(archival_service.archive_repo, "delete_live_before", return_value=BatchedRun(5, complete)),
            patch.object(data_type_coverage_repository, "trim_series_before") as trim,
        ):
            archival_service.run_daily_archival(MagicMock())

        assert trim.called is trimmed
        if trimmed:
            # The day retention cut at, so the trim counts it in the same time zone.
            assert trim.call_args.args[1] == date.today() - timedelta(days=30)


def _garmin_span(db: Session, user_id: UUID, data_type: str, kind: DataTypeKind) -> tuple[datetime, datetime] | None:
    db.expire_all()
    row = data_type_coverage_repository.get(db, user_id, "garmin", data_type, kind)
    return (row.coverage_start, row.coverage_end) if row else None


class TestBackfillFromHeldData:
    def test_spans_live_series_archive_and_events_across_batches(
        self, db: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("app.repositories.data_type_coverage_repository._BACKFILL_BATCH_SIZE", 1)
        user = UserFactory()
        watch = DataSourceFactory(user=user, provider=ProviderName.GARMIN, device_model="Forerunner 965")
        phone = DataSourceFactory(user=user, provider=ProviderName.GARMIN, device_model="Edge 1040")
        heart_rate = SeriesTypeDefinitionFactory.get_or_create_heart_rate()
        DataPointSeriesFactory(data_source=watch, series_type=heart_rate, recorded_at=NOW)
        DataPointSeriesFactory(data_source=phone, series_type=heart_rate, recorded_at=NOW + timedelta(days=2))
        db.add(
            DataPointSeriesArchive(
                id=uuid4(),
                data_source_id=watch.id,
                series_type_definition_id=heart_rate.id,
                bucket_start_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
                aggregation_type=AggregationMethod.AVG,
                value=Decimal(60),
                sample_count=100,
            )
        )
        EventRecordFactory(
            data_source=phone, category="workout", start_datetime=NOW, end_datetime=NOW + timedelta(hours=1)
        )
        db.flush()

        written = data_type_coverage_repository.backfill_from_held_data(db, dry_run=False)

        assert written == {DataTypeKind.SERIES: 2, DataTypeKind.EVENT: 1}
        assert _garmin_span(db, user.id, "heart_rate", DataTypeKind.SERIES) == (
            datetime(2025, 1, 1, tzinfo=timezone.utc),
            NOW + timedelta(days=2),
        )
        assert _garmin_span(db, user.id, "workout", DataTypeKind.EVENT) == (NOW, NOW + timedelta(hours=1))

    def test_only_widens_what_the_write_paths_already_hold(self, db: Session) -> None:
        user = UserFactory()
        source = DataSourceFactory(user=user, provider=ProviderName.GARMIN)
        DataPointSeriesFactory(
            data_source=source, series_type=SeriesTypeDefinitionFactory.get_or_create_heart_rate(), recorded_at=NOW
        )
        later = NOW + timedelta(days=30)
        data_type_coverage_repository.record(
            db, [CoverageSpan(user.id, "garmin", "heart_rate", DataTypeKind.SERIES, later, later)]
        )
        db.flush()

        data_type_coverage_repository.backfill_from_held_data(db, dry_run=False)

        assert _garmin_span(db, user.id, "heart_rate", DataTypeKind.SERIES) == (NOW, later)

    def test_dry_run_counts_and_writes_nothing(self, db: Session) -> None:
        source = DataSourceFactory(provider=ProviderName.GARMIN)
        DataPointSeriesFactory(
            data_source=source, series_type=SeriesTypeDefinitionFactory.get_or_create_heart_rate(), recorded_at=NOW
        )
        db.flush()

        assert data_type_coverage_repository.backfill_from_held_data(db, dry_run=True) == {
            DataTypeKind.SERIES: 1,
            DataTypeKind.EVENT: 0,
        }
        assert db.query(DataTypeCoverage).count() == 0


def test_backfill_task_runs_once_under_its_migration_name() -> None:
    task = "app.integrations.celery.tasks.backfill_data_type_coverage_task"
    with patch(f"{task}.engine"), patch(f"{task}.data_migration_service") as service:
        backfill_data_type_coverage()

    name, migrate = service.run.call_args.args[1:3]
    assert (name, service.run.call_args.kwargs["dry_run"]) == ("backfill_data_type_coverage", False)
    assert callable(migrate)
