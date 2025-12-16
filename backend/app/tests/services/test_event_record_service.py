"""
Tests for EventRecordService.

Tests cover:
- Creating event record details
- Getting formatted event records with filters
- Counting workouts by type
"""

import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from uuid import uuid4

from app.schemas.event_record import EventRecordQueryParams
from app.schemas.event_record_detail import EventRecordDetailCreate
from app.services.event_record_service import event_record_service
from app.tests.utils.factories import create_event_record, create_external_device_mapping, create_user


class TestEventRecordServiceCreateDetail:
    """Test creating event record details."""

    def test_create_detail_with_heart_rate_metrics(self, db: Session):
        """Should create event record detail with heart rate metrics."""
        # Arrange
        event_record = create_event_record(db, category="workout", type_="running")
        detail_payload = EventRecordDetailCreate(
            record_id=event_record.id,
            heart_rate_min=120,
            heart_rate_max=180,
            heart_rate_avg=Decimal("150.5"),
        )

        # Act
        detail = event_record_service.create_detail(db, detail_payload)

        # Assert
        assert detail.id is not None
        assert detail.record_id == event_record.id
        assert detail.heart_rate_min == 120
        assert detail.heart_rate_max == 180
        assert detail.heart_rate_avg == Decimal("150.5")

    def test_create_detail_with_step_metrics(self, db: Session):
        """Should create event record detail with step metrics."""
        # Arrange
        event_record = create_event_record(db, category="workout")
        detail_payload = EventRecordDetailCreate(
            record_id=event_record.id,
            steps_min=50,
            steps_max=200,
            steps_avg=Decimal("125.3"),
            steps_total=5000,
        )

        # Act
        detail = event_record_service.create_detail(db, detail_payload)

        # Assert
        assert detail.steps_min == 50
        assert detail.steps_max == 200
        assert detail.steps_avg == Decimal("125.3")
        assert detail.steps_total == 5000

    def test_create_detail_with_workout_metrics(self, db: Session):
        """Should create event record detail with workout metrics."""
        # Arrange
        event_record = create_event_record(db, category="workout", type_="cycling")
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

        # Assert
        assert detail.max_speed == Decimal("35.5")
        assert detail.average_speed == Decimal("25.2")
        assert detail.max_watts == Decimal("350.0")
        assert detail.average_watts == Decimal("210.5")
        assert detail.moving_time_seconds == 3600
        assert detail.total_elevation_gain == Decimal("450.0")

    def test_create_detail_with_sleep_metrics(self, db: Session):
        """Should create event record detail with sleep metrics."""
        # Arrange
        event_record = create_event_record(db, category="sleep", type_="sleep")
        detail_payload = EventRecordDetailCreate(
            record_id=event_record.id,
            sleep_total_duration_minutes=480,
            sleep_time_in_bed_minutes=510,
            sleep_efficiency_score=Decimal("94.1"),
            sleep_deep_minutes=120,
            sleep_rem_minutes=90,
            sleep_light_minutes=240,
            sleep_awake_minutes=30,
        )

        # Act
        detail = event_record_service.create_detail(db, detail_payload)

        # Assert
        assert detail.sleep_total_duration_minutes == 480
        assert detail.sleep_time_in_bed_minutes == 510
        assert detail.sleep_efficiency_score == Decimal("94.1")
        assert detail.sleep_deep_minutes == 120
        assert detail.sleep_rem_minutes == 90
        assert detail.sleep_light_minutes == 240
        assert detail.sleep_awake_minutes == 30

    def test_create_detail_minimal_data(self, db: Session):
        """Should create event record detail with minimal data."""
        # Arrange
        event_record = create_event_record(db)
        detail_payload = EventRecordDetailCreate(record_id=event_record.id)

        # Act
        detail = event_record_service.create_detail(db, detail_payload)

        # Assert
        assert detail.id is not None
        assert detail.record_id == event_record.id
        # All optional fields should be None
        assert detail.heart_rate_min is None
        assert detail.steps_total is None


