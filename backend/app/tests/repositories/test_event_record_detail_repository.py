"""
Tests for EventRecordDetailRepository.

Tests cover:
- create operations (workout details, sleep details, polymorphic behavior)
- get operations (by ID, by record_id)
- get_all operations (filtering, pagination, sorting)
- update operations (partial updates)
- delete operations
- polymorphic inheritance behavior
"""

import pytest
from decimal import Decimal
from uuid import uuid4
from sqlalchemy.orm import Session

from app.models import EventRecordDetail, WorkoutDetails, SleepDetails
from app.repositories.event_record_detail_repository import EventRecordDetailRepository
from app.schemas.event_record_detail import EventRecordDetailCreate, EventRecordDetailUpdate
from app.tests.utils.factories import create_event_record, create_workout_details, create_sleep_details


class TestEventRecordDetailRepository:
    """Test suite for EventRecordDetailRepository."""

    @pytest.fixture
    def detail_repo(self) -> EventRecordDetailRepository:
        """Create EventRecordDetailRepository instance."""
        return EventRecordDetailRepository(EventRecordDetail)

    def test_create_workout_details(self, db: Session, detail_repo: EventRecordDetailRepository):
        """Test creating workout details."""
        # Arrange
        event_record = create_event_record(db, category="workout")
        detail_data = EventRecordDetailCreate(
            record_id=event_record.id,
            heart_rate_avg=Decimal("145.5"),
            heart_rate_max=175,
            heart_rate_min=95,
            steps_total=8500,
        )

        # Act
        result = detail_repo.create(db, detail_data, detail_type="workout")

        # Assert
        assert isinstance(result, WorkoutDetails)
        assert result.record_id == event_record.id
        assert result.heart_rate_avg == Decimal("145.5")
        assert result.heart_rate_max == 175
        assert result.heart_rate_min == 95
        assert result.steps_total == 8500
        assert result.detail_type == "workout"

    def test_create_sleep_details(self, db: Session, detail_repo: EventRecordDetailRepository):
        """Test creating sleep details."""
        # Arrange
        event_record = create_event_record(db, category="sleep")
        detail_data = EventRecordDetailCreate(
            record_id=event_record.id,
            sleep_total_duration_minutes=480,
            sleep_deep_minutes=120,
            sleep_light_minutes=240,
            sleep_rem_minutes=90,
            sleep_awake_minutes=30,
        )

        # Act
        result = detail_repo.create(db, detail_data, detail_type="sleep")

        # Assert
        assert isinstance(result, SleepDetails)
        assert result.record_id == event_record.id
        assert result.sleep_total_duration_minutes == 480
        assert result.sleep_deep_minutes == 120
        assert result.sleep_light_minutes == 240
        assert result.sleep_rem_minutes == 90
        assert result.sleep_awake_minutes == 30
        assert result.detail_type == "sleep"

    def test_create_with_minimal_fields(self, db: Session, detail_repo: EventRecordDetailRepository):
        """Test creating workout details with only required fields."""
        # Arrange
        event_record = create_event_record(db, category="workout")
        detail_data = EventRecordDetailCreate(record_id=event_record.id)

        # Act
        result = detail_repo.create(db, detail_data, detail_type="workout")

        # Assert
        assert isinstance(result, WorkoutDetails)
        assert result.record_id == event_record.id
        assert result.heart_rate_avg is None
        assert result.steps_total is None

    def test_create_with_invalid_detail_type(self, db: Session, detail_repo: EventRecordDetailRepository):
        """Test creating detail with invalid detail_type raises ValueError."""
        # Arrange
        event_record = create_event_record(db)
        detail_data = EventRecordDetailCreate(record_id=event_record.id)

        # Act & Assert
        with pytest.raises(ValueError, match="Unknown detail type: invalid"):
            detail_repo.create(db, detail_data, detail_type="invalid")

    def test_get_by_record_id_workout(self, db: Session, detail_repo: EventRecordDetailRepository):
        """Test getting workout details by record_id."""
        # Arrange
        workout_details = create_workout_details(db)

        # Act
        result = detail_repo.get_by_record_id(db, workout_details.record_id)

        # Assert
        assert result is not None
        assert result.record_id == workout_details.record_id
        assert isinstance(result, WorkoutDetails)

    def test_get_by_record_id_sleep(self, db: Session, detail_repo: EventRecordDetailRepository):
        """Test getting sleep details by record_id."""
        # Arrange
        sleep_details = create_sleep_details(db)

        # Act
        result = detail_repo.get_by_record_id(db, sleep_details.record_id)

        # Assert
        assert result is not None
        assert result.record_id == sleep_details.record_id
        assert isinstance(result, SleepDetails)

    def test_get_by_record_id_nonexistent(self, db: Session, detail_repo: EventRecordDetailRepository):
        """Test getting detail by nonexistent record_id returns None."""
        # Act
        result = detail_repo.get_by_record_id(db, uuid4())

        # Assert
        assert result is None

    def test_get_all_empty_database(self, db: Session, detail_repo: EventRecordDetailRepository):
        """Test get_all returns empty list when no details exist."""
        # Act
        result = detail_repo.get_all(db, filters={}, offset=0, limit=10, sort_by=None)

        # Assert
        assert result == []

    def test_get_all_multiple_details(self, db: Session, detail_repo: EventRecordDetailRepository):
        """Test get_all returns multiple detail records."""
        # Arrange
        workout1 = create_workout_details(db)
        workout2 = create_workout_details(db)
        sleep1 = create_sleep_details(db)

        # Act
        result = detail_repo.get_all(db, filters={}, offset=0, limit=10, sort_by=None)

        # Assert
        assert len(result) >= 3
        record_ids = [d.record_id for d in result]
        assert workout1.record_id in record_ids
        assert workout2.record_id in record_ids
        assert sleep1.record_id in record_ids

    def test_get_all_with_pagination(self, db: Session, detail_repo: EventRecordDetailRepository):
        """Test pagination with offset and limit."""
        # Arrange
        for _ in range(5):
            create_workout_details(db)

        # Act - Get first 2 details
        page1 = detail_repo.get_all(db, filters={}, offset=0, limit=2, sort_by=None)

        # Act - Get next 2 details
        page2 = detail_repo.get_all(db, filters={}, offset=2, limit=2, sort_by=None)

        # Assert
        assert len(page1) == 2
        assert len(page2) == 2
        # Verify different results
        page1_ids = {d.record_id for d in page1}
        page2_ids = {d.record_id for d in page2}
        assert len(page1_ids & page2_ids) == 0  # No overlap

    def test_update_workout_details(self, db: Session, detail_repo: EventRecordDetailRepository):
        """Test updating workout details."""
        # Arrange
        workout_details = create_workout_details(
            db, heart_rate_avg=Decimal("140.0"), steps_total=5000
        )
        update_data = EventRecordDetailUpdate(
            heart_rate_avg=Decimal("155.0"), steps_total=10000
        )

        # Act
        result = detail_repo.update(db, workout_details, update_data)

        # Assert
        assert result.heart_rate_avg == Decimal("155.0")
        assert result.steps_total == 10000

        # Verify in database
        db.expire_all()
        updated = detail_repo.get_by_record_id(db, workout_details.record_id)
        assert updated.heart_rate_avg == Decimal("155.0")
        assert updated.steps_total == 10000

    def test_update_partial_fields(self, db: Session, detail_repo: EventRecordDetailRepository):
        """Test updating only some fields."""
        # Arrange
        workout_details = create_workout_details(
            db,
            heart_rate_avg=Decimal("140.0"),
            heart_rate_max=180,
            steps_total=5000,
        )
        update_data = EventRecordDetailUpdate(heart_rate_avg=Decimal("150.0"))

        # Act
        result = detail_repo.update(db, workout_details, update_data)

        # Assert
        assert result.heart_rate_avg == Decimal("150.0")
        assert result.heart_rate_max == 180  # Unchanged
        assert result.steps_total == 5000  # Unchanged

    def test_delete_workout_details(self, db: Session, detail_repo: EventRecordDetailRepository):
        """Test deleting workout details."""
        # Arrange
        workout_details = create_workout_details(db)
        record_id = workout_details.record_id

        # Act
        detail_repo.delete(db, workout_details)

        # Assert
        db.expire_all()
        deleted = detail_repo.get_by_record_id(db, record_id)
        assert deleted is None

    def test_polymorphic_inheritance_behavior(self, db: Session, detail_repo: EventRecordDetailRepository):
        """Test that polymorphic inheritance correctly returns specific detail types."""
        # Arrange
        workout_details = create_workout_details(db, heart_rate_avg=Decimal("150.0"))
        sleep_details = create_sleep_details(db, sleep_total_duration_minutes=420)

        # Act - Query base class but get specific types
        workout_result = detail_repo.get_by_record_id(db, workout_details.record_id)
        sleep_result = detail_repo.get_by_record_id(db, sleep_details.record_id)

        # Assert - Should return specific types, not base class
        assert isinstance(workout_result, WorkoutDetails)
        assert not isinstance(workout_result, SleepDetails)
        assert workout_result.detail_type == "workout"
        assert workout_result.heart_rate_avg == Decimal("150.0")

        assert isinstance(sleep_result, SleepDetails)
        assert not isinstance(sleep_result, WorkoutDetails)
        assert sleep_result.detail_type == "sleep"
        assert sleep_result.sleep_total_duration_minutes == 420
