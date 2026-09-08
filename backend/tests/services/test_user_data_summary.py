from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import DataPointSeriesArchive, DataSource, SeriesTypeDefinition
from app.schemas.enums import AggregationMethod, ProviderName, TimelineBucket, TimelineGroupBy
from app.schemas.responses.dashboard import UserDataTimelineResponse
from app.services.system_info_service import system_info_service
from tests.factories import (
    DataPointSeriesFactory,
    DataSourceFactory,
    EventRecordFactory,
    SeriesTypeDefinitionFactory,
    UserFactory,
)


def _archive_row(
    db: Session,
    data_source: DataSource,
    series_type: SeriesTypeDefinition,
    day: datetime,
    *,
    sample_count: int,
    aggregation: AggregationMethod = AggregationMethod.AVG,
) -> DataPointSeriesArchive:
    """Add an archived daily aggregate, as the archival job would write it."""
    row = DataPointSeriesArchive(
        id=uuid4(),
        data_source_id=data_source.id,
        series_type_definition_id=series_type.id,
        bucket_start_at=day,
        aggregation_type=aggregation,
        value=Decimal("70"),
        sample_count=sample_count,
    )
    db.add(row)
    db.commit()
    return row


class TestGetUserDataSummary:
    """Tests for SystemInfoService.get_user_data_summary."""

    def test_empty_user(self, db: Session) -> None:
        """User with no data returns all zeros."""
        user = UserFactory()
        result = system_info_service.get_user_data_summary(db, user.id)

        assert result.user_id == str(user.id)
        assert result.total_data_points == 0
        assert result.total_workouts == 0
        assert result.total_sleep_events == 0
        assert result.series_type_counts == {}
        assert result.workout_type_counts == {}
        assert result.by_provider == []

    def test_series_type_counts(self, db: Session) -> None:
        """Counts data points grouped by series type."""
        user = UserFactory()
        ds = DataSourceFactory(user=user, provider=ProviderName.APPLE)
        hr_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate()
        steps_type = SeriesTypeDefinitionFactory.get_or_create_steps()

        for _ in range(3):
            DataPointSeriesFactory(data_source=ds, series_type=hr_type)
        for _ in range(2):
            DataPointSeriesFactory(data_source=ds, series_type=steps_type)

        result = system_info_service.get_user_data_summary(db, user.id)

        assert result.total_data_points == 5
        assert result.series_type_counts["heart_rate"] == 3
        assert result.series_type_counts["steps"] == 2

    def test_workout_and_sleep_counts(self, db: Session) -> None:
        """Counts workouts and sleep events separately."""
        user = UserFactory()
        ds = DataSourceFactory(user=user, provider=ProviderName.GARMIN)

        for _ in range(4):
            EventRecordFactory(data_source=ds, category="workout", type="running")
        for _ in range(2):
            EventRecordFactory(data_source=ds, category="workout", type="cycling")
        for _ in range(3):
            EventRecordFactory(data_source=ds, category="sleep", type="sleep_session")

        result = system_info_service.get_user_data_summary(db, user.id)

        assert result.total_workouts == 6
        assert result.total_sleep_events == 3
        assert result.workout_type_counts["running"] == 4
        assert result.workout_type_counts["cycling"] == 2

    def test_multi_provider_breakdown(self, db: Session) -> None:
        """Breaks down counts by provider."""
        user = UserFactory()
        apple_ds = DataSourceFactory(user=user, provider=ProviderName.APPLE)
        garmin_ds = DataSourceFactory(user=user, provider=ProviderName.GARMIN)
        hr_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate()

        for _ in range(5):
            DataPointSeriesFactory(data_source=apple_ds, series_type=hr_type)
        for _ in range(3):
            DataPointSeriesFactory(data_source=garmin_ds, series_type=hr_type)

        EventRecordFactory(data_source=apple_ds, category="workout", type="running")
        EventRecordFactory(data_source=garmin_ds, category="sleep", type="sleep_session")

        result = system_info_service.get_user_data_summary(db, user.id)

        assert len(result.by_provider) == 2

        providers_by_name = {p.provider: p for p in result.by_provider}
        apple = providers_by_name[ProviderName.APPLE]
        garmin = providers_by_name[ProviderName.GARMIN]

        assert apple.data_points == 5
        assert apple.series_counts["heart_rate"] == 5
        assert apple.workout_count == 1
        assert apple.sleep_count == 0

        assert garmin.data_points == 3
        assert garmin.series_counts["heart_rate"] == 3
        assert garmin.workout_count == 0
        assert garmin.sleep_count == 1

    def test_does_not_include_other_users(self, db: Session) -> None:
        """Only counts data belonging to the requested user."""
        user_a = UserFactory()
        user_b = UserFactory()
        ds_a = DataSourceFactory(user=user_a, provider=ProviderName.APPLE)
        ds_b = DataSourceFactory(user=user_b, provider=ProviderName.APPLE)
        hr_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate()

        for _ in range(3):
            DataPointSeriesFactory(data_source=ds_a, series_type=hr_type)
        for _ in range(7):
            DataPointSeriesFactory(data_source=ds_b, series_type=hr_type)

        result = system_info_service.get_user_data_summary(db, user_a.id)
        assert result.total_data_points == 3

    def test_nonexistent_user(self, db: Session) -> None:
        """Returns empty summary for a user ID with no data."""
        result = system_info_service.get_user_data_summary(db, uuid4())
        assert result.total_data_points == 0
        assert result.by_provider == []

    def test_providers_sorted_by_total_records(self, db: Session) -> None:
        """Providers are sorted by total record count descending."""
        user = UserFactory()
        small_ds = DataSourceFactory(user=user, provider=ProviderName.OURA)
        big_ds = DataSourceFactory(user=user, provider=ProviderName.APPLE)
        hr_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate()

        DataPointSeriesFactory(data_source=small_ds, series_type=hr_type)
        for _ in range(10):
            DataPointSeriesFactory(data_source=big_ds, series_type=hr_type)

        result = system_info_service.get_user_data_summary(db, user.id)

        assert result.by_provider[0].provider == ProviderName.APPLE
        assert result.by_provider[1].provider == ProviderName.OURA


