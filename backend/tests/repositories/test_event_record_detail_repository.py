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

from decimal import Decimal
from typing import get_args
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.models import DETAIL_MODELS, DetailType, EventRecordDetail, SleepDetails, WorkoutDetails
from app.repositories.event_record_detail_repository import EventRecordDetailRepository
from app.schemas.model_crud.activities import EventRecordDetailCreate, EventRecordDetailUpdate
from tests.factories import EventRecordFactory, SleepDetailsFactory, WorkoutDetailsFactory


class TestEventRecordDetailRepository:
    """Test suite for EventRecordDetailRepository."""

    @pytest.fixture
    def detail_repo(self) -> EventRecordDetailRepository:
        """Create EventRecordDetailRepository instance configured for WorkoutDetails."""
        return EventRecordDetailRepository(WorkoutDetails)

    @pytest.fixture
    def sleep_detail_repo(self) -> EventRecordDetailRepository:
        """Create EventRecordDetailRepository instance configured for SleepDetails."""
        return EventRecordDetailRepository(SleepDetails)

    def test_create_workout_details(self, db: Session, detail_repo: EventRecordDetailRepository) -> None:
        """Test creating workout details."""
        # Arrange
        event_record = EventRecordFactory(category="workout")
        detail_data = EventRecordDetailCreate(
            record_id=event_record.id,
            heart_rate_avg=Decimal("145.5"),
            heart_rate_max=175,
            heart_rate_min=95,
            steps_count=8500,
        )

        # Act
        result = detail_repo.create(db, detail_data, detail_type="workout")

        # Assert
        assert isinstance(result, WorkoutDetails)
        assert result.record_id == event_record.id
        assert result.heart_rate_avg == Decimal("145.5")
        assert result.heart_rate_max == 175
        assert result.heart_rate_min == 95
        assert result.steps_count == 8500

    def test_create_sleep_details(self, db: Session, detail_repo: EventRecordDetailRepository) -> None:
        """Test creating sleep details."""
        # Arrange
        event_record = EventRecordFactory(category="sleep")
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

    def test_create_with_minimal_fields(self, db: Session, detail_repo: EventRecordDetailRepository) -> None:
        """Test creating workout details with only required fields."""
        # Arrange
        event_record = EventRecordFactory(category="workout")
        detail_data = EventRecordDetailCreate(record_id=event_record.id)

        # Act
        result = detail_repo.create(db, detail_data, detail_type="workout")

        # Assert
        assert isinstance(result, WorkoutDetails)
        assert result.record_id == event_record.id
        assert result.heart_rate_avg is None
        assert result.steps_count is None

    def test_create_with_invalid_detail_type(self, db: Session, detail_repo: EventRecordDetailRepository) -> None:
        """Test creating detail with invalid detail_type raises ValueError."""
        # Arrange
        event_record = EventRecordFactory()
        detail_data = EventRecordDetailCreate(record_id=event_record.id)

        # Act & Assert
        with pytest.raises(ValueError, match="Unknown detail type: invalid"):
            detail_repo.create(db, detail_data, detail_type="invalid")

    def test_get_by_record_id_workout(self, db: Session, detail_repo: EventRecordDetailRepository) -> None:
        """Test getting workout details by record_id."""
        # Arrange
        workout_details = WorkoutDetailsFactory()

        # Act
        result = detail_repo.get_by_record_id(db, workout_details.record_id)

        # Assert
        assert result is not None
        assert result.record_id == workout_details.record_id
        assert isinstance(result, WorkoutDetails)

    def test_get_by_record_id_sleep(self, db: Session, sleep_detail_repo: EventRecordDetailRepository) -> None:
        """Test getting sleep details by record_id."""
        # Arrange
        sleep_details = SleepDetailsFactory()

        # Act
        result = sleep_detail_repo.get_by_record_id(db, sleep_details.record_id)

        # Assert
        assert result is not None
        assert result.record_id == sleep_details.record_id
        assert isinstance(result, SleepDetails)

    def test_get_by_record_id_nonexistent(self, db: Session, detail_repo: EventRecordDetailRepository) -> None:
        """Test getting detail by nonexistent record_id returns None."""
        # Act
        result = detail_repo.get_by_record_id(db, uuid4())

        # Assert
        assert result is None

    def test_get_all_empty_database(self, db: Session) -> None:
        """Test get_all returns empty list when no workout details exist."""
        repo = EventRecordDetailRepository(WorkoutDetails)
        result = repo.get_all(db, filters={}, offset=0, limit=10, sort_by=None)
        assert result == []

    def test_get_all_multiple_details(self, db: Session) -> None:
        """Test get_all returns multiple workout detail records."""
        repo = EventRecordDetailRepository(WorkoutDetails)
        workout1 = WorkoutDetailsFactory()
        workout2 = WorkoutDetailsFactory()

        result = repo.get_all(db, filters={}, offset=0, limit=10, sort_by=None)

        assert len(result) >= 2
        record_ids = [d.record_id for d in result]
        assert workout1.record_id in record_ids
        assert workout2.record_id in record_ids

    def test_get_all_with_pagination(self, db: Session) -> None:
        """Test pagination with offset and limit."""
        repo = EventRecordDetailRepository(WorkoutDetails)
        for _ in range(5):
            WorkoutDetailsFactory()

        page1 = repo.get_all(db, filters={}, offset=0, limit=2, sort_by="record_id")
        page2 = repo.get_all(db, filters={}, offset=2, limit=2, sort_by="record_id")

        assert len(page1) == 2
        assert len(page2) == 2
        page1_ids = {d.record_id for d in page1}
        page2_ids = {d.record_id for d in page2}
        assert len(page1_ids & page2_ids) == 0

    def test_update_workout_details(self, db: Session, detail_repo: EventRecordDetailRepository) -> None:
        """Test updating workout details."""
        # Arrange
        workout_details = WorkoutDetailsFactory(heart_rate_avg=Decimal("140.0"), steps_count=5000)
        update_data = EventRecordDetailUpdate(heart_rate_avg=Decimal("155.0"), steps_count=10000)

        # Act
        result = detail_repo.update(db, workout_details, update_data)

        # Assert (using getattr for polymorphic attributes)
        assert getattr(result, "heart_rate_avg") == Decimal("155.0")
        assert getattr(result, "steps_count") == 10000

        # Verify in database
        db.expire_all()
        updated = detail_repo.get_by_record_id(db, workout_details.record_id)
        assert updated is not None
        assert getattr(updated, "heart_rate_avg") == Decimal("155.0")
        assert getattr(updated, "steps_count") == 10000

    def test_update_partial_fields(self, db: Session, detail_repo: EventRecordDetailRepository) -> None:
        """Test updating only some fields."""
        # Arrange
        workout_details = WorkoutDetailsFactory(
            heart_rate_avg=Decimal("140.0"),
            heart_rate_max=180,
            steps_count=5000,
        )
        update_data = EventRecordDetailUpdate(heart_rate_avg=Decimal("150.0"))

        # Act
        result = detail_repo.update(db, workout_details, update_data)

        # Assert (using getattr for polymorphic attributes)
        assert getattr(result, "heart_rate_avg") == Decimal("150.0")
        assert getattr(result, "heart_rate_max") == 180  # Unchanged
        assert getattr(result, "steps_count") == 5000  # Unchanged

    def test_delete_workout_details(self, db: Session, detail_repo: EventRecordDetailRepository) -> None:
        """Test deleting workout details."""
        # Arrange
        workout_details = WorkoutDetailsFactory()
        record_id = workout_details.record_id

        # Act
        detail_repo.delete(db, workout_details)

        # Assert
        db.expire_all()
        deleted = detail_repo.get_by_record_id(db, record_id)
        assert deleted is None

    def test_polymorphic_inheritance_behavior(
        self,
        db: Session,
        detail_repo: EventRecordDetailRepository,
        sleep_detail_repo: EventRecordDetailRepository,
    ) -> None:
        """Test that polymorphic inheritance correctly returns specific detail types."""
        # Arrange
        workout_details = WorkoutDetailsFactory(heart_rate_avg=Decimal("150.0"))
        sleep_details = SleepDetailsFactory(sleep_total_duration_minutes=420)

        # Act - each repo queries its own table
        workout_result = detail_repo.get_by_record_id(db, workout_details.record_id)
        sleep_result = sleep_detail_repo.get_by_record_id(db, sleep_details.record_id)

        # Assert - should return specific types, not base class
        assert isinstance(workout_result, WorkoutDetails)
        assert not isinstance(workout_result, SleepDetails)
        assert workout_result.heart_rate_avg == Decimal("150.0")

        assert isinstance(sleep_result, SleepDetails)
        assert not isinstance(sleep_result, WorkoutDetails)
        assert sleep_result.sleep_total_duration_minutes == 420


class TestDetailTypeRegistry:
    """Guard tests keeping the DetailType literal, the DETAIL_MODELS registry and
    the model classes as a single source of truth. A new detail subtype only needs
    a model (with its ``detail_type`` ClassVar) plus a DetailType member; these
    tests fail if the two ever drift apart."""

    def test_registry_matches_detail_type_literal(self) -> None:
        assert set(DETAIL_MODELS) == set(get_args(DetailType))

    def test_registry_covers_every_subclass(self) -> None:
        assert set(DETAIL_MODELS.values()) == set(EventRecordDetail.__subclasses__())

    def test_each_model_declares_matching_detail_type(self) -> None:
        for detail_type, model in DETAIL_MODELS.items():
            assert model.detail_type == detail_type
