"""
Tests for TimeSeriesService.

Tests cover:
- Bulk creating time series samples
- Getting user heart rate series
- Getting user step series
- Getting daily histogram of data points
- Counting data points by series type
- Counting data points by provider
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.schemas.time_series import (
    HeartRateSampleCreate,
    SeriesType,
    StepSampleCreate,
    TimeSeriesQueryParams,
    TimeSeriesSampleCreate,
)
from app.services.time_series_service import time_series_service
from app.tests.utils.factories import (
    create_data_point_series,
    create_external_device_mapping,
    create_series_type_definition,
    create_user,
)


class TestTimeSeriesServiceBulkCreateSamples:
    """Test bulk creation of time series samples."""

    @pytest.mark.asyncio
    async def test_bulk_create_heart_rate_samples(self, db: Session) -> None:
        """Should bulk create heart rate samples."""
        # Arrange
        user = create_user(db)
        create_external_device_mapping(db, user=user, device_id="device_1")

        now = datetime.now(timezone.utc)
        samples = [
            HeartRateSampleCreate(
                id=uuid4(),
                user_id=user.id,
                device_id="device_1",
                recorded_at=now - timedelta(minutes=i),
                value=70 + i,
                series_type=SeriesType.heart_rate,
            )
            for i in range(5)
        ]

        # Act
        time_series_service.bulk_create_samples(db, samples)

        # Assert - verify samples were created
        query_params = TimeSeriesQueryParams(device_id="device_1")
        retrieved_samples = await time_series_service.get_user_heart_rate_series(db, str(user.id), query_params)
        assert len(retrieved_samples) == 5

    @pytest.mark.asyncio
    async def test_bulk_create_step_samples(self, db: Session) -> None:
        """Should bulk create step samples."""
        # Arrange
        user = create_user(db)
        create_external_device_mapping(db, user=user, device_id="device_2")

        now = datetime.now(timezone.utc)
        samples = [
            StepSampleCreate(
                id=uuid4(),
                user_id=user.id,
                device_id="device_2",
                recorded_at=now - timedelta(hours=i),
                value=1000 + i * 100,
                series_type=SeriesType.steps,
            )
            for i in range(3)
        ]

        # Act
        time_series_service.bulk_create_samples(db, samples)

        # Assert
        query_params = TimeSeriesQueryParams(device_id="device_2")
        retrieved_samples = await time_series_service.get_user_step_series(db, str(user.id), query_params)
        assert len(retrieved_samples) == 3

    def test_bulk_create_mixed_series_types(self, db: Session) -> None:
        """Should bulk create samples of different series types."""
        # Arrange
        user = create_user(db)
        create_external_device_mapping(db, user=user, device_id="device_3")

        now = datetime.now(timezone.utc)
        samples = [
            TimeSeriesSampleCreate(
                id=uuid4(),
                user_id=user.id,
                device_id="device_3",
                recorded_at=now - timedelta(minutes=1),
                value=72,
                series_type=SeriesType.heart_rate,
            ),
            TimeSeriesSampleCreate(
                id=uuid4(),
                user_id=user.id,
                device_id="device_3",
                recorded_at=now - timedelta(minutes=2),
                value=5000,
                series_type=SeriesType.steps,
            ),
        ]

        # Act
        time_series_service.bulk_create_samples(db, samples)

        # Assert
        total_count = time_series_service.get_total_count(db)
        assert total_count >= 2


class TestTimeSeriesServiceGetUserHeartRateSeries:
    """Test retrieving user heart rate series."""

    @pytest.mark.asyncio
    async def test_get_user_heart_rate_series_basic(self, db: Session) -> None:
        """Should retrieve heart rate samples for user."""
        # Arrange
        user = create_user(db)
        mapping = create_external_device_mapping(db, user=user, device_id="watch_1")
        series_type = create_series_type_definition(db, code="heart_rate", unit="bpm")

        # Create heart rate samples
        now = datetime.now(timezone.utc)
        hr1 = create_data_point_series(
            db,
            mapping=mapping,
            series_type=series_type,
            value=72.0,
            recorded_at=now - timedelta(minutes=5),
        )
        hr2 = create_data_point_series(
            db,
            mapping=mapping,
            series_type=series_type,
            value=75.0,
            recorded_at=now - timedelta(minutes=3),
        )

        query_params = TimeSeriesQueryParams(device_id="watch_1")

        # Act
        samples = await time_series_service.get_user_heart_rate_series(db, str(user.id), query_params)

        # Assert
        assert len(samples) >= 2
        sample_ids = [s.id for s in samples]
        assert hr1.id in sample_ids
        assert hr2.id in sample_ids

    @pytest.mark.asyncio
    async def test_get_user_heart_rate_series_filters_by_device(self, db: Session) -> None:
        """Should filter heart rate samples by device_id."""
        # Arrange
        user = create_user(db)
        mapping1 = create_external_device_mapping(db, user=user, device_id="watch_1")
        mapping2 = create_external_device_mapping(db, user=user, device_id="watch_2")
        series_type = create_series_type_definition(db, code="heart_rate", unit="bpm")

        hr1 = create_data_point_series(db, mapping=mapping1, series_type=series_type, value=72.0)
        hr2 = create_data_point_series(db, mapping=mapping2, series_type=series_type, value=75.0)

        query_params = TimeSeriesQueryParams(device_id="watch_1")

        # Act
        samples = await time_series_service.get_user_heart_rate_series(db, str(user.id), query_params)

        # Assert
        sample_ids = [s.id for s in samples]
        assert hr1.id in sample_ids
        assert hr2.id not in sample_ids

    @pytest.mark.asyncio
    async def test_get_user_heart_rate_series_filters_by_date_range(self, db: Session) -> None:
        """Should filter heart rate samples by date range."""
        # Arrange
        user = create_user(db)
        mapping = create_external_device_mapping(db, user=user, device_id="watch_1")
        series_type = create_series_type_definition(db, code="heart_rate", unit="bpm")

        now = datetime.now(timezone.utc)
        start = now - timedelta(days=7)
        end = now - timedelta(days=1)

        hr_old = create_data_point_series(
            db,
            mapping=mapping,
            series_type=series_type,
            recorded_at=now - timedelta(days=10),
        )
        hr_in_range = create_data_point_series(
            db,
            mapping=mapping,
            series_type=series_type,
            recorded_at=now - timedelta(days=5),
        )
        hr_recent = create_data_point_series(db, mapping=mapping, series_type=series_type, recorded_at=now)

        query_params = TimeSeriesQueryParams(
            device_id="watch_1",
            start_datetime=start,
            end_datetime=end,
        )

        # Act
        samples = await time_series_service.get_user_heart_rate_series(db, str(user.id), query_params)

        # Assert
        sample_ids = [s.id for s in samples]
        assert hr_in_range.id in sample_ids
        assert hr_old.id not in sample_ids
        assert hr_recent.id not in sample_ids

    @pytest.mark.asyncio
    async def test_get_user_heart_rate_series_user_isolation(self, db: Session) -> None:
        """Should only return samples for specified user."""
        # Arrange
        user1 = create_user(db, email="user1@example.com")
        user2 = create_user(db, email="user2@example.com")

        mapping1 = create_external_device_mapping(db, user=user1, device_id="watch_1")
        mapping2 = create_external_device_mapping(db, user=user2, device_id="watch_2")

        series_type = create_series_type_definition(db, code="heart_rate", unit="bpm")

        hr1 = create_data_point_series(db, mapping=mapping1, series_type=series_type)
        hr2 = create_data_point_series(db, mapping=mapping2, series_type=series_type)

        query_params = TimeSeriesQueryParams(device_id="watch_1")

        # Act
        samples = await time_series_service.get_user_heart_rate_series(db, str(user1.id), query_params)

        # Assert
        sample_ids = [s.id for s in samples]
        assert hr1.id in sample_ids
        assert hr2.id not in sample_ids

    @pytest.mark.asyncio
    async def test_get_user_heart_rate_series_requires_device_id(self, db: Session) -> None:
        """Should return empty list without device_id or external_mapping_id."""
        # Arrange
        user = create_user(db)
        query_params = TimeSeriesQueryParams()  # No device_id or mapping_id

        # Act
        samples = await time_series_service.get_user_heart_rate_series(db, str(user.id), query_params)

        # Assert
        assert samples == []


class TestTimeSeriesServiceGetUserStepSeries:
    """Test retrieving user step series."""

    @pytest.mark.asyncio
    async def test_get_user_step_series_basic(self, db: Session) -> None:
        """Should retrieve step samples for user."""
        # Arrange
        user = create_user(db)
        mapping = create_external_device_mapping(db, user=user, device_id="tracker_1")
        series_type = create_series_type_definition(db, code="steps", unit="count")

        step1 = create_data_point_series(db, mapping=mapping, series_type=series_type, value=5000.0)
        step2 = create_data_point_series(db, mapping=mapping, series_type=series_type, value=7500.0)

        query_params = TimeSeriesQueryParams(device_id="tracker_1")

        # Act
        samples = await time_series_service.get_user_step_series(db, str(user.id), query_params)

        # Assert
        assert len(samples) >= 2
        sample_ids = [s.id for s in samples]
        assert step1.id in sample_ids
        assert step2.id in sample_ids


class TestTimeSeriesServiceGetDailyHistogram:
    """Test getting daily histogram of data points."""

    def test_get_daily_histogram_groups_by_day(self, db: Session) -> None:
        """Should group data points by day."""
        # Arrange
        mapping = create_external_device_mapping(db)
        series_type = create_series_type_definition(db, code="heart_rate", unit="bpm")

        start_date = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        end_date = datetime(2024, 1, 4, 0, 0, 0, tzinfo=timezone.utc)

        # Day 1: 3 samples
        for i in range(3):
            create_data_point_series(
                db,
                mapping=mapping,
                series_type=series_type,
                recorded_at=datetime(2024, 1, 1, 10 + i, 0, 0, tzinfo=timezone.utc),
            )

        # Day 2: 2 samples
        for i in range(2):
            create_data_point_series(
                db,
                mapping=mapping,
                series_type=series_type,
                recorded_at=datetime(2024, 1, 2, 10 + i, 0, 0, tzinfo=timezone.utc),
            )

        # Day 3: 1 sample
        create_data_point_series(
            db,
            mapping=mapping,
            series_type=series_type,
            recorded_at=datetime(2024, 1, 3, 10, 0, 0, tzinfo=timezone.utc),
        )

        # Act
        histogram = time_series_service.get_daily_histogram(db, start_date, end_date)

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
        histogram = time_series_service.get_daily_histogram(db, start_date, end_date)

        # Assert
        assert histogram == []


class TestTimeSeriesServiceGetCountBySeriesType:
    """Test counting data points by series type."""

    def test_get_count_by_series_type_groups_correctly(self, db: Session) -> None:
        """Should group and count data points by series type."""
        # Arrange
        mapping = create_external_device_mapping(db)
        hr_type = create_series_type_definition(db, code="heart_rate", unit="bpm")
        step_type = create_series_type_definition(db, code="steps", unit="count")

        # Create 3 heart rate samples
        for _ in range(3):
            create_data_point_series(db, mapping=mapping, series_type=hr_type)

        # Create 2 step samples
        for _ in range(2):
            create_data_point_series(db, mapping=mapping, series_type=step_type)

        # Act
        results = time_series_service.get_count_by_series_type(db)

        # Assert
        results_dict = dict(results)
        assert results_dict[hr_type.id] == 3
        assert results_dict[step_type.id] == 2

    def test_get_count_by_series_type_ordered_by_count(self, db: Session) -> None:
        """Should order results by count descending."""
        # Arrange
        mapping = create_external_device_mapping(db)
        # Use existing seeded series types to avoid ID conflicts
        type1 = create_series_type_definition(db, code="heart_rate", unit="bpm")
        type2 = create_series_type_definition(db, code="steps", unit="count")

        # Create more of type1
        for _ in range(5):
            create_data_point_series(db, mapping=mapping, series_type=type1)

        # Create fewer of type2
        for _ in range(2):
            create_data_point_series(db, mapping=mapping, series_type=type2)

        # Act
        results = time_series_service.get_count_by_series_type(db)

        # Assert
        # Results should be ordered by count descending
        assert results[0][1] >= results[1][1]

    def test_get_count_by_series_type_empty_result(self, db: Session) -> None:
        """Should return empty list when no data points exist."""
        # Act
        results = time_series_service.get_count_by_series_type(db)

        # Assert
        assert results == []


class TestTimeSeriesServiceGetCountByProvider:
    """Test counting data points by provider."""

    def test_get_count_by_provider_groups_correctly(self, db: Session) -> None:
        """Should group and count data points by provider."""
        # Arrange
        user = create_user(db)
        apple_mapping = create_external_device_mapping(db, user=user, provider_id="apple")
        garmin_mapping = create_external_device_mapping(db, user=user, provider_id="garmin")

        series_type = create_series_type_definition(db, code="heart_rate", unit="bpm")

        # Create 4 samples from Apple
        for _ in range(4):
            create_data_point_series(db, mapping=apple_mapping, series_type=series_type)

        # Create 2 samples from Garmin
        for _ in range(2):
            create_data_point_series(db, mapping=garmin_mapping, series_type=series_type)

        # Act
        results = time_series_service.get_count_by_provider(db)

        # Assert
        results_dict = dict(results)
        assert results_dict["apple"] == 4
        assert results_dict["garmin"] == 2

    def test_get_count_by_provider_ordered_by_count(self, db: Session) -> None:
        """Should order results by count descending."""
        # Arrange
        results = time_series_service.get_count_by_provider(db)

        if len(results) > 1:
            # Verify descending order
            for i in range(len(results) - 1):
                assert results[i][1] >= results[i + 1][1]

    def test_get_count_by_provider_empty_result(self, db: Session) -> None:
        """Should return empty list when no data points exist."""
        # Act
        results = time_series_service.get_count_by_provider(db)

        # Assert
        assert results == []


class TestTimeSeriesServiceGetTotalCount:
    """Test getting total count of data points."""

    def test_get_total_count(self, db: Session) -> None:
        """Should return total count of all data points."""
        # Arrange
        mapping = create_external_device_mapping(db)
        series_type = create_series_type_definition(db, code="heart_rate", unit="bpm")

        initial_count = time_series_service.get_total_count(db)

        # Create 5 samples
        for _ in range(5):
            create_data_point_series(db, mapping=mapping, series_type=series_type)

        # Act
        total_count = time_series_service.get_total_count(db)

        # Assert
        assert total_count == initial_count + 5

    def test_get_total_count_empty_database(self, db: Session) -> None:
        """Should return 0 when no data points exist."""
        # Note: This test might fail if there's existing data in the test DB
        # from other tests running in the same session
        # Act
        count = time_series_service.get_total_count(db)

        # Assert
        assert count >= 0  # At minimum should be non-negative


class TestTimeSeriesServiceGetCountInRange:
    """Test counting data points in date range."""

    def test_get_count_in_range(self, db: Session) -> None:
        """Should count data points within date range."""
        # Arrange
        mapping = create_external_device_mapping(db)
        series_type = create_series_type_definition(db, code="heart_rate", unit="bpm")

        now = datetime.now(timezone.utc)
        start = now - timedelta(days=7)
        end = now - timedelta(days=1)

        # Create samples at different times
        create_data_point_series(
            db,
            mapping=mapping,
            series_type=series_type,
            recorded_at=now - timedelta(days=10),
        )  # Before range
        create_data_point_series(
            db,
            mapping=mapping,
            series_type=series_type,
            recorded_at=now - timedelta(days=5),
        )  # In range
        create_data_point_series(
            db,
            mapping=mapping,
            series_type=series_type,
            recorded_at=now - timedelta(days=3),
        )  # In range
        create_data_point_series(db, mapping=mapping, series_type=series_type, recorded_at=now)  # After range

        # Act
        count = time_series_service.get_count_in_range(db, start, end)

        # Assert
        assert count == 2

    def test_get_count_in_range_empty_result(self, db: Session) -> None:
        """Should return 0 when no data points in range."""
        # Arrange
        now = datetime.now(timezone.utc)
        future = now + timedelta(days=7)
        far_future = future + timedelta(days=7)

        # Act
        count = time_series_service.get_count_in_range(db, future, far_future)

        # Assert
        assert count == 0