class TestEventRecordServiceGetRecordsResponse:
    """Test getting formatted event records."""

    @pytest.mark.asyncio
    async def test_get_records_response_basic(self, db: Session):
        """Should return formatted event records."""
        # Arrange
        user = create_user(db)
        mapping = create_external_device_mapping(db, user=user, provider_id="apple")
        record = create_event_record(
            db,
            mapping=mapping,
            category="workout",
            type_="running",
        )

        query_params = EventRecordQueryParams(category="workout")

        # Act
        records = await event_record_service.get_records_response(
            db, query_params, str(user.id)
        )

        # Assert
        assert len(records) >= 1
        matching_record = next((r for r in records if r.id == record.id), None)
        assert matching_record is not None
        assert matching_record.user_id == user.id
        assert matching_record.provider_id == "apple"
        assert matching_record.category == "workout"
        assert matching_record.type == "running"

    @pytest.mark.asyncio
    async def test_get_records_response_filters_by_category(self, db: Session):
        """Should filter records by category."""
        # Arrange
        user = create_user(db)
        mapping = create_external_device_mapping(db, user=user)

        workout_record = create_event_record(db, mapping=mapping, category="workout")
        sleep_record = create_event_record(db, mapping=mapping, category="sleep")

        query_params = EventRecordQueryParams(category="workout")

        # Act
        records = await event_record_service.get_records_response(
            db, query_params, str(user.id)
        )

        # Assert
        record_ids = [r.id for r in records]
        assert workout_record.id in record_ids
        assert sleep_record.id not in record_ids

    @pytest.mark.asyncio
    async def test_get_records_response_filters_by_type(self, db: Session):
        """Should filter records by type."""
        # Arrange
        user = create_user(db)
        mapping = create_external_device_mapping(db, user=user)

        running_record = create_event_record(
            db, mapping=mapping, category="workout", type_="running"
        )
        cycling_record = create_event_record(
            db, mapping=mapping, category="workout", type_="cycling"
        )

        query_params = EventRecordQueryParams(category="workout", record_type="running")

        # Act
        records = await event_record_service.get_records_response(
            db, query_params, str(user.id)
        )

        # Assert
        record_ids = [r.id for r in records]
        assert running_record.id in record_ids
        assert cycling_record.id not in record_ids

    @pytest.mark.asyncio
    async def test_get_records_response_filters_by_device_id(self, db: Session):
        """Should filter records by device_id."""
        # Arrange
        user = create_user(db)
        mapping1 = create_external_device_mapping(db, user=user, device_id="device_1")
        mapping2 = create_external_device_mapping(db, user=user, device_id="device_2")

        record1 = create_event_record(db, mapping=mapping1)
        record2 = create_event_record(db, mapping=mapping2)

        query_params = EventRecordQueryParams(category="workout", device_id="device_1")

        # Act
        records = await event_record_service.get_records_response(
            db, query_params, str(user.id)
        )

        # Assert
        record_ids = [r.id for r in records]
        assert record1.id in record_ids
        assert record2.id not in record_ids

    @pytest.mark.asyncio
    async def test_get_records_response_filters_by_provider(self, db: Session):
        """Should filter records by provider_id."""
        # Arrange
        user = create_user(db)
        apple_mapping = create_external_device_mapping(db, user=user, provider_id="apple")
        garmin_mapping = create_external_device_mapping(db, user=user, provider_id="garmin")

        apple_record = create_event_record(db, mapping=apple_mapping)
        garmin_record = create_event_record(db, mapping=garmin_mapping)

        query_params = EventRecordQueryParams(category="workout", provider_id="apple")

        # Act
        records = await event_record_service.get_records_response(
            db, query_params, str(user.id)
        )

        # Assert
        record_ids = [r.id for r in records]
        assert apple_record.id in record_ids
        assert garmin_record.id not in record_ids

    @pytest.mark.asyncio
    async def test_get_records_response_user_isolation(self, db: Session):
        """Should only return records for specified user."""
        # Arrange
        user1 = create_user(db, email="user1@example.com")
        user2 = create_user(db, email="user2@example.com")

        mapping1 = create_external_device_mapping(db, user=user1)
        mapping2 = create_external_device_mapping(db, user=user2)

        record1 = create_event_record(db, mapping=mapping1)
        record2 = create_event_record(db, mapping=mapping2)

        query_params = EventRecordQueryParams(category="workout")

        # Act
        records = await event_record_service.get_records_response(
            db, query_params, str(user1.id)
        )

        # Assert
        record_ids = [r.id for r in records]
        assert record1.id in record_ids
        assert record2.id not in record_ids

    @pytest.mark.asyncio
    async def test_get_records_response_empty_result(self, db: Session):
        """Should return empty list when no records match."""
        # Arrange
        user = create_user(db)
        query_params = EventRecordQueryParams(category="workout")

        # Act
        records = await event_record_service.get_records_response(
            db, query_params, str(user.id)
        )

        # Assert
        assert records == []


class TestEventRecordServiceGetCountByWorkoutType:
    """Test counting workouts by type."""

    def test_get_count_by_workout_type_groups_correctly(self, db: Session):
        """Should group and count workouts by type."""
        # Arrange
        mapping = create_external_device_mapping(db)

        # Create multiple workouts of different types
        create_event_record(db, mapping=mapping, category="workout", type_="running")
        create_event_record(db, mapping=mapping, category="workout", type_="running")
        create_event_record(db, mapping=mapping, category="workout", type_="running")
        create_event_record(db, mapping=mapping, category="workout", type_="cycling")
        create_event_record(db, mapping=mapping, category="workout", type_="cycling")
        create_event_record(db, mapping=mapping, category="workout", type_="swimming")

        # Act
        results = event_record_service.get_count_by_workout_type(db)

        # Assert
        results_dict = dict(results)
        assert results_dict.get("running") == 3
        assert results_dict.get("cycling") == 2
        assert results_dict.get("swimming") == 1

    def test_get_count_by_workout_type_ordered_by_count(self, db: Session):
        """Should order results by count descending."""
        # Arrange
        mapping = create_external_device_mapping(db)

        # Create workouts with different counts
        create_event_record(db, mapping=mapping, type_="running")
        create_event_record(db, mapping=mapping, type_="cycling")
        create_event_record(db, mapping=mapping, type_="cycling")

        # Act
        results = event_record_service.get_count_by_workout_type(db)

        # Assert
        # Results should be ordered by count descending
        assert results[0][1] >= results[1][1]  # First count >= second count

    def test_get_count_by_workout_type_handles_null_type(self, db: Session):
        """Should handle records with null type."""
        # Arrange
        mapping = create_external_device_mapping(db)

        create_event_record(db, mapping=mapping, type_=None)
        create_event_record(db, mapping=mapping, type_=None)
        create_event_record(db, mapping=mapping, type_="running")

        # Act
        results = event_record_service.get_count_by_workout_type(db)

        # Assert
        results_dict = dict(results)
        assert results_dict.get(None) == 2
        assert results_dict.get("running") == 1

    def test_get_count_by_workout_type_empty_result(self, db: Session):
        """Should return empty list when no workout records exist."""
        # Act
        results = event_record_service.get_count_by_workout_type(db)

        # Assert
        assert results == []
