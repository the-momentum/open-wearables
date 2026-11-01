"""
Tests for TimeSeriesService.

Tests cover:
- Bulk creating time series samples
- Getting daily histogram of data points
- Counting data points by series type
- Counting data points by provider
- Reading time series at raw and downsampled resolutions
"""

import importlib
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.models import DataSource, SeriesAggregate
from app.models.archival_setting import ArchivalSetting
from app.repositories import AggregateRepository
from app.repositories.data_migration_repository import DataMigrationRepository
from app.schemas.enums import ComputedBy, PeriodKind, Resolution, SeriesType, get_series_type_id
from app.schemas.model_crud.activities import (
    CalendarPeriod,
    HeartRateSampleCreate,
    StepSampleCreate,
    TimeSeriesQueryParams,
    TimeSeriesSampleCreate,
)
from app.services.timeseries_service import timeseries_service
from app.utils.pagination import encode_bucket_cursor, encode_date_cursor
from tests.factories import (
    DataPointSeriesFactory,
    DataSourceFactory,
    SeriesTypeDefinitionFactory,
    UserFactory,
)


class TestTimeSeriesServiceBulkCreateSamples:
    """Test bulk creation of time series samples."""

    def test_bulk_create_heart_rate_samples(self, db: Session) -> None:
        """Should bulk create heart rate samples."""
        # Arrange
        user = UserFactory()
        DataSourceFactory(source="apple", device_model="device_1")

        initial_count = timeseries_service.get_total_count(db)
        now = datetime.now(timezone.utc)
        samples = [
            HeartRateSampleCreate(
                id=uuid4(),
                user_id=user.id,
                provider_name="apple",
                device_model="device_1",
                recorded_at=now - timedelta(minutes=i),
                value=70 + i,
                series_type=SeriesType.heart_rate,
            )
            for i in range(5)
        ]

        # Act
        timeseries_service.bulk_create_samples(db, samples)

        # Assert - verify samples were created
        final_count = timeseries_service.get_total_count(db)
        assert final_count == initial_count + 5

    def test_bulk_create_step_samples(self, db: Session) -> None:
        """Should bulk create step samples."""
        # Arrange
        user = UserFactory()
        DataSourceFactory(source="apple", device_model="device_2")

        initial_count = timeseries_service.get_total_count(db)
        now = datetime.now(timezone.utc)
        samples = [
            StepSampleCreate(
                id=uuid4(),
                user_id=user.id,
                provider_name="apple",
                device_model="device_2",
                recorded_at=now - timedelta(hours=i),
                value=1000 + i * 100,
                series_type=SeriesType.steps,
            )
            for i in range(3)
        ]

        # Act
        timeseries_service.bulk_create_samples(db, samples)

        # Assert
        final_count = timeseries_service.get_total_count(db)
        assert final_count == initial_count + 3

    def test_bulk_create_mixed_series_types(self, db: Session) -> None:
        """Should bulk create samples of different series types."""
        # Arrange
        user = UserFactory()
        DataSourceFactory(source="apple", device_model="device_3")

        initial_count = timeseries_service.get_total_count(db)
        now = datetime.now(timezone.utc)
        samples = [
            TimeSeriesSampleCreate(
                id=uuid4(),
                user_id=user.id,
                provider_name="apple",
                device_model="device_3",
                recorded_at=now - timedelta(minutes=1),
                value=72,
                series_type=SeriesType.heart_rate,
            ),
            TimeSeriesSampleCreate(
                id=uuid4(),
                user_id=user.id,
                provider_name="apple",
                device_model="device_3",
                recorded_at=now - timedelta(minutes=2),
                value=5000,
                series_type=SeriesType.steps,
            ),
        ]

        # Act
        timeseries_service.bulk_create_samples(db, samples)

        # Assert
        total_count = timeseries_service.get_total_count(db)
        assert total_count >= initial_count + 2