class TestGetUserDataSummaryDateFilter:
    """Tests for date-range scoping of SummariesService.get_user_data_summary."""

    def test_filters_data_points_by_recorded_at(self, db: Session) -> None:
        """Only data points whose recorded_at falls in [start, end) are counted."""
        user = UserFactory()
        ds = DataSourceFactory(user=user, provider=ProviderName.APPLE)
        hr_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate()

        before = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
        after = datetime(2026, 6, 20, 12, 0, tzinfo=timezone.utc)

        # Distinct timestamps within the day to satisfy the (source, type, recorded_at) unique constraint.
        for hour in (10, 12, 14):
            DataPointSeriesFactory(
                data_source=ds, series_type=hr_type, recorded_at=datetime(2026, 6, 15, hour, 0, tzinfo=timezone.utc)
            )
        DataPointSeriesFactory(data_source=ds, series_type=hr_type, recorded_at=before)
        DataPointSeriesFactory(data_source=ds, series_type=hr_type, recorded_at=after)

        # Single day window covering 2026-06-15.
        start = datetime(2026, 6, 15, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 6, 16, 0, 0, tzinfo=timezone.utc)

        result = system_info_service.get_user_data_summary(db, user.id, start, end)

        assert result.total_data_points == 3
        assert result.series_type_counts["heart_rate"] == 3
        assert result.by_provider[0].provider == ProviderName.APPLE
        assert result.by_provider[0].data_points == 3

    def test_filters_events_by_start_datetime(self, db: Session) -> None:
        """Only events whose start_datetime falls in [start, end) are counted."""
        user = UserFactory()
        ds = DataSourceFactory(user=user, provider=ProviderName.GARMIN)

        after = datetime(2026, 6, 20, 8, 0, tzinfo=timezone.utc)

        # Distinct start times within the day to satisfy the (source, start, end) unique constraint.
        EventRecordFactory(
            data_source=ds,
            category="workout",
            type="running",
            start_datetime=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
        )
        EventRecordFactory(
            data_source=ds,
            category="sleep",
            type="sleep_session",
            start_datetime=datetime(2026, 6, 15, 22, 0, tzinfo=timezone.utc),
        )
        EventRecordFactory(data_source=ds, category="workout", type="cycling", start_datetime=after)

        start = datetime(2026, 6, 15, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 6, 16, 0, 0, tzinfo=timezone.utc)

        result = system_info_service.get_user_data_summary(db, user.id, start, end)

        assert result.total_workouts == 1
        assert result.total_sleep_events == 1
        assert result.workout_type_counts == {"running": 1}

    def test_no_dates_returns_all_time(self, db: Session) -> None:
        """Omitting the date range preserves all-time behaviour."""
        user = UserFactory()
        ds = DataSourceFactory(user=user, provider=ProviderName.APPLE)
        hr_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate()

        DataPointSeriesFactory(
            data_source=ds, series_type=hr_type, recorded_at=datetime(2020, 1, 1, tzinfo=timezone.utc)
        )
        DataPointSeriesFactory(
            data_source=ds, series_type=hr_type, recorded_at=datetime(2026, 6, 15, tzinfo=timezone.utc)
        )

        result = system_info_service.get_user_data_summary(db, user.id)

        assert result.total_data_points == 2

    def test_open_ended_start_only(self, db: Session) -> None:
        """A start-only window counts everything at or after the start."""
        user = UserFactory()
        ds = DataSourceFactory(user=user, provider=ProviderName.APPLE)
        hr_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate()

        DataPointSeriesFactory(
            data_source=ds, series_type=hr_type, recorded_at=datetime(2026, 6, 10, tzinfo=timezone.utc)
        )
        DataPointSeriesFactory(
            data_source=ds, series_type=hr_type, recorded_at=datetime(2026, 6, 20, tzinfo=timezone.utc)
        )

        start = datetime(2026, 6, 15, 0, 0, tzinfo=timezone.utc)
        result = system_info_service.get_user_data_summary(db, user.id, start, None)

        assert result.total_data_points == 1


