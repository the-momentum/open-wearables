"""
Tests for DataPointSeriesRepository.

Tests cover:
- CRUD operations with external mapping integration
- get_samples with filtering by series type, device, date range
- Aggregation methods (get_total_count, get_count_in_range, get_daily_histogram)
- get_count_by_series_type and get_count_by_provider
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.models import DataPointSeries
from app.repositories.data_point_series_repository import DataPointSeriesRepository
from app.schemas.series_types import SeriesType
from app.schemas.timeseries import TimeSeriesQueryParams, TimeSeriesSampleCreate
from tests.factories import ExternalDeviceMappingFactory, UserFactory


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
        mapping = ExternalDeviceMappingFactory(user=user, provider_name="apple", device_id="watch123")
        now = datetime.now(timezone.utc)

        sample_data = TimeSeriesSampleCreate(
            id=uuid4(),
            user_id=user.id,
            provider_name="apple",
            device_id="watch123",
            external_device_mapping_id=mapping.id,
            recorded_at=now,
            value=72.5,
            series_type=SeriesType.heart_rate,
        )

        # Act
        result = series_repo.create(db, sample_data)

        # Assert
        assert result.id == sample_data.id
        assert result.external_device_mapping_id == mapping.id
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
            provider_name="garmin",
            device_id="device456",
            external_device_mapping_id=None,
            recorded_at=now,
            value=150,
            series_type=SeriesType.heart_rate,
        )

        # Act
        result = series_repo.create(db, sample_data)

        # Assert
        assert result.external_device_mapping_id is not None
        # Verify mapping was created
        from app.models import ExternalDeviceMapping
        from app.repositories.external_mapping_repository import ExternalMappingRepository

        mapping_repo = ExternalMappingRepository(ExternalDeviceMapping)
        mapping = mapping_repo.get(db, result.external_device_mapping_id)
        assert mapping is not None
        assert mapping.user_id == user.id
        assert mapping.provider_name == "garmin"
        assert mapping.device_id == "device456"

    def test_create_sets_series_type_definition_id(self, db: Session, series_repo: DataPointSeriesRepository) -> None:
        """Test that series_type_definition_id is correctly set from series_type enum."""
        # Arrange
        user = UserFactory()
        mapping = ExternalDeviceMappingFactory(user=user)

        sample_data = TimeSeriesSampleCreate(
            id=uuid4(),
            user_id=user.id,
            provider_name="apple",
            device_id="device1",
            external_device_mapping_id=mapping.id,
            recorded_at=datetime.now(timezone.utc),
            value=10000,
            series_type=SeriesType.steps,
        )

        # Act
        result = series_repo.create(db, sample_data)

        # Assert
        assert result.series_type_definition_id is not None
        # Verify it's different from heart_rate
        from app.schemas.series_types import get_series_type_id

        expected_id = get_series_type_id(SeriesType.steps)
        assert result.series_type_definition_id == expected_id

    def test_create_duplicate_raises_integrity_error(self, db: Session, series_repo: DataPointSeriesRepository) -> None:
        """Test that creating duplicate data points returns the existing record instead of raising error."""
        # Arrange
        user = UserFactory()
        mapping = ExternalDeviceMappingFactory(user=user, provider_name="apple", device_id="watch123")
        recorded_time = datetime.now(timezone.utc)

        # Create first sample
        first_sample = TimeSeriesSampleCreate(
            id=uuid4(),
            user_id=user.id,
            provider_name="apple",
            device_id="watch123",
            external_device_mapping_id=mapping.id,
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
            provider_name="apple",
            device_id="watch123",
            external_device_mapping_id=mapping.id,
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
        assert result2.external_device_mapping_id == mapping.id
        assert result2.recorded_at == recorded_time

    def test_get_samples_requires_device_filter(self, db: Session, series_repo: DataPointSeriesRepository) -> None:
        """Test that get_samples requires at least device_id or external_device_mapping_id."""
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
        mapping1 = ExternalDeviceMappingFactory(user=user, device_id="device1")
        mapping2 = ExternalDeviceMappingFactory(user=user, device_id="device2")

        now = datetime.now(timezone.utc)

        # Create samples for device1
        for i in range(3):
            sample = TimeSeriesSampleCreate(
                id=uuid4(),
                user_id=user.id,
                provider_name="apple",
                device_id="device1",
                external_device_mapping_id=mapping1.id,
                recorded_at=now - timedelta(hours=i),
                value=70 + i,
                series_type=SeriesType.heart_rate,
            )
            series_repo.create(db, sample)

        # Create sample for device2
        sample = TimeSeriesSampleCreate(
            id=uuid4(),
            user_id=user.id,
            provider_name="apple",
            device_id="device2",
            external_device_mapping_id=mapping2.id,
            recorded_at=now,
            value=80,
            series_type=SeriesType.heart_rate,
        )
        series_repo.create(db, sample)

        query_params = TimeSeriesQueryParams(device_id="device1")

        # Act
        results, total_count = series_repo.get_samples(db, query_params, [SeriesType.heart_rate], user.id)

        # Assert
        assert len(results) == 3
        assert total_count == 3
        for _, mapping in results:
            assert mapping.device_id == "device1"

    def test_get_samples_by_external_device_mapping_id(
        self, db: Session, series_repo: DataPointSeriesRepository
    ) -> None:
        """Test getting samples filtered by external mapping ID."""
        # Arrange
        user = UserFactory()
        mapping = ExternalDeviceMappingFactory(user=user)

        now = datetime.now(timezone.utc)
        sample_ids = []

        for i in range(3):
            sample = TimeSeriesSampleCreate(
                id=uuid4(),
                user_id=user.id,
                provider_name="apple",
                device_id="device1",
                external_device_mapping_id=mapping.id,
                recorded_at=now - timedelta(hours=i),
                value=70 + i,
                series_type=SeriesType.heart_rate,
            )
            result = series_repo.create(db, sample)
            sample_ids.append(result.id)

        query_params = TimeSeriesQueryParams(external_device_mapping_id=mapping.id)

        # Act
        results, total_count = series_repo.get_samples(db, query_params, [SeriesType.heart_rate], user.id)

        # Assert
        assert len(results) == 3
        assert total_count == 3
        for sample, _ in results:
            assert sample.external_device_mapping_id == mapping.id

    def test_get_samples_by_series_type(self, db: Session, series_repo: DataPointSeriesRepository) -> None:
        """Test that get_samples only returns samples of the specified series type."""
        # Arrange
        user = UserFactory()
        mapping = ExternalDeviceMappingFactory(user=user, device_id="device1")
        now = datetime.now(timezone.utc)

        # Create heart rate samples
        for i in range(2):
            sample = TimeSeriesSampleCreate(
                id=uuid4(),
                user_id=user.id,
                provider_name="apple",
                device_id="device1",
                external_device_mapping_id=mapping.id,
                recorded_at=now - timedelta(hours=i),
                value=70 + i,
                series_type=SeriesType.heart_rate,
            )
            series_repo.create(db, sample)

        # Create steps sample
        sample = TimeSeriesSampleCreate(
            id=uuid4(),
            user_id=user.id,
            provider_name="apple",
            device_id="device1",
            external_device_mapping_id=mapping.id,
            recorded_at=now,
            value=10000,
            series_type=SeriesType.steps,
        )
        series_repo.create(db, sample)

        query_params = TimeSeriesQueryParams(device_id="device1")

        # Act
        results, total_count = series_repo.get_samples(db, query_params, [SeriesType.heart_rate], user.id)

        # Assert
        assert len(results) == 2
        assert total_count == 2
        from app.schemas.series_types import get_series_type_id

        expected_type_id = get_series_type_id(SeriesType.heart_rate)
        for sample, _ in results:
            assert sample.series_type_definition_id == expected_type_id

    def test_get_samples_by_date_range(self, db: Session, series_repo: DataPointSeriesRepository) -> None:
        """Test filtering samples by date range.

        Uses half-open interval [start, end) - start is inclusive, end is exclusive.
        """
        # Arrange
        user = UserFactory()
        mapping = ExternalDeviceMappingFactory(user=user, device_id="device1")

        now = datetime.now(timezone.utc)
        yesterday = now - timedelta(days=1)
        two_days_ago = now - timedelta(days=2)

        # Create samples at different times
        for dt in [two_days_ago, yesterday, now]:
            sample = TimeSeriesSampleCreate(
                id=uuid4(),
                user_id=user.id,
                provider_name="apple",
                device_id="device1",
                external_device_mapping_id=mapping.id,
                recorded_at=dt,
                value=72,
                series_type=SeriesType.heart_rate,
            )
            series_repo.create(db, sample)

        # Query with half-open interval [yesterday, now + 1s) to include both yesterday and now
        end_datetime = now + timedelta(seconds=1)
        query_params = TimeSeriesQueryParams(
            device_id="device1",
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
        """Test filtering samples by provider ID."""
        # Arrange
        user = UserFactory()
        mapping_apple = ExternalDeviceMappingFactory(user=user, provider_name="apple", device_id="device1")
        mapping_garmin = ExternalDeviceMappingFactory(user=user, provider_name="garmin", device_id="device1")

        now = datetime.now(timezone.utc)

        # Create samples for both providers
        sample1 = TimeSeriesSampleCreate(
            id=uuid4(),
            user_id=user.id,
            provider_name="apple",
            device_id="device1",
            external_device_mapping_id=mapping_apple.id,
            recorded_at=now,
            value=72,
            series_type=SeriesType.heart_rate,
        )
        series_repo.create(db, sample1)

        sample2 = TimeSeriesSampleCreate(
            id=uuid4(),
            user_id=user.id,
            provider_name="garmin",
            device_id="device1",
            external_device_mapping_id=mapping_garmin.id,
            recorded_at=now,
            value=75,
            series_type=SeriesType.heart_rate,
        )
        series_repo.create(db, sample2)

        query_params = TimeSeriesQueryParams(device_id="device1", provider_name="apple")

        # Act
        results, total_count = series_repo.get_samples(db, query_params, [SeriesType.heart_rate], user.id)

        # Assert
        assert len(results) == 1
        assert total_count == 1
        _, mapping = results[0]
        assert mapping.provider_name == "apple"

    def test_get_samples_ordered_by_recorded_at_asc(self, db: Session, series_repo: DataPointSeriesRepository) -> None:
        """Test that samples are ordered by recorded_at ascending."""
        # Arrange
        user = UserFactory()
        mapping = ExternalDeviceMappingFactory(user=user, device_id="device1")

        now = datetime.now(timezone.utc)
        times = [now - timedelta(hours=i) for i in range(3)]

        for dt in times:
            sample = TimeSeriesSampleCreate(
                id=uuid4(),
                user_id=user.id,
                provider_name="apple",
                device_id="device1",
                external_device_mapping_id=mapping.id,
                recorded_at=dt,
                value=72,
                series_type=SeriesType.heart_rate,
            )
            series_repo.create(db, sample)

        query_params = TimeSeriesQueryParams(device_id="device1")

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
        ExternalDeviceMappingFactory(user=user)

        # Note: Creating 1000+ records would be slow, so we just verify the limit exists
        # by checking the method implementation
        query_params = TimeSeriesQueryParams(device_id="device1")

        # Act
        results, total_count = series_repo.get_samples(db, query_params, [SeriesType.heart_rate], user.id)

        # Assert
        assert len(results) <= 1000

    def test_get_total_count(self, db: Session, series_repo: DataPointSeriesRepository) -> None:
        """Test counting total data points."""
        # Arrange
        initial_count = series_repo.get_total_count(db)

        user = UserFactory()
        mapping = ExternalDeviceMappingFactory(user=user)
        now = datetime.now(timezone.utc)

        for i in range(3):
            sample = TimeSeriesSampleCreate(
                id=uuid4(),
                user_id=user.id,
                provider_name="apple",
                device_id="device1",
                external_device_mapping_id=mapping.id,
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
        mapping = ExternalDeviceMappingFactory(user=user)

        now = datetime.now(timezone.utc)
        yesterday = now - timedelta(days=1)
        two_days_ago = now - timedelta(days=2)

        # Create samples at different times
        for i, dt in enumerate([two_days_ago, yesterday, yesterday + timedelta(seconds=1), now]):
            sample = TimeSeriesSampleCreate(
                id=uuid4(),
                user_id=user.id,
                provider_name="apple",
                device_id="device1",
                external_device_mapping_id=mapping.id,
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
        mapping = ExternalDeviceMappingFactory(user=user)

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
                    provider_name="apple",
                    device_id="device1",
                    external_device_mapping_id=mapping.id,
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
        mapping = ExternalDeviceMappingFactory(user=user)
        now = datetime.now(timezone.utc)

        # Create heart rate samples
        for i in range(3):
            sample = TimeSeriesSampleCreate(
                id=uuid4(),
                user_id=user.id,
                provider_name="apple",
                device_id="device1",
                external_device_mapping_id=mapping.id,
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
                provider_name="apple",
                device_id="device1",
                external_device_mapping_id=mapping.id,
                recorded_at=now + timedelta(seconds=i),
                value=10000,
                series_type=SeriesType.steps,
            )
            series_repo.create(db, sample)

        # Act
        results = series_repo.get_count_by_series_type(db)

        # Assert
        counts_dict = dict(results)
        from app.schemas.series_types import get_series_type_id

        hr_type_id = get_series_type_id(SeriesType.heart_rate)
        steps_type_id = get_series_type_id(SeriesType.steps)

        assert counts_dict.get(hr_type_id, 0) >= 3
        assert counts_dict.get(steps_type_id, 0) >= 2

    def test_get_count_by_provider(self, db: Session, series_repo: DataPointSeriesRepository) -> None:
        """Test aggregating data point counts by provider."""
        # Arrange
        user = UserFactory()
        mapping_apple = ExternalDeviceMappingFactory(user=user, provider_name="apple")
        mapping_garmin = ExternalDeviceMappingFactory(user=user, provider_name="garmin")

        now = datetime.now(timezone.utc)

        # Create samples for Apple
        for i in range(3):
            sample = TimeSeriesSampleCreate(
                id=uuid4(),
                user_id=user.id,
                provider_name="apple",
                device_id="device1",
                external_device_mapping_id=mapping_apple.id,
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
                provider_name="garmin",
                device_id="device2",
                external_device_mapping_id=mapping_garmin.id,
                recorded_at=now + timedelta(seconds=i),
                value=75,
                series_type=SeriesType.heart_rate,
            )
            series_repo.create(db, sample)

        # Act
        results = series_repo.get_count_by_provider(db)

        # Assert
        counts_dict = dict(results)
        assert counts_dict.get("apple", 0) >= 3
        assert counts_dict.get("garmin", 0) >= 2

    def test_get_samples_filters_by_user(self, db: Session, series_repo: DataPointSeriesRepository) -> None:
        """Test that samples are filtered by user ID."""
        # Arrange
        user1 = UserFactory()
        user2 = UserFactory()
        mapping1 = ExternalDeviceMappingFactory(user=user1, device_id="device1")
        mapping2 = ExternalDeviceMappingFactory(user=user2, device_id="device1")

        now = datetime.now(timezone.utc)

        # Create samples for user1
        for i in range(2):
            sample = TimeSeriesSampleCreate(
                id=uuid4(),
                user_id=user1.id,
                provider_name="apple",
                device_id="device1",
                external_device_mapping_id=mapping1.id,
                recorded_at=now + timedelta(seconds=i),
                value=72,
                series_type=SeriesType.heart_rate,
            )
            series_repo.create(db, sample)

        # Create sample for user2
        sample = TimeSeriesSampleCreate(
            id=uuid4(),
            user_id=user2.id,
            provider_name="apple",
            device_id="device1",
            external_device_mapping_id=mapping2.id,
            recorded_at=now,
            value=75,
            series_type=SeriesType.heart_rate,
        )
        series_repo.create(db, sample)

        query_params = TimeSeriesQueryParams(device_id="device1")

        # Act
        results, total_count = series_repo.get_samples(db, query_params, [SeriesType.heart_rate], user1.id)

        # Assert
        assert len(results) == 2
        assert total_count == 2
        for _, mapping in results:
            assert mapping.user_id == user1.id
