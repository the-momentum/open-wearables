"""
Tests for server-side downsampling of the timeseries endpoint (resolution parameter).

Tests cover:
- The raw passthrough invariant (resolution="raw" returns stored samples unchanged)
- Each downsampling resolution (1min, 5min, 15min, 1hour)
- Aggregation semantics per series type (AVG for heart rate, SUM for steps)
- UTC-aligned bucket boundaries
- Empty ranges
- Pagination over downsampled buckets
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from app.models import DataSource, SeriesTypeDefinition, User
from app.schemas.enums import SeriesType, TimeseriesResolution
from app.schemas.model_crud.activities import TimeSeriesQueryParams
from app.services.timeseries_service import timeseries_service
from tests.factories import (
    DataPointSeriesFactory,
    DataSourceFactory,
    SeriesTypeDefinitionFactory,
    UserFactory,
)

RANGE_START = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
RANGE_END = datetime(2024, 1, 2, 0, 0, 0, tzinfo=timezone.utc)

# (user, data source, heart_rate series type, steps series type)
UserSetup = tuple[User, DataSource, SeriesTypeDefinition, SeriesTypeDefinition]


def make_params(
    resolution: TimeseriesResolution = TimeseriesResolution.RAW,
    limit: int = 50,
    cursor: str | None = None,
) -> TimeSeriesQueryParams:
    return TimeSeriesQueryParams(
        start_datetime=RANGE_START,
        end_datetime=RANGE_END,
        limit=limit,
        cursor=cursor,
        resolution=resolution,
    )


@pytest.fixture
def user_setup(db: Session) -> UserSetup:
    """A user with one data source and the seeded heart_rate/steps series types."""
    user = UserFactory()
    mapping = DataSourceFactory(user=user, source="apple_health_sdk")
    hr_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate()
    steps_type = SeriesTypeDefinitionFactory.get_or_create_steps()
    return user, mapping, hr_type, steps_type


class TestRawResolutionPassthrough:
    """resolution="raw" (the default) must return stored samples unchanged."""

    def test_raw_returns_stored_samples_unchanged(self, db: Session, user_setup: UserSetup) -> None:
        user, mapping, hr_type, _ = user_setup
        recorded_at = datetime(2024, 1, 1, 10, 0, 13, tzinfo=timezone.utc)
        for i in range(5):
            DataPointSeriesFactory(
                mapping=mapping,
                series_type=hr_type,
                recorded_at=recorded_at + timedelta(seconds=17 * i),
                value=60 + i,
            )

        result = timeseries_service.get_timeseries(db, user.id, [SeriesType.heart_rate], make_params())

        assert len(result.data) == 5
        assert result.pagination.total_count == 5
        # Timestamps are NOT aligned to any bucket: raw passthrough
        assert result.data[0].timestamp == recorded_at
        assert [item.value for item in result.data] == [60.0, 61.0, 62.0, 63.0, 64.0]
        # Raw responses do not advertise a resolution
        assert result.metadata.resolution is None

    def test_default_resolution_matches_explicit_raw(self, db: Session, user_setup: UserSetup) -> None:
        user, mapping, hr_type, _ = user_setup
        DataPointSeriesFactory(
            mapping=mapping,
            series_type=hr_type,
            recorded_at=datetime(2024, 1, 1, 10, 0, 13, tzinfo=timezone.utc),
            value=66,
        )

        default_params = TimeSeriesQueryParams(start_datetime=RANGE_START, end_datetime=RANGE_END)
        explicit_raw = make_params(TimeseriesResolution.RAW)

        default_result = timeseries_service.get_timeseries(db, user.id, [SeriesType.heart_rate], default_params)
        raw_result = timeseries_service.get_timeseries(db, user.id, [SeriesType.heart_rate], explicit_raw)

        assert default_result.model_dump() == raw_result.model_dump()


class TestDownsamplingResolutions:
    """Each non-raw resolution buckets and aggregates samples."""

    def test_one_minute_resolution_averages_heart_rate(self, db: Session, user_setup: UserSetup) -> None:
        user, mapping, hr_type, _ = user_setup
        # Three samples in the 10:00 bucket, one in the 10:01 bucket
        for seconds, value in [(5, 60), (25, 90), (45, 90)]:
            DataPointSeriesFactory(
                mapping=mapping,
                series_type=hr_type,
                recorded_at=datetime(2024, 1, 1, 10, 0, seconds, tzinfo=timezone.utc),
                value=value,
            )
        DataPointSeriesFactory(
            mapping=mapping,
            series_type=hr_type,
            recorded_at=datetime(2024, 1, 1, 10, 1, 5, tzinfo=timezone.utc),
            value=72,
        )

        result = timeseries_service.get_timeseries(
            db, user.id, [SeriesType.heart_rate], make_params(TimeseriesResolution.ONE_MINUTE)
        )

        assert len(result.data) == 2
        assert result.pagination.total_count == 2
        assert result.metadata.resolution == TimeseriesResolution.ONE_MINUTE
        assert result.metadata.sample_count == 2
        assert result.data[0].timestamp == datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        assert result.data[0].value == pytest.approx(80.0)  # (60 + 90 + 90) / 3
        assert result.data[0].unit == "bpm"
        assert result.data[1].timestamp == datetime(2024, 1, 1, 10, 1, 0, tzinfo=timezone.utc)
        assert result.data[1].value == pytest.approx(72.0)

    def test_five_minutes_resolution_sums_steps(self, db: Session, user_setup: UserSetup) -> None:
        user, mapping, _, steps_type = user_setup
        # 10:00:00, 10:00:59 and 10:04:59 all fall into the 10:00 five-minute bucket
        for seconds, value in [(0, 10), (59, 20), (299, 30)]:
            DataPointSeriesFactory(
                mapping=mapping,
                series_type=steps_type,
                recorded_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc) + timedelta(seconds=seconds),
                value=value,
            )

        result = timeseries_service.get_timeseries(
            db, user.id, [SeriesType.steps], make_params(TimeseriesResolution.FIVE_MINUTES)
        )

        assert len(result.data) == 1
        assert result.data[0].timestamp == datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        assert result.data[0].value == pytest.approx(60.0)  # 10 + 20 + 30
        assert result.data[0].unit == "count"

    def test_fifteen_minutes_resolution_buckets(self, db: Session, user_setup: UserSetup) -> None:
        user, mapping, hr_type, _ = user_setup
        # One sample per quarter hour across one hour
        for minute, value in [(0, 60), (15, 70), (30, 80), (45, 90)]:
            DataPointSeriesFactory(
                mapping=mapping,
                series_type=hr_type,
                recorded_at=datetime(2024, 1, 1, 10, minute, 0, tzinfo=timezone.utc),
                value=value,
            )

        result = timeseries_service.get_timeseries(
            db, user.id, [SeriesType.heart_rate], make_params(TimeseriesResolution.FIFTEEN_MINUTES)
        )

        assert [item.timestamp for item in result.data] == [
            datetime(2024, 1, 1, 10, minute, 0, tzinfo=timezone.utc) for minute in (0, 15, 30, 45)
        ]
        assert [item.value for item in result.data] == [60.0, 70.0, 80.0, 90.0]

    def test_one_hour_resolution_buckets(self, db: Session, user_setup: UserSetup) -> None:
        user, mapping, hr_type, _ = user_setup
        for hour, value in [(9, 55), (10, 65), (11, 75)]:
            DataPointSeriesFactory(
                mapping=mapping,
                series_type=hr_type,
                recorded_at=datetime(2024, 1, 1, hour, 30, 0, tzinfo=timezone.utc),
                value=value,
            )

        result = timeseries_service.get_timeseries(
            db, user.id, [SeriesType.heart_rate], make_params(TimeseriesResolution.ONE_HOUR)
        )

        assert [item.timestamp for item in result.data] == [
            datetime(2024, 1, 1, hour, 0, 0, tzinfo=timezone.utc) for hour in (9, 10, 11)
        ]


class TestBucketBoundaries:
    """Buckets are aligned on UTC epoch multiples of the interval."""

    def test_sample_at_bucket_start_opens_new_bucket(self, db: Session, user_setup: UserSetup) -> None:
        user, mapping, hr_type, _ = user_setup
        # 10:04:59 belongs to the 10:00 bucket, 10:05:00 opens the 10:05 bucket
        for minute, second, value in [(4, 59, 60), (5, 0, 70), (9, 59, 80)]:
            DataPointSeriesFactory(
                mapping=mapping,
                series_type=hr_type,
                recorded_at=datetime(2024, 1, 1, 10, minute, second, tzinfo=timezone.utc),
                value=value,
            )

        result = timeseries_service.get_timeseries(
            db, user.id, [SeriesType.heart_rate], make_params(TimeseriesResolution.FIVE_MINUTES)
        )

        assert len(result.data) == 2
        assert result.data[0].timestamp == datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        assert result.data[0].value == pytest.approx(60.0)
        assert result.data[1].timestamp == datetime(2024, 1, 1, 10, 5, 0, tzinfo=timezone.utc)
        assert result.data[1].value == pytest.approx(75.0)  # (70 + 80) / 2

    def test_buckets_do_not_merge_across_data_sources(self, db: Session, user_setup: UserSetup) -> None:
        user, mapping, hr_type, _ = user_setup
        other_mapping = DataSourceFactory(user=user, source="garmin_connect_api")
        recorded_at = datetime(2024, 1, 1, 10, 0, 30, tzinfo=timezone.utc)
        DataPointSeriesFactory(mapping=mapping, series_type=hr_type, recorded_at=recorded_at, value=60)
        DataPointSeriesFactory(mapping=other_mapping, series_type=hr_type, recorded_at=recorded_at, value=70)

        result = timeseries_service.get_timeseries(
            db, user.id, [SeriesType.heart_rate], make_params(TimeseriesResolution.ONE_MINUTE)
        )

        assert len(result.data) == 2
        assert {item.value for item in result.data} == {60.0, 70.0}
        assert {item.source.provider for item in result.data} == {"apple_health_sdk", "garmin_connect_api"}

    def test_mixed_series_types_bucket_independently(self, db: Session, user_setup: UserSetup) -> None:
        user, mapping, hr_type, steps_type = user_setup
        base = datetime(2024, 1, 1, 10, 0, 30, tzinfo=timezone.utc)
        DataPointSeriesFactory(mapping=mapping, series_type=hr_type, recorded_at=base, value=60)
        DataPointSeriesFactory(mapping=mapping, series_type=hr_type, recorded_at=base + timedelta(seconds=15), value=80)
        DataPointSeriesFactory(mapping=mapping, series_type=steps_type, recorded_at=base, value=100)
        DataPointSeriesFactory(
            mapping=mapping, series_type=steps_type, recorded_at=base + timedelta(seconds=15), value=50
        )

        result = timeseries_service.get_timeseries(db, user.id, [], make_params(TimeseriesResolution.ONE_MINUTE))

        by_type = {item.type: item for item in result.data}
        assert by_type[SeriesType.heart_rate].value == pytest.approx(70.0)  # AVG
        assert by_type[SeriesType.steps].value == pytest.approx(150.0)  # SUM


class TestDownsampledEdgeCases:
    def test_empty_range_returns_empty_page(self, db: Session, user_setup: UserSetup) -> None:
        user, _, _, _ = user_setup

        result = timeseries_service.get_timeseries(
            db, user.id, [SeriesType.heart_rate], make_params(TimeseriesResolution.FIVE_MINUTES)
        )

        assert result.data == []
        assert result.metadata.sample_count == 0
        assert result.metadata.resolution == TimeseriesResolution.FIVE_MINUTES
        assert result.pagination.total_count == 0
        assert result.pagination.has_more is False
        assert result.pagination.next_cursor is None

    def test_downsampled_pagination_follows_next_cursor(self, db: Session, user_setup: UserSetup) -> None:
        user, mapping, hr_type, _ = user_setup
        # Three hourly buckets
        for hour, value in [(8, 50), (9, 60), (10, 70)]:
            DataPointSeriesFactory(
                mapping=mapping,
                series_type=hr_type,
                recorded_at=datetime(2024, 1, 1, hour, 15, 0, tzinfo=timezone.utc),
                value=value,
            )

        page1 = timeseries_service.get_timeseries(
            db, user.id, [SeriesType.heart_rate], make_params(TimeseriesResolution.ONE_HOUR, limit=2)
        )

        assert len(page1.data) == 2
        assert page1.pagination.has_more is True
        assert page1.pagination.total_count == 3
        assert page1.pagination.next_cursor is not None

        page2 = timeseries_service.get_timeseries(
            db,
            user.id,
            [SeriesType.heart_rate],
            make_params(TimeseriesResolution.ONE_HOUR, limit=2, cursor=page1.pagination.next_cursor),
        )

        assert len(page2.data) == 1
        assert page2.data[0].timestamp == datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        assert page2.pagination.has_more is False
        # No overlap and no gap between pages
        assert page1.data[-1].timestamp < page2.data[0].timestamp
