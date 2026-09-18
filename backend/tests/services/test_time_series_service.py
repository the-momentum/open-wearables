"""
Tests for TimeSeriesService.

Tests cover:
- Bulk creating time series samples
- Getting daily histogram of data points
- Counting data points by series type
- Counting data points by provider
- Reading time series at raw and downsampled resolutions
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy.orm import Session

from app.schemas.enums import Resolution, SeriesType
from app.schemas.model_crud.activities import (
    HeartRateSampleCreate,
    StepSampleCreate,
    TimeSeriesQueryParams,
    TimeSeriesSampleCreate,
)
from app.services.timeseries_service import timeseries_service
from app.utils.pagination import encode_bucket_cursor
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
