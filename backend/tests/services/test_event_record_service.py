"""
Tests for EventRecordService.

Tests cover:
- Creating event record details
- Getting formatted event records with filters
- Counting workouts by type
"""

from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.schemas.event_record import EventRecordQueryParams
from app.schemas.event_record_detail import EventRecordDetailCreate
from app.services.event_record_service import event_record_service
from tests.factories import DataSourceFactory, EventRecordFactory, UserFactory


class TestEventRecordServiceCreateDetail:
    """Test creating event record details."""

    def test_create_detail_with_heart_rate_metrics(self, db: Session) -> None:
        """Should create event record detail with heart rate metrics."""
        # Arrange
        event_record = EventRecordFactory(category="workout", type_="running")
        detail_payload = EventRecordDetailCreate(
            record_id=event_record.id,
            heart_rate_min=120,
            heart_rate_max=180,
            heart_rate_avg=Decimal("150.5"),
        )

        # Act
        detail = event_record_service.create_detail(db, detail_payload)

        # Assert (using getattr for polymorphic attributes)
        assert detail.record_id is not None
        assert detail.record_id == event_record.id
        assert getattr(detail, "heart_rate_min") == 120
        assert getattr(detail, "heart_rate_max") == 180
        assert getattr(detail, "heart_rate_avg") == Decimal("150.5")

    def test_create_detail_with_step_metrics(self, db: Session) -> None:
        """Should create event record detail with step metrics."""
        # Arrange
        event_record = EventRecordFactory(category="workout")
        detail_payload = EventRecordDetailCreate(
            record_id=event_record.id,
            steps_count=5000,
        )

        # Act
        detail = event_record_service.create_detail(db, detail_payload)

        # Assert (using getattr for polymorphic attributes)
        assert getattr(detail, "steps_count") == 5000

    def test_create_detail_with_workout_metrics(self, db: Session) -> None:
        """Should create event record detail with workout metrics."""
        # Arrange
        event_record = EventRecordFactory(category="workout", type_="cycling")
        detail_payload = EventRecordDetailCreate(
            record_id=event_record.id,
            max_speed=Decimal("35.5"),
            average_speed=Decimal("25.2"),
            max_watts=Decimal("350.0"),
            average_watts=Decimal("210.5"),
            moving_time_seconds=3600,
            total_elevation_gain=Decimal("450.0"),
            elev_high=Decimal("1200.0"),
            elev_low=Decimal("750.0"),
        )

        # Act
        detail = event_record_service.create_detail(db, detail_payload)

        # Assert (using getattr for polymorphic attributes)
        assert getattr(detail, "max_speed") == Decimal("35.5")
        assert getattr(detail, "average_speed") == Decimal("25.2")
        assert getattr(detail, "max_watts") == Decimal("350.0")
        assert getattr(detail, "average_watts") == Decimal("210.5")
        assert getattr(detail, "moving_time_seconds") == 3600
        assert getattr(detail, "total_elevation_gain") == Decimal("450.0")

    def test_create_detail_minimal_data(self, db: Session) -> None:
        """Should create event record detail with minimal data."""
        # Arrange
        event_record = EventRecordFactory()
        detail_payload = EventRecordDetailCreate(record_id=event_record.id)

        # Act
        detail = event_record_service.create_detail(db, detail_payload)

        # Assert (using getattr for polymorphic attributes)
        assert detail.record_id is not None
        assert detail.record_id == event_record.id
        # All optional fields should be None
        assert getattr(detail, "heart_rate_min", None) is None
        assert getattr(detail, "steps_count", None) is None


