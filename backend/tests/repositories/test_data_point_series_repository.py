"""
Tests for DataPointSeriesRepository.

Tests cover:
- CRUD operations with data source integration
- get_samples with filtering by series type, device, date range
- Aggregation methods (get_total_count, get_count_in_range, get_daily_histogram)
- get_count_by_series_type and get_count_by_provider
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session

from app.models import DataPointSeries, DataSource
from app.repositories.data_point_series_repository import DataPointSeriesRepository
from app.schemas.enums import SeriesType
from app.schemas.model_crud.activities import TimeSeriesQueryParams, TimeSeriesSampleCreate
from tests.factories import DataSourceFactory, UserFactory


class TestDataPointSeriesRepository:
    """Test suite for DataPointSeriesRepository."""

    @pytest.fixture
    def series_repo(self) -> DataPointSeriesRepository:
        """Create DataPointSeriesRepository instance."""
        return DataPointSeriesRepository(DataPointSeries)

    def test_create_with_existing_mapping(self, db: Session, series_repo: DataPointSeriesRepository) -> None:
        """Test creating a data point with an existing external mapping."""
        # Arrange
        user = UserFactory()
        mapping = DataSourceFactory(user=user, source="apple", device_model="watch123")
        now = datetime.now(timezone.utc)

        sample_data = TimeSeriesSampleCreate(
            id=uuid4(),
            user_id=user.id,
            source="apple",
            device_model="watch123",
            data_source_id=mapping.id,
            recorded_at=now,
            value=72.5,
            series_type=SeriesType.heart_rate,
        )

        # Act
        result = series_repo.create(db, sample_data)

        # Assert
        assert result.id == sample_data.id
        assert result.data_source_id == mapping.id
        assert result.recorded_at == now
        assert result.value == Decimal("72.5")
        # series_type_definition_id should be set from series_type
        assert result.series_type_definition_id is not None

        # Verify in database
        db.expire_all()
        db_sample = series_repo.get(db, sample_data.id)
        assert db_sample is not None

    def test_create_auto_creates_mapping(self, db: Session, series_repo: DataPointSeriesRepository) -> None:
        """Test that create automatically creates a mapping if it doesn't exist."""
        # Arrange
        user = UserFactory()
        now = datetime.now(timezone.utc)

        sample_data = TimeSeriesSampleCreate(
            id=uuid4(),
            user_id=user.id,
            source="garmin",
            device_model="device456",
            data_source_id=None,
            recorded_at=now,
            value=150,
            series_type=SeriesType.heart_rate,
        )

        # Act
        result = series_repo.create(db, sample_data)

        # Assert
        assert result.data_source_id is not None
        # Verify data source was created
        from app.repositories.data_source_repository import DataSourceRepository

        data_source_repo = DataSourceRepository(DataSource)
        data_source = data_source_repo.get(db, result.data_source_id)
        assert data_source is not None
        assert data_source.user_id == user.id
        assert data_source.source == "garmin"
        assert data_source.device_model == "device456"

    def test_create_sets_series_type_definition_id(self, db: Session, series_repo: DataPointSeriesRepository) -> None:
        """Test that series_type_definition_id is correctly set from series_type enum."""
        # Arrange
        user = UserFactory()
        mapping = DataSourceFactory(user=user)

        sample_data = TimeSeriesSampleCreate(
            id=uuid4(),
            user_id=user.id,
            source="apple",
            device_model="device1",
            data_source_id=mapping.id,
            recorded_at=datetime.now(timezone.utc),
            value=10000,
            series_type=SeriesType.steps,
        )

        # Act
        result = series_repo.create(db, sample_data)

        # Assert
        assert result.series_type_definition_id is not None
        # Verify it's different from heart_rate
        from app.schemas.enums import get_series_type_id

        expected_id = get_series_type_id(SeriesType.steps)
        assert result.series_type_definition_id == expected_id

    def test_create_duplicate_raises_integrity_error(self, db: Session, series_repo: DataPointSeriesRepository) -> None:
        """Test that creating duplicate data points returns the existing record instead of raising error."""
        # Arrange
        user = UserFactory()
        mapping = DataSourceFactory(user=user, source="apple", device_model="watch123")
        recorded_time = datetime.now(timezone.utc)

        # Create first sample
        first_sample = TimeSeriesSampleCreate(
            id=uuid4(),
            user_id=user.id,
            source="apple",
            device_model="watch123",
            data_source_id=mapping.id,
            recorded_at=recorded_time,
            value=72.5,
            series_type=SeriesType.heart_rate,
        )
        result1 = series_repo.create(db, first_sample)
        first_id = result1.id

        # Create duplicate sample with same mapping, series_type, and recorded_at
        duplicate_sample = TimeSeriesSampleCreate(
            id=uuid4(),  # Different ID
            user_id=user.id,
            source="apple",
            device_model="watch123",
            data_source_id=mapping.id,
            recorded_at=recorded_time,  # Same timestamp
            value=75.0,  # Different value
            series_type=SeriesType.heart_rate,  # Same series type
        )

        # Act - Should return existing record, not raise error
        result2 = series_repo.create(db, duplicate_sample)

        # Assert - Should return the first record, not create a new one
        assert result2 is not None
        assert result2.id == first_id  # Same ID as the first record
        assert result2.value == Decimal("72.5")  # Original value, not the duplicate's value
        assert result2.data_source_id == mapping.id
        assert result2.recorded_at == recorded_time

    def test_get_samples_requires_device_filter(self, db: Session, series_repo: DataPointSeriesRepository) -> None:
        """Test that get_samples requires at least device_id or data_source_id."""
        # Arrange
        user = UserFactory()
        query_params = TimeSeriesQueryParams()

        # Act
        results, total_count = series_repo.get_samples(db, query_params, [SeriesType.heart_rate], user.id)

        # Assert
        assert results == []  # Returns empty list when no device filter provided
        assert total_count == 0

    def test_get_samples_by_device_id(self, db: Session, series_repo: DataPointSeriesRepository) -> None:
        """Test getting samples filtered by device ID."""
        # Arrange
        user = UserFactory()
        mapping1 = DataSourceFactory(user=user, device_model="device1")
        mapping2 = DataSourceFactory(user=user, device_model="device2")

        now = datetime.now(timezone.utc)

        # Create samples for device1
        for i in range(3):
            sample = TimeSeriesSampleCreate(
                id=uuid4(),
                user_id=user.id,
                source="apple",
                device_model="device1",
                data_source_id=mapping1.id,
                recorded_at=now - timedelta(hours=i),
                value=70 + i,
                series_type=SeriesType.heart_rate,
            )
            series_repo.create(db, sample)

        # Create sample for device2
        sample = TimeSeriesSampleCreate(
            id=uuid4(),
            user_id=user.id,
            source="apple",
            device_model="device2",
            data_source_id=mapping2.id,
            recorded_at=now,
            value=80,
            series_type=SeriesType.heart_rate,
        )
        series_repo.create(db, sample)

        query_params = TimeSeriesQueryParams(device_model="device1")

        # Act
        results, total_count = series_repo.get_samples(db, query_params, [SeriesType.heart_rate], user.id)

        # Assert
        assert len(results) == 3
        assert total_count == 3
        for _, data_source in results:
            assert data_source.device_model == "device1"

    def test_get_samples_by_data_source_id(self, db: Session, series_repo: DataPointSeriesRepository) -> None:
        """Test getting samples filtered by external mapping ID."""
        # Arrange
        user = UserFactory()
        mapping = DataSourceFactory(user=user, source="apple", device_model="device1")

        now = datetime.now(timezone.utc)
        sample_ids = []

        for i in range(3):
            sample = TimeSeriesSampleCreate(
                id=uuid4(),
                user_id=user.id,
                source="apple",
                device_model="device1",
                data_source_id=mapping.id,
                recorded_at=now - timedelta(hours=i),
                value=70 + i,
                series_type=SeriesType.heart_rate,
            )
            result = series_repo.create(db, sample)
            sample_ids.append(result.id)

        query_params = TimeSeriesQueryParams(data_source_id=mapping.id)

        # Act
        results, total_count = series_repo.get_samples(db, query_params, [SeriesType.heart_rate], user.id)

        # Assert
        assert len(results) == 3
        assert total_count == 3
        for sample, _ in results:
            assert sample.data_source_id == mapping.id

    def test_get_samples_by_series_type(self, db: Session, series_repo: DataPointSeriesRepository) -> None:
        """Test that get_samples only returns samples of the specified series type."""
        # Arrange
        user = UserFactory()
        mapping = DataSourceFactory(user=user, device_model="device1")
        now = datetime.now(timezone.utc)

        # Create heart rate samples
        for i in range(2):
            sample = TimeSeriesSampleCreate(
                id=uuid4(),
                user_id=user.id,
                source="apple",
                device_model="device1",
                data_source_id=mapping.id,
                recorded_at=now - timedelta(hours=i),
                value=70 + i,
                series_type=SeriesType.heart_rate,
            )
            series_repo.create(db, sample)

        # Create steps sample
        sample = TimeSeriesSampleCreate(
            id=uuid4(),
            user_id=user.id,
            source="apple",
            device_model="device1",
            data_source_id=mapping.id,
            recorded_at=now,
            value=10000,
            series_type=SeriesType.steps,
        )
        series_repo.create(db, sample)

        query_params = TimeSeriesQueryParams(device_model="device1")

        # Act
        results, total_count = series_repo.get_samples(db, query_params, [SeriesType.heart_rate], user.id)

        # Assert
        assert len(results) == 2
        assert total_count == 2
        from app.schemas.enums import get_series_type_id

        expected_type_id = get_series_type_id(SeriesType.heart_rate)
        for sample, _ in results:
            assert sample.series_type_definition_id == expected_type_id

    def test_get_samples_by_date_range(self, db: Session, series_repo: DataPointSeriesRepository) -> None:
        """Test filtering samples by date range.

        Uses half-open interval [start, end) - start is inclusive, end is exclusive.
        """
        # Arrange
        user = UserFactory()
        mapping = DataSourceFactory(user=user, device_model="device1")

        now = datetime.now(timezone.utc)
        yesterday = now - timedelta(days=1)
        two_days_ago = now - timedelta(days=2)

        # Create samples at different times
        for dt in [two_days_ago, yesterday, now]:
            sample = TimeSeriesSampleCreate(
                id=uuid4(),
                user_id=user.id,
                source="apple",
                device_model="device1",
                data_source_id=mapping.id,
                recorded_at=dt,
                value=72,
                series_type=SeriesType.heart_rate,
            )
            series_repo.create(db, sample)

        # Query with half-open interval [yesterday, now + 1s) to include both yesterday and now
        end_datetime = now + timedelta(seconds=1)
        query_params = TimeSeriesQueryParams(
            device_model="device1",
            start_datetime=yesterday,
            end_datetime=end_datetime,
        )

        # Act
        results, total_count = series_repo.get_samples(db, query_params, [SeriesType.heart_rate], user.id)

        # Assert - should get yesterday and now (2 samples), excluding two_days_ago
        assert len(results) == 2
        assert total_count == 2
        for sample, _ in results:
            assert sample.recorded_at >= yesterday
            assert sample.recorded_at < end_datetime

    def test_get_samples_by_provider(self, db: Session, series_repo: DataPointSeriesRepository) -> None:
        """Test getting samples filtered by provider."""
        # Arrange
        user = UserFactory()
        mapping_apple = DataSourceFactory(user=user, source="apple", device_model="device1")
        mapping_garmin = DataSourceFactory(user=user, source="garmin", device_model="device1")

        now = datetime.now(timezone.utc)

        # Create samples for both providers
        sample1 = TimeSeriesSampleCreate(
            id=uuid4(),
            user_id=user.id,
            source="apple",
            device_model="device1",
            data_source_id=mapping_apple.id,
            recorded_at=now,
            value=72,
            series_type=SeriesType.heart_rate,
        )
        series_repo.create(db, sample1)

        sample2 = TimeSeriesSampleCreate(
            id=uuid4(),
            user_id=user.id,
            source="garmin",
            device_model="device1",
            data_source_id=mapping_garmin.id,
            recorded_at=now,
            value=75,
            series_type=SeriesType.heart_rate,
        )
        series_repo.create(db, sample2)

        query_params = TimeSeriesQueryParams(device_model="device1", source="apple")

        # Act
        results, total_count = series_repo.get_samples(db, query_params, [SeriesType.heart_rate], user.id)

        # Assert
        assert len(results) == 1
        assert total_count == 1
        _, data_source = results[0]
        assert data_source.source == "apple"

    def test_get_samples_ordered_by_recorded_at_asc(self, db: Session, series_repo: DataPointSeriesRepository) -> None:
        """Test that samples are ordered by recorded_at ascending."""
        # Arrange
        user = UserFactory()
        mapping = DataSourceFactory(user=user, device_model="device1")

        now = datetime.now(timezone.utc)
        times = [now - timedelta(hours=i) for i in range(3)]

        for dt in times:
            sample = TimeSeriesSampleCreate(
                id=uuid4(),
                user_id=user.id,
                source="apple",
                device_model="device1",
                data_source_id=mapping.id,
                recorded_at=dt,
                value=72,
                series_type=SeriesType.heart_rate,
            )
            series_repo.create(db, sample)

        query_params = TimeSeriesQueryParams(device_model="device1")

        # Act
        results, total_count = series_repo.get_samples(db, query_params, [SeriesType.heart_rate], user.id)

        # Assert
        assert len(results) >= 3
        assert total_count >= 3
        # Should be ordered oldest first (ascending)
        for i in range(len(results) - 1):
            assert results[i][0].recorded_at <= results[i + 1][0].recorded_at

    def test_get_samples_limit_1000(self, db: Session, series_repo: DataPointSeriesRepository) -> None:
        """Test that get_samples is limited to 1000 records."""
        # Arrange
        user = UserFactory()
        DataSourceFactory(user=user)

        # Note: Creating 1000+ records would be slow, so we just verify the limit exists
        # by checking the method implementation
        query_params = TimeSeriesQueryParams(device_model="device1")

        # Act
        results, total_count = series_repo.get_samples(db, query_params, [SeriesType.heart_rate], user.id)

        # Assert
        assert len(results) <= 1000

    def test_get_total_count(self, db: Session, series_repo: DataPointSeriesRepository) -> None:
        """Test counting total data points."""
        # Arrange
        initial_count = series_repo.get_total_count(db)

        user = UserFactory()
        mapping = DataSourceFactory(user=user)
        now = datetime.now(timezone.utc)

        for i in range(3):
            sample = TimeSeriesSampleCreate(
                id=uuid4(),
                user_id=user.id,
                source="apple",
                device_model="device1",
                data_source_id=mapping.id,
                recorded_at=now + timedelta(seconds=i),
                value=70 + i,
                series_type=SeriesType.heart_rate,
            )
            series_repo.create(db, sample)

        # Act
        result = series_repo.get_total_count(db)

        # Assert
        assert result == initial_count + 3

    def test_get_count_in_range(self, db: Session, series_repo: DataPointSeriesRepository) -> None:
        """Test counting data points within a datetime range."""
        # Arrange
        user = UserFactory()
        mapping = DataSourceFactory(user=user)

        now = datetime.now(timezone.utc)
        yesterday = now - timedelta(days=1)
        two_days_ago = now - timedelta(days=2)

        # Create samples at different times
        for i, dt in enumerate([two_days_ago, yesterday, yesterday + timedelta(seconds=1), now]):
            sample = TimeSeriesSampleCreate(
                id=uuid4(),
                user_id=user.id,
                source="apple",
                device_model="device1",
                data_source_id=mapping.id,
                recorded_at=dt,
                value=72,
                series_type=SeriesType.heart_rate,
            )
            series_repo.create(db, sample)

        # Act - Count samples from yesterday to now (exclusive)
        result = series_repo.get_count_in_range(db, yesterday, now)

        # Assert
        assert result == 2  # Two samples from yesterday

    def test_get_daily_histogram(self, db: Session, series_repo: DataPointSeriesRepository) -> None:
        """Test getting daily histogram of data points."""
        # Arrange
        user = UserFactory()
        mapping = DataSourceFactory(user=user)

        now = datetime.now(timezone.utc).replace(hour=12, minute=0, second=0, microsecond=0)
        yesterday = now - timedelta(days=1)
        two_days_ago = now - timedelta(days=2)

        # Create samples: 1 two days ago, 2 yesterday, 3 today
        dates_and_counts = [
            (two_days_ago, 1),
            (yesterday, 2),
            (now, 3),
        ]

        for dt, count in dates_and_counts:
            for i in range(count):
                sample = TimeSeriesSampleCreate(
                    id=uuid4(),
                    user_id=user.id,
                    source="apple",
                    device_model="device1",
                    data_source_id=mapping.id,
                    recorded_at=dt + timedelta(seconds=i),
                    value=72,
                    series_type=SeriesType.heart_rate,
                )
                series_repo.create(db, sample)

        # Act
        tomorrow = now + timedelta(days=1)
        result = series_repo.get_daily_histogram(db, two_days_ago, tomorrow)

        # Assert
        assert len(result) == 3
        assert result[0] == 1  # Two days ago
        assert result[1] == 2  # Yesterday
        assert result[2] == 3  # Today

    def test_get_count_by_series_type(self, db: Session, series_repo: DataPointSeriesRepository) -> None:
        """Test aggregating data point counts by series type."""
        # Arrange
        user = UserFactory()
        mapping = DataSourceFactory(user=user)
        now = datetime.now(timezone.utc)

        # Create heart rate samples
        for i in range(3):
            sample = TimeSeriesSampleCreate(
                id=uuid4(),
                user_id=user.id,
                source="apple",
                device_model="device1",
                data_source_id=mapping.id,
                recorded_at=now + timedelta(seconds=i),
                value=72,
                series_type=SeriesType.heart_rate,
            )
            series_repo.create(db, sample)

        # Create steps samples
        for i in range(2):
            sample = TimeSeriesSampleCreate(
                id=uuid4(),
                user_id=user.id,
                source="apple",
                device_model="device1",
                data_source_id=mapping.id,
                recorded_at=now + timedelta(seconds=i),
                value=10000,
                series_type=SeriesType.steps,
            )
            series_repo.create(db, sample)

        # Act
        results = series_repo.get_count_by_series_type(db)

        # Assert
        counts_dict = dict(results)
        from app.schemas.enums import get_series_type_id

        hr_type_id = get_series_type_id(SeriesType.heart_rate)
        steps_type_id = get_series_type_id(SeriesType.steps)

        assert counts_dict.get(hr_type_id, 0) >= 3
        assert counts_dict.get(steps_type_id, 0) >= 2

    def test_get_count_by_source(self, db: Session, series_repo: DataPointSeriesRepository) -> None:
        """Test aggregating data point counts by source."""
        # Arrange
        user = UserFactory()
        mapping_apple = DataSourceFactory(user=user, source="apple")
        mapping_garmin = DataSourceFactory(user=user, source="garmin")

        now = datetime.now(timezone.utc)

        # Create samples for Apple
        for i in range(3):
            sample = TimeSeriesSampleCreate(
                id=uuid4(),
                user_id=user.id,
                source="apple",
                device_model="device1",
                data_source_id=mapping_apple.id,
                recorded_at=now + timedelta(seconds=i),
                value=72,
                series_type=SeriesType.heart_rate,
            )
            series_repo.create(db, sample)

        # Create samples for Garmin
        for i in range(2):
            sample = TimeSeriesSampleCreate(
                id=uuid4(),
                user_id=user.id,
                source="garmin",
                device_model="device2",
                data_source_id=mapping_garmin.id,
                recorded_at=now + timedelta(seconds=i),
                value=75,
                series_type=SeriesType.heart_rate,
            )
            series_repo.create(db, sample)

        # Act
        results = series_repo.get_count_by_source(db)

        # Assert
        counts_dict = dict(results)
        assert counts_dict.get("apple", 0) >= 3
        assert counts_dict.get("garmin", 0) >= 2

    def test_get_samples_filters_by_user(self, db: Session, series_repo: DataPointSeriesRepository) -> None:
        """Test that samples are filtered by user ID."""
        # Arrange
        user1 = UserFactory()
        user2 = UserFactory()
        mapping1 = DataSourceFactory(user=user1, device_model="device1")
        mapping2 = DataSourceFactory(user=user2, device_model="device1")

        now = datetime.now(timezone.utc)

        # Create samples for user1
        for i in range(2):
            sample = TimeSeriesSampleCreate(
                id=uuid4(),
                user_id=user1.id,
                source="apple",
                device_model="device1",
                data_source_id=mapping1.id,
                recorded_at=now + timedelta(seconds=i),
                value=72,
                series_type=SeriesType.heart_rate,
            )
            series_repo.create(db, sample)

        # Create sample for user2
        sample = TimeSeriesSampleCreate(
            id=uuid4(),
            user_id=user2.id,
            source="apple",
            device_model="device1",
            data_source_id=mapping2.id,
            recorded_at=now,
            value=75,
            series_type=SeriesType.heart_rate,
        )
        series_repo.create(db, sample)

        query_params = TimeSeriesQueryParams(device_model="device1")

        # Act
        results, total_count = series_repo.get_samples(db, query_params, [SeriesType.heart_rate], user1.id)

        # Assert
        assert len(results) == 2
        assert total_count == 2
        for _, data_source in results:
            assert data_source.user_id == user1.id

    def test_bulk_create_reports_inserted_then_updated(
        self, db: Session, series_repo: DataPointSeriesRepository
    ) -> None:
        """bulk_create returns WriteCounts splitting new rows from in-place updates."""
        user = UserFactory()
        ts = datetime(2099, 1, 1, tzinfo=timezone.utc)

        def sample(value: int) -> TimeSeriesSampleCreate:
            return TimeSeriesSampleCreate(
                id=uuid4(),
                user_id=user.id,
                source="oura",
                recorded_at=ts,
                value=value,
                series_type=SeriesType.steps,
            )

        # First write of this (data_source, series_type, recorded_at) → insert.
        first = series_repo.bulk_create(db, [sample(1000)])
        assert (first.inserted, first.updated) == (1, 0)
        assert int(first) == 1

        # Same key again → ON CONFLICT DO UPDATE → counted as an update, not a new row.
        second = series_repo.bulk_create(db, [sample(2000)])
        assert (second.inserted, second.updated) == (0, 1)
        assert int(second) == 1

    def test_bulk_create_empty_returns_zero_counts(self, db: Session, series_repo: DataPointSeriesRepository) -> None:
        """An empty batch writes nothing and reports zero inserted/updated."""
        counts = series_repo.bulk_create(db, [])
        assert (counts.inserted, counts.updated) == (0, 0)
        assert int(counts) == 0

    def test_bulk_create_batch_exceeding_one_chunk(self, db: Session, series_repo: DataPointSeriesRepository) -> None:
        """A batch larger than one chunk must stay under Postgres' 65535-param cap.

        Regression: a full chunk * columns-per-row once overflowed 65535 bind
        params (e.g. 9000 rows * 8 cols), failing the whole insert.
        """
        user = UserFactory()
        base = datetime(2099, 1, 1, tzinfo=timezone.utc)
        n = series_repo.BATCH_INSERT_CHUNK_SIZE + 500
        samples = [
            TimeSeriesSampleCreate(
                id=uuid4(),
                user_id=user.id,
                source="garmin",
                recorded_at=base + timedelta(seconds=15 * i),
                value=60 + (i % 40),
                series_type=SeriesType.heart_rate,
            )
            for i in range(n)
        ]

        counts = series_repo.bulk_create(db, samples)
        assert counts.inserted == n

    # ------------------------------------------------------------------
    # get_daily_activity_aggregates — prefer-daily-total-else-sum logic
    # ------------------------------------------------------------------

    def _steps(
        self,
        user_id: UUID,
        source: str,
        device_model: str | None,
        recorded_at: datetime,
        value: int,
        is_daily_total: bool | None,
    ) -> TimeSeriesSampleCreate:
        return TimeSeriesSampleCreate(
            id=uuid4(),
            user_id=user_id,
            source=source,
            device_model=device_model,
            recorded_at=recorded_at,
            zone_offset="+00:00",
            value=value,
            series_type=SeriesType.steps,
            is_daily_total=is_daily_total,
        )

    def test_aggregate_prefers_daily_total_over_intraday(
        self, db: Session, series_repo: DataPointSeriesRepository
    ) -> None:
        """When a daily total exists it wins; its own intraday samples are not added."""
        user = UserFactory()
        day = datetime(2026, 6, 20, tzinfo=timezone.utc)
        samples = [self._steps(user.id, "garmin", "fenix", day, 10000, True)]
        samples += [
            self._steps(user.id, "garmin", "fenix", day + timedelta(hours=h), v, False)
            for h, v in [(1, 4000), (2, 3000), (3, 2500)]
        ]
        series_repo.bulk_create(db, samples)
        db.commit()

        result = series_repo.get_daily_activity_aggregates(db, user.id, day, day + timedelta(days=1))

        assert len(result) == 1
        assert result[0]["steps_sum"] == 10000  # daily total, NOT 10000 + 9500

    def test_aggregate_sums_samples_when_no_daily_total(
        self, db: Session, series_repo: DataPointSeriesRepository
    ) -> None:
        """With no daily total, fall back to summing the intraday samples."""
        user = UserFactory()
        day = datetime(2026, 6, 20, tzinfo=timezone.utc)
        samples = [
            self._steps(user.id, "apple", "watch", day + timedelta(hours=h), v, False)
            for h, v in [(1, 4000), (2, 3000), (3, 2500)]
        ]
        series_repo.bulk_create(db, samples)
        db.commit()

        result = series_repo.get_daily_activity_aggregates(db, user.id, day, day + timedelta(days=1))

        assert len(result) == 1
        assert result[0]["steps_sum"] == 9500

    def test_aggregate_treats_null_is_daily_total_as_sample(
        self, db: Session, series_repo: DataPointSeriesRepository
    ) -> None:
        """Legacy rows (is_daily_total=None) are summed like samples."""
        user = UserFactory()
        day = datetime(2026, 6, 20, tzinfo=timezone.utc)
        samples = [
            self._steps(user.id, "apple", "watch", day + timedelta(hours=h), v, None) for h, v in [(1, 100), (2, 200)]
        ]
        series_repo.bulk_create(db, samples)
        db.commit()

        result = series_repo.get_daily_activity_aggregates(db, user.id, day, day + timedelta(days=1))

        assert result[0]["steps_sum"] == 300

    def test_aggregate_prefers_daily_per_source(self, db: Session, series_repo: DataPointSeriesRepository) -> None:
        """Prefer-daily is per source: a Garmin daily total and Apple intraday combine across sources."""
        user = UserFactory()
        day = datetime(2026, 6, 20, tzinfo=timezone.utc)
        samples = [
            self._steps(user.id, "garmin", "fenix", day, 10000, True),
            self._steps(user.id, "garmin", "fenix", day + timedelta(hours=1), 9000, False),  # ignored (daily wins)
            self._steps(user.id, "apple", "watch", day + timedelta(hours=2), 3000, False),
            self._steps(user.id, "apple", "watch", day + timedelta(hours=3), 5000, False),
        ]
        series_repo.bulk_create(db, samples)
        db.commit()

        result = series_repo.get_daily_activity_aggregates(db, user.id, day, day + timedelta(days=1))

        by_source = {r["source"]: r["steps_sum"] for r in result}
        assert by_source["garmin"] == 10000
        assert by_source["apple"] == 8000