class TestUserDataSummaryArchive:
    """Counts must survive archival: the live table loses everything past the cutoff."""

    def test_archived_data_points_are_counted(self, db: Session) -> None:
        user = UserFactory()
        ds = DataSourceFactory(user=user, provider=ProviderName.OURA)
        hr_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate()

        DataPointSeriesFactory(
            data_source=ds, series_type=hr_type, recorded_at=datetime(2026, 6, 15, 8, tzinfo=timezone.utc)
        )
        _archive_row(db, ds, hr_type, datetime(2026, 1, 5, tzinfo=timezone.utc), sample_count=400)

        result = system_info_service.get_user_data_summary(db, user.id)

        assert result.total_data_points == 401
        assert result.series_type_counts["heart_rate"] == 401
        assert result.by_provider[0].series_counts["heart_rate"] == 401

    def test_same_archived_day_is_counted_once(self, db: Session) -> None:
        """aggregation_type is part of the archive key, so one day can hold several rows."""
        user = UserFactory()
        ds = DataSourceFactory(user=user, provider=ProviderName.OURA)
        hr_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate()
        day = datetime(2026, 1, 5, tzinfo=timezone.utc)

        _archive_row(db, ds, hr_type, day, sample_count=400, aggregation=AggregationMethod.AVG)
        _archive_row(db, ds, hr_type, day, sample_count=400, aggregation=AggregationMethod.MAX)

        result = system_info_service.get_user_data_summary(db, user.id)

        assert result.total_data_points == 400

    def test_archived_days_respect_the_window(self, db: Session) -> None:
        user = UserFactory()
        ds = DataSourceFactory(user=user, provider=ProviderName.OURA)
        hr_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate()

        _archive_row(db, ds, hr_type, datetime(2026, 1, 5, tzinfo=timezone.utc), sample_count=400)
        _archive_row(db, ds, hr_type, datetime(2026, 2, 5, tzinfo=timezone.utc), sample_count=7)

        result = system_info_service.get_user_data_summary(
            db,
            user.id,
            datetime(2026, 2, 1, tzinfo=timezone.utc),
            datetime(2026, 3, 1, tzinfo=timezone.utc),
        )

        assert result.total_data_points == 7