class TestEventRecordServiceGetRecordsResponse:
    """Test getting formatted event records."""

    @pytest.mark.asyncio
    async def test_get_records_response_basic(self, db: Session) -> None:
        """Should return formatted event records."""
        # Arrange
        user = UserFactory()
        mapping = DataSourceFactory(user=user, source="apple")
        record = EventRecordFactory(
            mapping=mapping,
            category="workout",
            type_="running",
        )

        query_params = EventRecordQueryParams(category="workout")

        # Act
        records = await event_record_service.get_records_response(db, query_params, str(user.id))

        # Assert
        assert len(records) >= 1
        matching_record = next((r for r in records if r.id == record.id), None)
        assert matching_record is not None
        assert matching_record.user_id == user.id
        assert matching_record.source == "apple"
        assert matching_record.category == "workout"
        assert matching_record.type == "running"

    @pytest.mark.asyncio
    async def test_get_records_response_filters_by_category(self, db: Session) -> None:
        """Should filter records by category."""
        # Arrange
        user = UserFactory()
        mapping = DataSourceFactory(user=user)

        workout_record = EventRecordFactory(mapping=mapping, category="workout")
        sleep_record = EventRecordFactory(mapping=mapping, category="sleep")

        query_params = EventRecordQueryParams(category="workout")

        # Act
        records = await event_record_service.get_records_response(db, query_params, str(user.id))

        # Assert
        record_ids = [r.id for r in records]
        assert workout_record.id in record_ids
        assert sleep_record.id not in record_ids

    @pytest.mark.asyncio
    async def test_get_records_response_filters_by_type(self, db: Session) -> None:
        """Should filter records by type."""
        # Arrange
        user = UserFactory()
        mapping = DataSourceFactory(user=user)

        running_record = EventRecordFactory(mapping=mapping, category="workout", type_="running")
        cycling_record = EventRecordFactory(mapping=mapping, category="workout", type_="cycling")

        query_params = EventRecordQueryParams(category="workout", record_type="running")

        # Act
        records = await event_record_service.get_records_response(db, query_params, str(user.id))

        # Assert
        record_ids = [r.id for r in records]
        assert running_record.id in record_ids
        assert cycling_record.id not in record_ids

    @pytest.mark.asyncio
    async def test_get_records_response_filters_by_device_id(self, db: Session) -> None:
        """Should filter records by device_id."""
        # Arrange
        user = UserFactory()
        mapping1 = DataSourceFactory(user=user, device_model="device_1")
        mapping2 = DataSourceFactory(user=user, device_model="device_2")

        record1 = EventRecordFactory(mapping=mapping1)
        record2 = EventRecordFactory(mapping=mapping2)

        query_params = EventRecordQueryParams(category="workout", device_model="device_1")

        # Act
        records = await event_record_service.get_records_response(db, query_params, str(user.id))

        # Assert
        record_ids = [r.id for r in records]
        assert record1.id in record_ids
        assert record2.id not in record_ids

    @pytest.mark.asyncio
    async def test_get_records_response_filters_by_provider(self, db: Session) -> None:
        """Should filter records by provider_name."""
        # Arrange
        user = UserFactory()
        apple_mapping = DataSourceFactory(user=user, source="apple")
        garmin_mapping = DataSourceFactory(user=user, source="garmin")

        apple_record = EventRecordFactory(mapping=apple_mapping)
        garmin_record = EventRecordFactory(mapping=garmin_mapping)

        query_params = EventRecordQueryParams(category="workout", source="apple")

        # Act
        records = await event_record_service.get_records_response(db, query_params, str(user.id))

        # Assert
        record_ids = [r.id for r in records]
        assert apple_record.id in record_ids
        assert garmin_record.id not in record_ids

    @pytest.mark.asyncio
    async def test_get_records_response_user_isolation(self, db: Session) -> None:
        """Should only return records for specified user."""
        # Arrange
        user1 = UserFactory(email="user1@example.com")
        user2 = UserFactory(email="user2@example.com")

        mapping1 = DataSourceFactory(user=user1)
        mapping2 = DataSourceFactory(user=user2)

        record1 = EventRecordFactory(mapping=mapping1)
        record2 = EventRecordFactory(mapping=mapping2)

        query_params = EventRecordQueryParams(category="workout")

        # Act
        records = await event_record_service.get_records_response(db, query_params, str(user1.id))

        # Assert
        record_ids = [r.id for r in records]
        assert record1.id in record_ids
        assert record2.id not in record_ids

    @pytest.mark.asyncio
    async def test_get_records_response_empty_result(self, db: Session) -> None:
        """Should return empty list when no records match."""
        # Arrange
        user = UserFactory()
        query_params = EventRecordQueryParams(category="workout")

        # Act
        records = await event_record_service.get_records_response(db, query_params, str(user.id))

        # Assert
        assert records == []


class TestEventRecordServiceGetCountByWorkoutType:
    """Test counting workouts by type."""

    def test_get_count_by_workout_type_groups_correctly(self, db: Session) -> None:
        """Should group and count workouts by type."""
        # Arrange
        mapping = DataSourceFactory()

        # Create multiple workouts of different types
        EventRecordFactory(mapping=mapping, category="workout", type_="running")
        EventRecordFactory(mapping=mapping, category="workout", type_="running")
        EventRecordFactory(mapping=mapping, category="workout", type_="running")
        EventRecordFactory(mapping=mapping, category="workout", type_="cycling")
        EventRecordFactory(mapping=mapping, category="workout", type_="cycling")
        EventRecordFactory(mapping=mapping, category="workout", type_="swimming")

        # Act
        results = event_record_service.get_count_by_workout_type(db)

        # Assert
        results_dict = dict(results)
        assert results_dict.get("running") == 3
        assert results_dict.get("cycling") == 2
        assert results_dict.get("swimming") == 1

    def test_get_count_by_workout_type_ordered_by_count(self, db: Session) -> None:
        """Should order results by count descending."""
        # Arrange
        mapping = DataSourceFactory()

        # Create workouts with different counts
        EventRecordFactory(mapping=mapping, type_="running")
        EventRecordFactory(mapping=mapping, type_="cycling")
        EventRecordFactory(mapping=mapping, type_="cycling")

        # Act
        results = event_record_service.get_count_by_workout_type(db)

        # Assert
        # Results should be ordered by count descending
        assert results[0][1] >= results[1][1]  # First count >= second count

    def test_get_count_by_workout_type_handles_null_type(self, db: Session) -> None:
        """Should handle records with null type."""
        # Arrange
        mapping = DataSourceFactory()

        EventRecordFactory(mapping=mapping, type_=None)
        EventRecordFactory(mapping=mapping, type_=None)
        EventRecordFactory(mapping=mapping, type_="running")

        # Act
        results = event_record_service.get_count_by_workout_type(db)

        # Assert
        results_dict = dict(results)
        assert results_dict.get(None) == 2
        assert results_dict.get("running") == 1

    def test_get_count_by_workout_type_empty_result(self, db: Session) -> None:
        """Should return empty list when no workout records exist."""
        # Act
        results = event_record_service.get_count_by_workout_type(db)

        # Assert
        assert results == []