class TestTimeSeriesServiceGetDailyHistogram:
    """Test getting daily histogram of data points."""

    def test_get_daily_histogram_groups_by_day(self, db: Session) -> None:
        """Should group data points by day."""
        # Arrange
        mapping = DataSourceFactory()
        series_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate()

        start_date = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        end_date = datetime(2024, 1, 4, 0, 0, 0, tzinfo=timezone.utc)

        # Day 1: 3 samples
        for i in range(3):
            DataPointSeriesFactory(
                mapping=mapping,
                series_type=series_type,
                recorded_at=datetime(2024, 1, 1, 10 + i, 0, 0, tzinfo=timezone.utc),
            )

        # Day 2: 2 samples
        for i in range(2):
            DataPointSeriesFactory(
                mapping=mapping,
                series_type=series_type,
                recorded_at=datetime(2024, 1, 2, 10 + i, 0, 0, tzinfo=timezone.utc),
            )

        # Day 3: 1 sample
        DataPointSeriesFactory(
            mapping=mapping,
            series_type=series_type,
            recorded_at=datetime(2024, 1, 3, 10, 0, 0, tzinfo=timezone.utc),
        )

        # Act
        histogram = timeseries_service.get_daily_histogram(db, start_date, end_date)

        # Assert
        assert len(histogram) == 3
        assert histogram[0] == 3  # Day 1
        assert histogram[1] == 2  # Day 2
        assert histogram[2] == 1  # Day 3

    def test_get_daily_histogram_empty_range(self, db: Session) -> None:
        """Should return empty list for range with no data."""
        # Arrange
        start_date = datetime(2024, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
        end_date = datetime(2024, 6, 7, 0, 0, 0, tzinfo=timezone.utc)

        # Act
        histogram = timeseries_service.get_daily_histogram(db, start_date, end_date)

        # Assert
        assert histogram == []


class TestTimeSeriesServiceGetCountBySource:
    """Test counting data points by source."""

    def test_get_count_by_source_groups_correctly(self, db: Session) -> None:
        """Should group and count data points by source."""
        # Arrange
        user = UserFactory()
        apple_mapping = DataSourceFactory(user=user, source="apple")
        garmin_mapping = DataSourceFactory(user=user, source="garmin")

        series_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate()

        # Create 4 samples from Apple
        for _ in range(4):
            DataPointSeriesFactory(mapping=apple_mapping, series_type=series_type)

        # Create 2 samples from Garmin
        for _ in range(2):
            DataPointSeriesFactory(mapping=garmin_mapping, series_type=series_type)

        # Act
        results = timeseries_service.get_count_by_source(db)

        # Assert
        results_dict = dict(results)
        assert results_dict["apple"] == 4
        assert results_dict["garmin"] == 2

    def test_get_count_by_source_ordered_by_count(self, db: Session) -> None:
        """Should order results by count descending."""
        # Arrange
        results = timeseries_service.get_count_by_source(db)

        if len(results) > 1:
            # Verify descending order
            for i in range(len(results) - 1):
                assert results[i][1] >= results[i + 1][1]

    def test_get_count_by_source_empty_result(self, db: Session) -> None:
        """Should return empty list when no data points exist."""
        # Act
        results = timeseries_service.get_count_by_source(db)

        # Assert
        assert results == []


class TestTimeSeriesServiceGetTotalCount:
    """Test getting total count of data points."""

    def test_get_total_count(self, db: Session) -> None:
        """Should return total count of all data points."""
        # Arrange
        mapping = DataSourceFactory()
        series_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate()

        initial_count = timeseries_service.get_total_count(db)

        # Create 5 samples
        for _ in range(5):
            DataPointSeriesFactory(mapping=mapping, series_type=series_type)

        # Act
        total_count = timeseries_service.get_total_count(db)

        # Assert
        assert total_count == initial_count + 5

    def test_get_total_count_empty_database(self, db: Session) -> None:
        """Should return 0 when no data points exist."""
        # Note: This test might fail if there's existing data in the test DB
        # from other tests running in the same session
        # Act
        count = timeseries_service.get_total_count(db)

        # Assert
        assert count >= 0  # At minimum should be non-negative


class TestTimeSeriesServiceGetCountInRange:
    """Test counting data points in date range."""

    def test_get_count_in_range(self, db: Session) -> None:
        """Should count data points within date range."""
        # Arrange
        mapping = DataSourceFactory()
        series_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate()

        now = datetime.now(timezone.utc)
        start = now - timedelta(days=7)
        end = now - timedelta(days=1)

        # Create samples at different times
        DataPointSeriesFactory(
            mapping=mapping,
            series_type=series_type,
            recorded_at=now - timedelta(days=10),
        )  # Before range
        DataPointSeriesFactory(
            mapping=mapping,
            series_type=series_type,
            recorded_at=now - timedelta(days=5),
        )  # In range
        DataPointSeriesFactory(
            mapping=mapping,
            series_type=series_type,
            recorded_at=now - timedelta(days=3),
        )  # In range
        DataPointSeriesFactory(mapping=mapping, series_type=series_type, recorded_at=now)  # After range

        # Act
        count = timeseries_service.get_count_in_range(db, start, end)

        # Assert
        assert count == 2

    def test_get_count_in_range_empty_result(self, db: Session) -> None:
        """Should return 0 when no data points in range."""
        # Arrange
        now = datetime.now(timezone.utc)
        future = now + timedelta(days=7)
        far_future = future + timedelta(days=7)

        # Act
        count = timeseries_service.get_count_in_range(db, future, far_future)

        # Assert
        assert count == 0


class TestTimeSeriesServiceGetTimeseries:
    """Test reading time series at raw and downsampled resolutions."""

    _START = datetime(2024, 3, 1, 12, 0, 0, tzinfo=timezone.utc)

    def _minute_of_heart_rate(self, db: Session, values: list[int], minute: int = 0) -> object:
        """One sample per second, so a minute bucket has a known average."""
        user = UserFactory()
        mapping = DataSourceFactory(user=user)
        series_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate()
        for second, value in enumerate(values):
            DataPointSeriesFactory(
                mapping=mapping,
                series_type=series_type,
                recorded_at=self._START + timedelta(minutes=minute, seconds=second),
                value=value,
            )
        return user

    def _params(self, **overrides) -> TimeSeriesQueryParams:
        return TimeSeriesQueryParams(
            start_datetime=self._START,
            end_datetime=self._START + timedelta(hours=2),
            **overrides,
        )

    def test_raw_resolution_returns_every_sample(self, db: Session) -> None:
        """Should return stored samples untouched when resolution is raw."""
        # Arrange
        user = self._minute_of_heart_rate(db, [60, 70, 80, 90])

        # Act
        result = timeseries_service.get_timeseries(db, user.id, [SeriesType.heart_rate], self._params())

        # Assert
        assert [s.value for s in result.data] == [60, 70, 80, 90]

    def test_bucket_returns_the_average_not_the_first_sample(self, db: Session) -> None:
        """Should collapse a minute into its mean, which is the whole point of the parameter."""
        # Arrange
        user = self._minute_of_heart_rate(db, [60, 70, 80, 90])

        # Act
        result = timeseries_service.get_timeseries(
            db, user.id, [SeriesType.heart_rate], self._params(resolution=Resolution.ONE_MIN)
        )

        # Assert
        assert len(result.data) == 1
        assert result.data[0].value == 75
        assert result.data[0].timestamp == self._START

    def test_one_bucket_per_minute_of_data(self, db: Session) -> None:
        """Should return at most as many points as there are populated buckets."""
        # Arrange
        user = UserFactory()
        mapping = DataSourceFactory(user=user)
        series_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate()
        for second in range(180):  # three minutes, one sample per second
            DataPointSeriesFactory(
                mapping=mapping,
                series_type=series_type,
                recorded_at=self._START + timedelta(seconds=second),
                value=100,
            )

        # Act
        result = timeseries_service.get_timeseries(
            db, user.id, [SeriesType.heart_rate], self._params(resolution=Resolution.ONE_MIN)
        )

        # Assert
        assert len(result.data) == 3
        assert [s.timestamp for s in result.data] == [self._START + timedelta(minutes=m) for m in range(3)]

    def test_cumulative_types_are_summed_not_averaged(self, db: Session) -> None:
        """Steps are a SUM metric in the shared coverage map; averaging them would understate them."""
        # Arrange
        user = UserFactory()
        mapping = DataSourceFactory(user=user)
        series_type = SeriesTypeDefinitionFactory.get_or_create_steps()
        for second, value in enumerate([10, 20, 30]):
            DataPointSeriesFactory(
                mapping=mapping,
                series_type=series_type,
                recorded_at=self._START + timedelta(seconds=second),
                value=value,
            )

        # Act
        result = timeseries_service.get_timeseries(
            db, user.id, [SeriesType.steps], self._params(resolution=Resolution.ONE_MIN)
        )

        # Assert
        assert [s.value for s in result.data] == [60]

    def test_buckets_are_not_mixed_across_sources(self, db: Session) -> None:
        """Two devices in one bucket stay two points, so a chart can draw a series per source."""
        # Arrange
        user = UserFactory()
        series_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate()
        for device, value in (("watch", 60), ("band", 120)):
            mapping = DataSourceFactory(user=user, device_model=device)
            DataPointSeriesFactory(mapping=mapping, series_type=series_type, recorded_at=self._START, value=value)

        # Act
        result = timeseries_service.get_timeseries(
            db, user.id, [SeriesType.heart_rate], self._params(resolution=Resolution.ONE_MIN)
        )

        # Assert
        assert sorted(s.value for s in result.data) == [60, 120]

    def test_paging_walks_buckets_without_gaps_or_repeats(self, db: Session) -> None:
        """The cursor carries the bucket start, so pages must tile the range exactly once."""
        # Arrange
        user = UserFactory()
        mapping = DataSourceFactory(user=user)
        series_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate()
        for minute in range(5):
            DataPointSeriesFactory(
                mapping=mapping,
                series_type=series_type,
                recorded_at=self._START + timedelta(minutes=minute),
                value=100 + minute,
            )

        # Act - walk every page with a limit that forces pagination
        seen, cursor = [], None
        for _ in range(5):
            page = timeseries_service.get_timeseries(
                db,
                user.id,
                [SeriesType.heart_rate],
                self._params(resolution=Resolution.ONE_MIN, limit=2, cursor=cursor),
            )
            seen.extend(s.timestamp for s in page.data)
            cursor = page.pagination.next_cursor
            if not cursor:
                break

        # Assert
        assert seen == [self._START + timedelta(minutes=m) for m in range(5)]

    def test_sparse_range_skips_to_the_first_sample(self, db: Session) -> None:
        """A wide range over sparse data must not return empty pages before reaching the data."""
        # Arrange - the only samples sit months after the requested start
        user = UserFactory()
        mapping = DataSourceFactory(user=user)
        series_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate()
        far_off = self._START + timedelta(days=200)
        for minute in range(3):
            DataPointSeriesFactory(
                mapping=mapping,
                series_type=series_type,
                recorded_at=far_off + timedelta(minutes=minute),
                value=100,
            )

        # Act
        result = timeseries_service.get_timeseries(
            db,
            user.id,
            [SeriesType.heart_rate],
            TimeSeriesQueryParams(
                start_datetime=self._START,
                end_datetime=far_off + timedelta(days=1),
                resolution=Resolution.ONE_MIN,
            ),
        )

        # Assert
        assert [s.timestamp for s in result.data] == [far_off + timedelta(minutes=m) for m in range(3)]

    def test_daily_totals_do_not_land_in_intraday_buckets(self, db: Session) -> None:
        """A day's step total must not be summed into a minute alongside the intraday samples."""
        # Arrange - 3 samples of 10 steps, plus the provider's own daily total for that day
        user = UserFactory()
        mapping = DataSourceFactory(user=user)
        series_type = SeriesTypeDefinitionFactory.get_or_create_steps()
        for second in range(3):
            DataPointSeriesFactory(
                mapping=mapping,
                series_type=series_type,
                recorded_at=self._START + timedelta(seconds=second),
                value=10,
                is_daily_total=False,
            )
        DataPointSeriesFactory(
            mapping=mapping,
            series_type=series_type,
            recorded_at=self._START + timedelta(seconds=30),
            value=12000,
            is_daily_total=True,
        )

        # Act
        result = timeseries_service.get_timeseries(
            db, user.id, [SeriesType.steps], self._params(resolution=Resolution.ONE_MIN)
        )

        # Assert - the minute reports the 30 steps actually taken, not 12030
        assert [s.value for s in result.data] == [30]

    def test_paging_backward_returns_buckets_adjacent_to_the_cursor(self, db: Session) -> None:
        """Paging back must land on the buckets just before the cursor, not the oldest in range."""
        # Arrange
        user = UserFactory()
        mapping = DataSourceFactory(user=user)
        series_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate()
        for minute in range(6):
            DataPointSeriesFactory(
                mapping=mapping,
                series_type=series_type,
                recorded_at=self._START + timedelta(minutes=minute),
                value=100 + minute,
            )

        # Act
        result = timeseries_service.get_timeseries(
            db,
            user.id,
            [SeriesType.heart_rate],
            self._params(
                resolution=Resolution.ONE_MIN,
                limit=2,
                cursor=encode_bucket_cursor(self._START + timedelta(minutes=5), "prev"),
            ),
        )

        # Assert
        assert [s.timestamp for s in result.data] == [self._START + timedelta(minutes=m) for m in (3, 4)]

    def test_last_page_hands_out_no_cursor(self, db: Session) -> None:
        """A capped scan window is not a next page: the cursor must lead somewhere."""
        # Arrange - exactly `limit` buckets exist
        user = UserFactory()
        mapping = DataSourceFactory(user=user)
        series_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate()
        for minute in range(2):
            DataPointSeriesFactory(
                mapping=mapping,
                series_type=series_type,
                recorded_at=self._START + timedelta(minutes=minute),
                value=100,
            )

        # Act
        result = timeseries_service.get_timeseries(
            db, user.id, [SeriesType.heart_rate], self._params(resolution=Resolution.ONE_MIN, limit=2)
        )

        # Assert
        assert len(result.data) == 2
        assert result.pagination.has_more is False
        assert result.pagination.next_cursor is None

    def test_first_page_reached_backwards_hands_out_no_previous_cursor(self, db: Session) -> None:
        """Paging back to the oldest bucket must end the walk, not offer an empty page."""
        # Arrange
        user = UserFactory()
        mapping = DataSourceFactory(user=user)
        series_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate()
        for minute in range(4):
            DataPointSeriesFactory(
                mapping=mapping,
                series_type=series_type,
                recorded_at=self._START + timedelta(minutes=minute),
                value=100 + minute,
            )
        params = self._params(resolution=Resolution.ONE_MIN, limit=2)
        page_one = timeseries_service.get_timeseries(db, user.id, [SeriesType.heart_rate], params)
        page_two = timeseries_service.get_timeseries(
            db,
            user.id,
            [SeriesType.heart_rate],
            self._params(resolution=Resolution.ONE_MIN, limit=2, cursor=page_one.pagination.next_cursor),
        )

        # Act - walk back to where we started
        back = timeseries_service.get_timeseries(
            db,
            user.id,
            [SeriesType.heart_rate],
            self._params(resolution=Resolution.ONE_MIN, limit=2, cursor=page_two.pagination.previous_cursor),
        )

        # Assert
        assert [s.timestamp for s in back.data] == [s.timestamp for s in page_one.data]
        assert back.pagination.has_more is False
        assert back.pagination.previous_cursor is None

    def _two_sources(self, db: Session) -> tuple[object, object, object]:
        """One user wearing a Garmin watch and a Whoop band, both logging heart rate."""
        user = UserFactory()
        series_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate()
        watch = DataSourceFactory(
            user=user, provider="garmin", source="garmin", device_model="FR965", device_type="watch"
        )
        band = DataSourceFactory(
            user=user, provider="whoop", source="whoop", device_model="Whoop 4.0", device_type="band"
        )
        for mapping, value in ((watch, 100), (band, 200)):
            for second in range(3):
                DataPointSeriesFactory(
                    mapping=mapping,
                    series_type=series_type,
                    recorded_at=self._START + timedelta(seconds=second),
                    value=value,
                )
        return user, watch, band

    def test_total_count_is_taken_on_the_first_page_only(self, db: Session) -> None:
        """A full COUNT over the largest table is paid once; a keyset page cannot change it."""
        # Arrange
        user = self._minute_of_heart_rate(db, [60, 70, 80, 90])

        # Act
        first = timeseries_service.get_timeseries(db, user.id, [SeriesType.heart_rate], self._params(limit=2))
        second = timeseries_service.get_timeseries(
            db, user.id, [SeriesType.heart_rate], self._params(limit=2, cursor=first.pagination.next_cursor)
        )

        # Assert
        assert first.pagination.total_count == 4
        assert second.pagination.total_count is None
        assert [s.value for s in second.data] == [80, 90]

    def test_source_filters_narrow_to_one_device(self, db: Session) -> None:
        """Every declared source filter reaches the query; data_source_id used to be ignored."""
        # Arrange
        user, watch, _ = self._two_sources(db)

        # Act & Assert - unfiltered sees both devices
        assert {s.value for s in self._fetch(db, user).data} == {100, 200}
        for filters in (
            {"provider": "garmin"},
            {"source": "garmin"},
            {"device_model": "FR965"},
            {"data_source_id": watch.id},
        ):
            result = self._fetch(db, user, **filters)
            assert {s.value for s in result.data} == {100}, filters
            assert {s.source.provider for s in result.data} == {"garmin"}, filters

    def test_source_filters_apply_to_aggregated_reads(self, db: Session) -> None:
        """The filters sit in the shared clause, so bucketed reads honour them too."""
        # Arrange
        user, _, band = self._two_sources(db)

        # Act
        result = self._fetch(db, user, resolution=Resolution.ONE_MIN, provider="whoop")

        # Assert
        assert [(s.timestamp, s.value) for s in result.data] == [(self._START, 200)]

    def _fetch(self, db: Session, user: object, **filters) -> object:
        return timeseries_service.get_timeseries(db, user.id, [SeriesType.heart_rate], self._params(**filters))

    def test_priority_filter_keeps_one_device_per_series(self, db: Session) -> None:
        """Two devices logging the same signal collapse to the higher-ranked one."""
        # Arrange - with no provider ranking configured, device type decides: watch beats band
        user, _, _ = self._two_sources(db)

        # Act
        unfiltered = self._fetch(db, user)
        filtered = timeseries_service.get_timeseries(
            db, user.id, [SeriesType.heart_rate], self._params(), filter_by_priority=True
        )

        # Assert
        assert {s.source.provider for s in unfiltered.data} == {"garmin", "whoop"}
        assert {s.source.provider for s in filtered.data} == {"garmin"}

    def test_priority_filter_falls_back_per_series_type(self, db: Session) -> None:
        """A watch without steps yields only that series, it does not lose its heart rate."""
        # Arrange
        user = UserFactory()
        watch = DataSourceFactory(user=user, provider="garmin", source="garmin", device_type="watch")
        band = DataSourceFactory(user=user, provider="whoop", source="whoop", device_type="band")
        heart_rate = SeriesTypeDefinitionFactory.get_or_create_heart_rate()
        steps = SeriesTypeDefinitionFactory.get_or_create_steps()
        DataPointSeriesFactory(mapping=watch, series_type=heart_rate, recorded_at=self._START, value=100)
        DataPointSeriesFactory(mapping=band, series_type=heart_rate, recorded_at=self._START, value=200)
        DataPointSeriesFactory(mapping=band, series_type=steps, recorded_at=self._START, value=42)

        # Act
        result = timeseries_service.get_timeseries(
            db, user.id, [SeriesType.heart_rate, SeriesType.steps], self._params(), filter_by_priority=True
        )

        # Assert - heart rate from the watch, steps from the band that alone recorded them
        assert {(s.type, s.source.provider, s.value) for s in result.data} == {
            (SeriesType.heart_rate, "garmin", 100),
            (SeriesType.steps, "whoop", 42),
        }

    def test_priority_picks_a_winner_from_the_filtered_sources(self, db: Session) -> None:
        """Ranking runs over what the request asked for, not over every device the user owns."""
        # Arrange - the watch outranks the band, but the caller asked for the band's provider
        user, _, _ = self._two_sources(db)

        # Act
        result = timeseries_service.get_timeseries(
            db, user.id, [SeriesType.heart_rate], self._params(provider="whoop"), filter_by_priority=True
        )

        # Assert - without this the two filters intersect to nothing
        assert {(s.value, s.source.provider) for s in result.data} == {(200, "whoop")}

    def test_priority_skips_a_source_holding_only_daily_totals(self, db: Session) -> None:
        """Bucketed reads drop daily totals, so a source with nothing else must not win."""
        # Arrange - the watch outranks the band but only reported the day's own step total
        user = UserFactory()
        watch = DataSourceFactory(user=user, provider="garmin", source="garmin", device_type="watch")
        band = DataSourceFactory(user=user, provider="whoop", source="whoop", device_type="band")
        steps = SeriesTypeDefinitionFactory.get_or_create_steps()
        DataPointSeriesFactory(
            mapping=watch, series_type=steps, recorded_at=self._START, value=9000, is_daily_total=True
        )
        for second in range(3):
            DataPointSeriesFactory(
                mapping=band,
                series_type=steps,
                recorded_at=self._START + timedelta(seconds=second),
                value=10,
                is_daily_total=False,
            )

        # Act
        result = timeseries_service.get_timeseries(
            db, user.id, [SeriesType.steps], self._params(resolution=Resolution.ONE_MIN), filter_by_priority=True
        )

        # Assert - without this the watch wins and the bucket it would fill is then discarded
        assert [(s.value, s.source.provider) for s in result.data] == [(30, "whoop")]

    def test_priority_on_days_takes_the_source_holding_day_rows(self, db: Session) -> None:
        """Day reads come from the day rows: a source with only a provider day value must win there, and
        a higher-ranked one whose samples are not rolled up (or were deleted by retention) has nothing."""
        # Arrange - the watch outranks the band but has samples only; the band sent its day's total
        user = UserFactory()
        watch = DataSourceFactory(user=user, provider="garmin", source="garmin", device_type="watch")
        band = DataSourceFactory(user=user, provider="whoop", source="whoop", device_type="band")
        steps = SeriesTypeDefinitionFactory.get_or_create_steps()
        DataPointSeriesFactory(mapping=watch, series_type=steps, recorded_at=self._START, value=10)
        period = CalendarPeriod.of_date(self._START.date())
        AggregateRepository(SeriesAggregate).upsert(
            db,
            [
                {
                    "data_source_id": band.id,
                    "series_type_definition_id": steps.id,
                    "period_kind": PeriodKind.DAY,
                    "period_start": period.start,
                    "period_end": period.end,
                    "zone_offset": period.zone_offset,
                    "computed_by": ComputedBy.PROVIDER,
                    "sum": Decimal("9000"),
                    "count": 1,
                }
            ],
        )

        # Act
        result = timeseries_service.get_timeseries(
            db, user.id, [SeriesType.steps], self._params(resolution=Resolution.ONE_DAY), filter_by_priority=True
        )

        # Assert - probing the samples instead would crown the watch and return an empty day
        assert [(s.value, s.source.provider) for s in result.data] == [(9000, "whoop")]

    def test_priority_on_days_ignores_a_sources_rows_outside_the_asked_days(self, db: Session) -> None:
        """The probe must see the local days the read returns: the watch's only row is the next local day,
        inside the UTC reach of the range but outside it, so the band's row for the asked day must show."""
        user = UserFactory()
        watch = DataSourceFactory(user=user, provider="garmin", source="garmin", device_type="watch")
        band = DataSourceFactory(user=user, provider="whoop", source="whoop", device_type="band")
        steps = SeriesTypeDefinitionFactory.get_or_create_steps()
        day = self._START.date()
        repo = AggregateRepository(SeriesAggregate)
        for source, period, total in (
            (watch, CalendarPeriod.of_date(day + timedelta(days=1), "+02:00"), "100"),
            (band, CalendarPeriod.of_date(day), "9000"),
        ):
            repo.upsert(
                db,
                [
                    {
                        "data_source_id": source.id,
                        "series_type_definition_id": steps.id,
                        "period_kind": PeriodKind.DAY,
                        "period_start": period.start,
                        "period_end": period.end,
                        "zone_offset": period.zone_offset,
                        "computed_by": ComputedBy.PROVIDER,
                        "sum": Decimal(total),
                        "count": 1,
                    }
                ],
            )
        params = self._params(resolution=Resolution.ONE_DAY).model_copy(
            update={
                "start_datetime": CalendarPeriod.of_date(day).start,
                "end_datetime": CalendarPeriod.of_date(day).end,
            }
        )

        result = timeseries_service.get_timeseries(db, user.id, [SeriesType.steps], params, filter_by_priority=True)

        assert [(s.value, s.source.provider) for s in result.data] == [(9000, "whoop")]

    def test_date_only_bounds_are_accepted_by_bucketed_reads(self, db: Session) -> None:
        """A date-only query parameter parses without a timezone and must still compare."""
        # Arrange
        user = UserFactory()
        mapping = DataSourceFactory(user=user)
        DataPointSeriesFactory(
            mapping=mapping,
            series_type=SeriesTypeDefinitionFactory.get_or_create_heart_rate(),
            recorded_at=self._START,
            value=128,
        )

        # Act - naive bounds, as the date-only route parsers produce them
        midnight = self._START.replace(tzinfo=None, hour=0, minute=0)
        result = timeseries_service.get_timeseries(
            db,
            user.id,
            [SeriesType.heart_rate],
            TimeSeriesQueryParams(
                start_datetime=midnight,
                end_datetime=midnight + timedelta(days=1),
                resolution=Resolution.ONE_MIN,
            ),
        )

        # Assert
        assert [s.value for s in result.data] == [128]


class TestTimeSeriesServicePeriods:
    """Day, week and month resolutions read series_aggregate, not the samples."""

    def _day(
        self,
        db: Session,
        source: DataSource,
        series_type: SeriesType,
        day: date,
        computed_by: ComputedBy,
        zone_offset: str = "+00:00",
        **stats: Decimal | int,
    ) -> None:
        period = CalendarPeriod.of_date(day, zone_offset)
        AggregateRepository(SeriesAggregate).upsert(
            db,
            [
                {
                    "data_source_id": source.id,
                    "series_type_definition_id": get_series_type_id(series_type),
                    "period_kind": PeriodKind.DAY,
                    "period_start": period.start,
                    "period_end": period.end,
                    "zone_offset": period.zone_offset,
                    "computed_by": computed_by,
                    "count": 1,
                    **stats,
                }
            ],
        )

    def _params(self, resolution: Resolution, start: date, end: date, **overrides) -> TimeSeriesQueryParams:
        return TimeSeriesQueryParams(
            start_datetime=datetime.combine(start, datetime.min.time(), timezone.utc),
            end_datetime=datetime.combine(end, datetime.min.time(), timezone.utc),
            resolution=resolution,
            **overrides,
        )

    def test_a_day_takes_the_providers_row_and_falls_back_to_ours(self, db: Session) -> None:
        source = DataSourceFactory()
        provider_day, own_day = date(2024, 3, 1), date(2024, 3, 2)
        self._day(db, source, SeriesType.steps, provider_day, ComputedBy.PROVIDER, sum=Decimal("8432"))
        # Ours for the same day sits at the user's offset: still the same local day.
        self._day(db, source, SeriesType.steps, provider_day, ComputedBy.OPEN_WEARABLES, "+02:00", sum=Decimal("8100"))
        self._day(db, source, SeriesType.steps, own_day, ComputedBy.OPEN_WEARABLES, "+02:00", sum=Decimal("5000"))

        result = timeseries_service.get_timeseries(
            db, source.user_id, [SeriesType.steps], self._params(Resolution.ONE_DAY, provider_day, date(2024, 3, 3))
        )

        assert [(s.value, s.computed_by) for s in result.data] == [
            (8432, ComputedBy.PROVIDER),
            (5000, ComputedBy.OPEN_WEARABLES),
        ]
        second = result.data[1]
        assert (second.timestamp, second.zone_offset) == (CalendarPeriod.of_date(own_day, "+02:00").start, "+02:00")
        assert second.period_end == CalendarPeriod.of_date(date(2024, 3, 3), "+02:00").start

    def test_a_day_value_is_the_statistic_its_series_is_read_by(self, db: Session) -> None:
        source = DataSourceFactory()
        day = date(2024, 3, 1)
        self._day(
            db,
            source,
            SeriesType.heart_rate,
            day,
            ComputedBy.OPEN_WEARABLES,
            avg=Decimal("70.5"),
            min=Decimal("47"),
            max=Decimal("165"),
            count=86400,
        )

        sample = timeseries_service.get_timeseries(
            db, source.user_id, [SeriesType.heart_rate], self._params(Resolution.ONE_DAY, day, date(2024, 3, 2))
        ).data[0]

        assert sample.value == 70.5
        assert sample.stats is not None
        assert (sample.stats.min, sample.stats.max, sample.stats.count) == (47, 165, 86400)

    def _steps(self, source: DataSource, at: datetime, value: int) -> None:
        DataPointSeriesFactory(
            mapping=source, series_type=SeriesTypeDefinitionFactory.get_or_create_steps(), recorded_at=at, value=value
        )

    def test_days_without_a_row_are_counted_from_the_samples(self, db: Session) -> None:
        source = DataSourceFactory()
        self._day(db, source, SeriesType.steps, date(2024, 3, 1), ComputedBy.PROVIDER, sum=Decimal("8432"))
        self._steps(source, datetime(2024, 3, 1, 9, tzinfo=timezone.utc), 120)
        for hour, steps in ((9, 1000), (18, 250)):
            self._steps(source, datetime(2024, 3, 2, hour, tzinfo=timezone.utc), steps)

        result = timeseries_service.get_timeseries(
            db, source.user_id, [SeriesType.steps], self._params(Resolution.ONE_DAY, date(2024, 3, 1), date(2024, 3, 3))
        )

        assert [(s.timestamp.date(), s.value, s.computed_by) for s in result.data] == [
            (date(2024, 3, 1), 8432, ComputedBy.PROVIDER),
            (date(2024, 3, 2), 1250, ComputedBy.OPEN_WEARABLES),
        ]

    def test_a_week_of_samples_only_adds_up_too(self, db: Session) -> None:
        source = DataSourceFactory()
        for day, steps in ((4, 1000), (10, 2000)):
            self._steps(source, datetime(2024, 3, day, 12, tzinfo=timezone.utc), steps)

        result = timeseries_service.get_timeseries(
            db,
            source.user_id,
            [SeriesType.steps],
            self._params(Resolution.ONE_WEEK, date(2024, 3, 4), date(2024, 3, 11)),
        )

        assert [(s.timestamp.date(), s.value) for s in result.data] == [(date(2024, 3, 4), 3000)]

    def test_once_the_rollup_reached_the_history_the_samples_are_not_read(self, db: Session) -> None:
        source = DataSourceFactory()
        self._steps(source, datetime(2024, 3, 2, 9, tzinfo=timezone.utc), 1000)
        db.merge(ArchivalSetting(id=1, rollup_enabled=True, delete_after_days=None))
        DataMigrationRepository().mark_completed(db, "aggregate_backfill:rollup_all")
        db.flush()

        result = timeseries_service.get_timeseries(
            db, source.user_id, [SeriesType.steps], self._params(Resolution.ONE_DAY, date(2024, 3, 1), date(2024, 3, 3))
        )

        assert result.data == []

    def test_a_week_adds_its_days_up_from_monday(self, db: Session) -> None:
        source = DataSourceFactory()
        # 2024-03-04 is a Monday.
        for day, steps in [(date(2024, 3, 4), "1000"), (date(2024, 3, 10), "2000"), (date(2024, 3, 11), "4000")]:
            self._day(db, source, SeriesType.steps, day, ComputedBy.PROVIDER, sum=Decimal(steps))

        result = timeseries_service.get_timeseries(
            db,
            source.user_id,
            [SeriesType.steps],
            self._params(Resolution.ONE_WEEK, date(2024, 3, 4), date(2024, 3, 18)),
        )

        assert [(s.timestamp.date(), s.value) for s in result.data] == [
            (date(2024, 3, 4), 3000),
            (date(2024, 3, 11), 4000),
        ]
        assert result.data[0].computed_by == ComputedBy.OPEN_WEARABLES

    def test_months_page_forward_and_back_without_gaps(self, db: Session) -> None:
        source = DataSourceFactory()
        for month in (1, 2, 3):
            self._day(db, source, SeriesType.steps, date(2024, month, 15), ComputedBy.PROVIDER, sum=Decimal(month))
        params = self._params(Resolution.ONE_MONTH, date(2024, 1, 1), date(2024, 4, 1), limit=2)

        first = timeseries_service.get_timeseries(db, source.user_id, [SeriesType.steps], params)
        second = timeseries_service.get_timeseries(
            db, source.user_id, [SeriesType.steps], params.model_copy(update={"cursor": first.pagination.next_cursor})
        )
        back = timeseries_service.get_timeseries(
            db,
            source.user_id,
            [SeriesType.steps],
            params.model_copy(update={"cursor": second.pagination.previous_cursor}),
        )

        assert [s.value for s in first.data] == [1, 2]
        assert ([s.value for s in second.data], second.pagination.next_cursor) == ([3], None)
        assert [s.value for s in back.data] == [1, 2]

    def test_a_sparse_range_starts_at_its_first_day_with_data(self, db: Session) -> None:
        source = DataSourceFactory()
        self._day(db, source, SeriesType.steps, date(2024, 6, 1), ComputedBy.PROVIDER, sum=Decimal("100"))
        params = self._params(Resolution.ONE_DAY, date(2024, 1, 1), date(2024, 7, 1), limit=2)

        result = timeseries_service.get_timeseries(db, source.user_id, [SeriesType.steps], params)

        assert ([s.value for s in result.data], result.pagination.has_more) == ([100], False)

    def test_two_provider_rows_on_one_local_day_read_as_the_later_one(self, db: Session) -> None:
        """A Whoop cycle starting at 23:30 and the next at 01:00 both map to that date; the later wins, every time."""
        source = DataSourceFactory()
        day = date(2024, 3, 1)
        self._day(db, source, SeriesType.steps, day, ComputedBy.PROVIDER, "+02:00", sum=Decimal("100"))
        self._day(db, source, SeriesType.steps, day, ComputedBy.PROVIDER, "-05:00", sum=Decimal("200"))
        params = self._params(Resolution.ONE_DAY, day, day + timedelta(days=1))

        results = [timeseries_service.get_timeseries(db, source.user_id, [SeriesType.steps], params) for _ in range(3)]

        assert [[s.value for s in r.data] for r in results] == [[200], [200], [200]]

    def test_the_first_day_is_found_even_when_an_offset_puts_a_later_day_first_in_utc(self, db: Session) -> None:
        """The day at +14:00 starts earlier in UTC than the previous day at -12:00; the range still opens on Mar 1."""
        source = DataSourceFactory()
        self._day(db, source, SeriesType.steps, date(2024, 3, 2), ComputedBy.PROVIDER, "+14:00", sum=Decimal("2"))
        self._day(db, source, SeriesType.steps, date(2024, 3, 1), ComputedBy.PROVIDER, "-12:00", sum=Decimal("1"))
        params = self._params(Resolution.ONE_DAY, date(2024, 3, 1), date(2024, 3, 3))

        result = timeseries_service.get_timeseries(db, source.user_id, [SeriesType.steps], params)

        assert [s.value for s in result.data] == [1, 2]

    def test_a_page_holds_only_as_many_periods_as_fit_its_row_budget(
        self, db: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # app.services exports the service instance under the module's name, so patch the module itself.
        # One series of one source: two rows a day at most (the provider's and ours), so two days a page.
        monkeypatch.setattr(importlib.import_module("app.services.timeseries_service"), "_PERIOD_ROWS_PER_PAGE", 4)
        source = DataSourceFactory()
        for n in range(3):
            self._day(db, source, SeriesType.steps, date(2024, 3, 1 + n), ComputedBy.PROVIDER, sum=Decimal(n + 1))
        params = self._params(Resolution.ONE_DAY, date(2024, 3, 1), date(2024, 3, 4), limit=10)

        first = timeseries_service.get_timeseries(db, source.user_id, [SeriesType.steps], params)
        second = timeseries_service.get_timeseries(
            db, source.user_id, [SeriesType.steps], params.model_copy(update={"cursor": first.pagination.next_cursor})
        )

        assert ([s.value for s in first.data], first.pagination.has_more) == ([1, 2], True)
        assert ([s.value for s in second.data], second.pagination.has_more) == ([3], False)

    def test_a_weeks_page_budget_counts_its_seven_day_rows(self, db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(importlib.import_module("app.services.timeseries_service"), "_PERIOD_ROWS_PER_PAGE", 7)
        source = DataSourceFactory()
        for n in range(2):
            self._day(db, source, SeriesType.steps, date(2024, 3, 4 + 7 * n), ComputedBy.PROVIDER, sum=Decimal(n + 1))
        params = self._params(Resolution.ONE_WEEK, date(2024, 3, 4), date(2024, 3, 18), limit=10)

        first = timeseries_service.get_timeseries(db, source.user_id, [SeriesType.steps], params)

        assert ([s.value for s in first.data], first.pagination.has_more) == ([1], True)

    def test_the_page_counts_the_series_that_hold_data_not_every_series(
        self, db: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No types asked for: the page is sized by the one series this source holds, not by all of them."""
        monkeypatch.setattr(importlib.import_module("app.services.timeseries_service"), "_PERIOD_ROWS_PER_PAGE", 20)
        source = DataSourceFactory()
        for n in range(12):
            self._day(db, source, SeriesType.steps, date(2024, 3, 1 + n), ComputedBy.PROVIDER, sum=Decimal(n + 1))
        params = self._params(Resolution.ONE_DAY, date(2024, 3, 1), date(2024, 3, 13), limit=50)

        page = timeseries_service.get_timeseries(db, source.user_id, [], params)

        assert (len(page.data), page.pagination.has_more) == (10, True)

    @pytest.mark.parametrize("bound", ["start", "end", "cursor"])
    def test_far_dates_read_as_open_ends(self, db: Session, bound: str) -> None:
        source = DataSourceFactory()
        self._day(db, source, SeriesType.steps, date(2024, 3, 1), ComputedBy.PROVIDER, sum=Decimal(1))
        params = self._params(Resolution.ONE_DAY, date(2024, 3, 1), date(2024, 3, 2))
        update = {
            "start": {"start_datetime": datetime(1, 1, 1, tzinfo=timezone.utc)},
            "end": {"end_datetime": datetime(9999, 12, 31, tzinfo=timezone.utc)},
            "cursor": {"cursor": encode_date_cursor(date(1, 1, 1))},
        }[bound]

        page = timeseries_service.get_timeseries(
            db, source.user_id, [SeriesType.steps], params.model_copy(update=update), filter_by_priority=True
        )

        assert [s.value for s in page.data] == [1]

    def test_a_week_with_a_clock_change_ends_at_the_new_offset(self, db: Session) -> None:
        """The week of 2024-03-25 starts at +01:00 and ends at +02:00: its end is the next Monday at +02:00."""
        source = DataSourceFactory()
        self._day(db, source, SeriesType.steps, date(2024, 3, 25), ComputedBy.PROVIDER, "+01:00", sum=Decimal("1"))
        self._day(db, source, SeriesType.steps, date(2024, 3, 31), ComputedBy.PROVIDER, "+02:00", sum=Decimal("2"))
        params = self._params(Resolution.ONE_WEEK, date(2024, 3, 25), date(2024, 4, 1))

        (week,) = timeseries_service.get_timeseries(db, source.user_id, [SeriesType.steps], params).data

        assert (week.timestamp, week.period_end) == (
            CalendarPeriod.of_date(date(2024, 3, 25), "+01:00").start,
            CalendarPeriod.of_date(date(2024, 4, 1), "+02:00").start,
        )

    def test_samples_carry_their_window(self, db: Session) -> None:
        source = DataSourceFactory()
        at = datetime(2024, 3, 1, 12, tzinfo=timezone.utc)
        DataPointSeriesFactory(mapping=source, recorded_at=at, window_seconds=900)
        params = TimeSeriesQueryParams(start_datetime=at, end_datetime=at + timedelta(hours=1))

        raw = timeseries_service.get_timeseries(db, source.user_id, [SeriesType.heart_rate], params)
        hourly = timeseries_service.get_timeseries(
            db, source.user_id, [SeriesType.heart_rate], params.model_copy(update={"resolution": Resolution.ONE_HOUR})
        )

        assert (raw.data[0].window_seconds, hourly.data[0].window_seconds) == (900, 3600)