class TestGetUserDataTimeline:
    """Tests for SystemInfoService.get_user_data_timeline."""

    def _buckets(self, response: UserDataTimelineResponse, key: str) -> dict[str, int]:
        return {str(day): count for day, count in next(s for s in response.series if s.key == key).buckets}

    def test_empty_user_has_no_series(self, db: Session) -> None:
        user = UserFactory()
        result = system_info_service.get_user_data_timeline(db, user.id)

        assert result.bucket == TimelineBucket.DAY
        assert result.group_by == TimelineGroupBy.PROVIDER
        assert result.series == []

    def test_buckets_use_utc_not_the_session_timezone(self, db: Session) -> None:
        """A bare date_trunc would follow the connection's timezone and split days elsewhere."""
        user = UserFactory()
        ds = DataSourceFactory(user=user, provider=ProviderName.GARMIN)
        hr_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate()

        # 00:30Z on the 16th is still the 15th in New York.
        DataPointSeriesFactory(
            data_source=ds, series_type=hr_type, recorded_at=datetime(2026, 6, 15, 23, 30, tzinfo=timezone.utc)
        )
        DataPointSeriesFactory(
            data_source=ds, series_type=hr_type, recorded_at=datetime(2026, 6, 16, 0, 30, tzinfo=timezone.utc)
        )
        db.execute(text("SET LOCAL TIME ZONE 'America/New_York'"))

        result = system_info_service.get_user_data_timeline(db, user.id)

        assert self._buckets(result, ProviderName.GARMIN) == {"2026-06-15": 1, "2026-06-16": 1}

    def test_empty_buckets_are_omitted(self, db: Session) -> None:
        user = UserFactory()
        ds = DataSourceFactory(user=user, provider=ProviderName.GARMIN)
        hr_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate()

        for day in (15, 17):
            DataPointSeriesFactory(
                data_source=ds, series_type=hr_type, recorded_at=datetime(2026, 6, day, 8, tzinfo=timezone.utc)
            )

        result = system_info_service.get_user_data_timeline(db, user.id)

        assert self._buckets(result, ProviderName.GARMIN) == {"2026-06-15": 1, "2026-06-17": 1}

    def test_groups_by_series_type(self, db: Session) -> None:
        user = UserFactory()
        ds = DataSourceFactory(user=user, provider=ProviderName.GARMIN)
        hr_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate()
        steps_type = SeriesTypeDefinitionFactory.get_or_create_steps()

        for hour in (8, 9):
            DataPointSeriesFactory(
                data_source=ds, series_type=hr_type, recorded_at=datetime(2026, 6, 15, hour, tzinfo=timezone.utc)
            )
        DataPointSeriesFactory(
            data_source=ds, series_type=steps_type, recorded_at=datetime(2026, 6, 15, 8, tzinfo=timezone.utc)
        )

        result = system_info_service.get_user_data_timeline(db, user.id, group_by=TimelineGroupBy.SERIES_TYPE)

        # Series are ordered by total, so the heavier type comes first.
        assert [s.key for s in result.series] == ["heart_rate", "steps"]
        assert self._buckets(result, "heart_rate") == {"2026-06-15": 2}
        assert self._buckets(result, "steps") == {"2026-06-15": 1}

    def test_week_bucket_starts_on_monday(self, db: Session) -> None:
        user = UserFactory()
        ds = DataSourceFactory(user=user, provider=ProviderName.GARMIN)
        hr_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate()

        # 2026-06-15 is a Monday; the 17th shares its week, the 22nd opens the next.
        for day in (15, 17, 22):
            DataPointSeriesFactory(
                data_source=ds, series_type=hr_type, recorded_at=datetime(2026, 6, day, 8, tzinfo=timezone.utc)
            )

        result = system_info_service.get_user_data_timeline(db, user.id, bucket=TimelineBucket.WEEK)

        assert result.bucket == TimelineBucket.WEEK
        assert self._buckets(result, ProviderName.GARMIN) == {"2026-06-15": 2, "2026-06-22": 1}

    def test_archived_days_are_not_gaps(self, db: Session) -> None:
        """The point of the timeline: archived history must not render as missing data."""
        user = UserFactory()
        ds = DataSourceFactory(user=user, provider=ProviderName.OURA)
        hr_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate()

        # A live-only day, an archived-only day, and one the two share.
        for recorded_at in (
            datetime(2026, 6, 15, 8, tzinfo=timezone.utc),
            datetime(2026, 2, 20, 8, tzinfo=timezone.utc),
        ):
            DataPointSeriesFactory(data_source=ds, series_type=hr_type, recorded_at=recorded_at)
        _archive_row(db, ds, hr_type, datetime(2026, 1, 5, tzinfo=timezone.utc), sample_count=288)
        _archive_row(db, ds, hr_type, datetime(2026, 2, 20, tzinfo=timezone.utc), sample_count=10)

        result = system_info_service.get_user_data_timeline(db, user.id)

        assert self._buckets(result, ProviderName.OURA) == {
            "2026-01-05": 288,
            "2026-02-20": 11,
            "2026-06-15": 1,
        }

    def test_archived_day_survives_a_window_opening_mid_day(self, db: Session) -> None:
        """An archived day is one indivisible row, so a mid-day start keeps the whole day."""
        user = UserFactory()
        ds = DataSourceFactory(user=user, provider=ProviderName.OURA)
        hr_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate()

        _archive_row(db, ds, hr_type, datetime(2026, 1, 5, tzinfo=timezone.utc), sample_count=288)

        result = system_info_service.get_user_data_timeline(
            db,
            user.id,
            start_datetime=datetime(2026, 1, 5, 12, tzinfo=timezone.utc),
            end_datetime=datetime(2026, 1, 6, tzinfo=timezone.utc),
        )

        assert self._buckets(result, ProviderName.OURA) == {"2026-01-05": 288}

    def test_window_scopes_live_counts(self, db: Session) -> None:
        user = UserFactory()
        ds = DataSourceFactory(user=user, provider=ProviderName.GARMIN)
        hr_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate()

        for day in (10, 15, 20):
            DataPointSeriesFactory(
                data_source=ds, series_type=hr_type, recorded_at=datetime(2026, 6, day, 8, tzinfo=timezone.utc)
            )

        result = system_info_service.get_user_data_timeline(
            db,
            user.id,
            start_datetime=datetime(2026, 6, 15, tzinfo=timezone.utc),
            end_datetime=datetime(2026, 6, 16, tzinfo=timezone.utc),
        )

        assert self._buckets(result, ProviderName.GARMIN) == {"2026-06-15": 1}

    def test_other_users_are_excluded(self, db: Session) -> None:
        user = UserFactory()
        other = UserFactory()
        hr_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate()
        DataPointSeriesFactory(
            data_source=DataSourceFactory(user=user, provider=ProviderName.GARMIN),
            series_type=hr_type,
            recorded_at=datetime(2026, 6, 15, 8, tzinfo=timezone.utc),
        )
        other_ds = DataSourceFactory(user=other, provider=ProviderName.WHOOP)
        DataPointSeriesFactory(
            data_source=other_ds, series_type=hr_type, recorded_at=datetime(2026, 6, 15, 8, tzinfo=timezone.utc)
        )
        _archive_row(db, other_ds, hr_type, datetime(2026, 1, 5, tzinfo=timezone.utc), sample_count=288)

        result = system_info_service.get_user_data_timeline(db, user.id)

        assert [s.key for s in result.series] == [ProviderName.GARMIN]
        assert self._buckets(result, ProviderName.GARMIN) == {"2026-06-15": 1}
