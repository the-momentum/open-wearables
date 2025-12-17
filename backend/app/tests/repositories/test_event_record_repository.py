"""
Tests for EventRecordRepository.

Tests cover:
- CRUD operations with external mapping integration
- get_records_with_filters with complex filtering
- Filtering by category, type, device, provider, date range, duration
- get_count_by_workout_type aggregation
- Pagination and sorting
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.models import EventRecord
from app.repositories.event_record_repository import EventRecordRepository
from app.schemas.event_record import EventRecordCreate, EventRecordQueryParams
from app.tests.utils.factories import create_event_record, create_external_device_mapping, create_user


class TestEventRecordRepository:
    """Test suite for EventRecordRepository."""

    @pytest.fixture
    def event_repo(self) -> EventRecordRepository:
        """Create EventRecordRepository instance."""
        return EventRecordRepository(EventRecord)

    def test_create_with_existing_mapping(self, db: Session, event_repo: EventRecordRepository) -> None:
        """Test creating an event record with an existing external mapping."""
        # Arrange
        user = create_user(db)
        mapping = create_external_device_mapping(db, user=user, provider_id="apple", device_id="watch123")
        now = datetime.now(timezone.utc)

        event_data = EventRecordCreate(
            id=uuid4(),
            user_id=user.id,
            provider_id="apple",
            device_id="watch123",
            external_mapping_id=mapping.id,
            category="workout",
            type="running",
            source_name="Apple Watch",
            duration_seconds=3600,
            start_datetime=now,
            end_datetime=now + timedelta(seconds=3600),
        )

        # Act
        result = event_repo.create(db, event_data)

        # Assert
        assert result.id == event_data.id
        assert result.external_mapping_id == mapping.id
        assert result.category == "workout"
        assert result.type == "running"
        assert result.duration_seconds == 3600

        # Verify in database
        db.expire_all()
        db_event = event_repo.get(db, event_data.id)
        assert db_event is not None
        assert db_event.external_mapping_id == mapping.id

    def test_create_auto_creates_mapping(self, db: Session, event_repo: EventRecordRepository) -> None:
        """Test that create automatically creates a mapping if it doesn't exist."""
        # Arrange
        user = create_user(db)
        now = datetime.now(timezone.utc)

        event_data = EventRecordCreate(
            id=uuid4(),
            user_id=user.id,
            provider_id="garmin",
            device_id="device456",
            external_mapping_id=None,
            category="workout",
            type="cycling",
            source_name="Garmin Edge",
            duration_seconds=7200,
            start_datetime=now,
            end_datetime=now + timedelta(seconds=7200),
        )

        # Act
        result = event_repo.create(db, event_data)

        # Assert
        assert result.external_mapping_id is not None
        # Verify mapping was created
        from app.models import ExternalDeviceMapping
        from app.repositories.external_mapping_repository import ExternalMappingRepository

        mapping_repo = ExternalMappingRepository(ExternalDeviceMapping)
        mapping = mapping_repo.get(db, result.external_mapping_id)
        assert mapping is not None
        assert mapping.user_id == user.id
        assert mapping.provider_id == "garmin"
        assert mapping.device_id == "device456"

    def test_get(self, db: Session, event_repo: EventRecordRepository) -> None:
        """Test retrieving an event record by ID."""
        # Arrange
        event = create_event_record(db, category="workout", type_="swimming")

        # Act
        result = event_repo.get(db, event.id)

        # Assert
        assert result is not None
        assert result.id == event.id
        assert result.category == "workout"
        assert result.type == "swimming"

    def test_get_records_with_filters_by_category(self, db: Session, event_repo: EventRecordRepository) -> None:
        """Test filtering event records by category."""
        # Arrange
        user = create_user(db)
        mapping = create_external_device_mapping(db, user=user)

        create_event_record(db, mapping=mapping, category="workout", type_="running")
        create_event_record(db, mapping=mapping, category="workout", type_="cycling")
        create_event_record(db, mapping=mapping, category="sleep", type_="deep")

        query_params = EventRecordQueryParams(
            category="workout",
            limit=10,
            offset=0,
        )

        # Act
        results, total_count = event_repo.get_records_with_filters(db, query_params, str(user.id))

        # Assert
        assert total_count == 2
        assert len(results) == 2
        for event, _ in results:
            assert event.category == "workout"

    def test_get_records_with_filters_by_type(self, db: Session, event_repo: EventRecordRepository) -> None:
        """Test filtering event records by type (with ILIKE)."""
        # Arrange
        user = create_user(db)
        mapping = create_external_device_mapping(db, user=user)

        create_event_record(db, mapping=mapping, category="workout", type_="HKWorkoutActivityTypeRunning")
        create_event_record(db, mapping=mapping, category="workout", type_="HKWorkoutActivityTypeCycling")
        create_event_record(db, mapping=mapping, category="workout", type_="running_trail")

        query_params = EventRecordQueryParams(
            category="workout",
            record_type="running",  # Should match both with "running" in name
            limit=10,
            offset=0,
        )

        # Act
        results, total_count = event_repo.get_records_with_filters(db, query_params, str(user.id))

        # Assert
        assert total_count == 2
        for event, _ in results:
            assert "running" in event.type.lower()

    def test_get_records_with_filters_by_device_id(self, db: Session, event_repo: EventRecordRepository) -> None:
        """Test filtering event records by device ID."""
        # Arrange
        user = create_user(db)
        mapping1 = create_external_device_mapping(db, user=user, device_id="device1")
        mapping2 = create_external_device_mapping(db, user=user, device_id="device2")

        create_event_record(db, mapping=mapping1, category="workout")
        create_event_record(db, mapping=mapping1, category="workout")
        create_event_record(db, mapping=mapping2, category="workout")

        query_params = EventRecordQueryParams(
            category="workout",
            device_id="device1",
            limit=10,
            offset=0,
        )

        # Act
        results, total_count = event_repo.get_records_with_filters(db, query_params, str(user.id))

        # Assert
        assert total_count == 2
        for _, mapping in results:
            assert mapping.device_id == "device1"

    def test_get_records_with_filters_by_provider(self, db: Session, event_repo: EventRecordRepository) -> None:
        """Test filtering event records by provider ID."""
        # Arrange
        user = create_user(db)
        mapping_apple = create_external_device_mapping(db, user=user, provider_id="apple")
        mapping_garmin = create_external_device_mapping(db, user=user, provider_id="garmin")

        create_event_record(db, mapping=mapping_apple, category="workout")
        create_event_record(db, mapping=mapping_garmin, category="workout")

        query_params = EventRecordQueryParams(
            category="workout",
            provider_id="apple",
            limit=10,
            offset=0,
        )

        # Act
        results, total_count = event_repo.get_records_with_filters(db, query_params, str(user.id))

        # Assert
        assert total_count == 1
        _, mapping = results[0]
        assert mapping.provider_id == "apple"

    def test_get_records_with_filters_by_date_range(self, db: Session, event_repo: EventRecordRepository) -> None:
        """Test filtering event records by date range."""
        # Arrange
        user = create_user(db)
        mapping = create_external_device_mapping(db, user=user)

        now = datetime.now(timezone.utc)
        yesterday = now - timedelta(days=1)
        two_days_ago = now - timedelta(days=2)

        create_event_record(
            db,
            mapping=mapping,
            start_datetime=two_days_ago,
            end_datetime=two_days_ago + timedelta(hours=1),
        )
        create_event_record(db, mapping=mapping, start_datetime=yesterday, end_datetime=yesterday + timedelta(hours=1))
        create_event_record(db, mapping=mapping, start_datetime=now, end_datetime=now + timedelta(hours=1))

        query_params = EventRecordQueryParams(
            category="workout",
            start_date=yesterday.isoformat(),
            end_date=now.isoformat(),
            limit=10,
            offset=0,
        )

        # Act
        results, total_count = event_repo.get_records_with_filters(db, query_params, str(user.id))

        # Assert
        assert total_count == 1  # Only the one that starts yesterday and ends before now
        event, _ = results[0]
        assert event.start_datetime >= yesterday
        assert event.end_datetime <= now

    def test_get_records_with_filters_by_duration(self, db: Session, event_repo: EventRecordRepository) -> None:
        """Test filtering event records by duration range."""
        # Arrange
        user = create_user(db)
        mapping = create_external_device_mapping(db, user=user)

        create_event_record(db, mapping=mapping, duration_seconds=1800)  # 30 min
        create_event_record(db, mapping=mapping, duration_seconds=3600)  # 60 min
        create_event_record(db, mapping=mapping, duration_seconds=7200)  # 120 min

        query_params = EventRecordQueryParams(
            category="workout",
            min_duration=3000,  # 50 min
            max_duration=6000,  # 100 min
            limit=10,
            offset=0,
        )

        # Act
        results, total_count = event_repo.get_records_with_filters(db, query_params, str(user.id))

        # Assert
        assert total_count == 1
        event, _ = results[0]
        assert event.duration_seconds == 3600

    def test_get_records_with_filters_by_source_name(self, db: Session, event_repo: EventRecordRepository) -> None:
        """Test filtering event records by source name (ILIKE)."""
        # Arrange
        user = create_user(db)
        mapping = create_external_device_mapping(db, user=user)

        create_event_record(db, mapping=mapping, source_name="Apple Watch Series 7")
        create_event_record(db, mapping=mapping, source_name="Apple Watch SE")
        create_event_record(db, mapping=mapping, source_name="Garmin Forerunner")

        query_params = EventRecordQueryParams(
            category="workout",
            source_name="apple watch",
            limit=10,
            offset=0,
        )

        # Act
        results, total_count = event_repo.get_records_with_filters(db, query_params, str(user.id))

        # Assert
        assert total_count == 2
        for event, _ in results:
            assert "apple watch" in event.source_name.lower()

    def test_get_records_with_pagination(self, db: Session, event_repo: EventRecordRepository) -> None:
        """Test pagination of event records."""
        # Arrange
        user = create_user(db)
        mapping = create_external_device_mapping(db, user=user)

        for i in range(5):
            create_event_record(db, mapping=mapping, category="workout")

        # Act - Get first page
        query_params1 = EventRecordQueryParams(category="workout", limit=2, offset=0)
        page1, total_count = event_repo.get_records_with_filters(db, query_params1, str(user.id))

        # Act - Get second page
        query_params2 = EventRecordQueryParams(category="workout", limit=2, offset=2)
        page2, _ = event_repo.get_records_with_filters(db, query_params2, str(user.id))

        # Assert
        assert total_count == 5
        assert len(page1) == 2
        assert len(page2) == 2
        # Verify different results
        page1_ids = {event.id for event, _ in page1}
        page2_ids = {event.id for event, _ in page2}
        assert len(page1_ids & page2_ids) == 0

    def test_get_records_with_sort_by_start_datetime_desc(self, db: Session, event_repo: EventRecordRepository) -> None:
        """Test sorting event records by start_datetime descending (default)."""
        # Arrange
        user = create_user(db)
        mapping = create_external_device_mapping(db, user=user)

        now = datetime.now(timezone.utc)
        event1 = create_event_record(db, mapping=mapping, start_datetime=now - timedelta(days=2))
        event2 = create_event_record(db, mapping=mapping, start_datetime=now - timedelta(days=1))
        event3 = create_event_record(db, mapping=mapping, start_datetime=now)

        query_params = EventRecordQueryParams(
            category="workout",
            sort_by="start_datetime",
            sort_order="desc",
            limit=10,
            offset=0,
        )

        # Act
        results, _ = event_repo.get_records_with_filters(db, query_params, str(user.id))

        # Assert
        assert len(results) >= 3
        # Most recent first
        result_events = [event for event, _ in results]
        assert result_events[0].id == event3.id
        assert result_events[1].id == event2.id
        assert result_events[2].id == event1.id

    def test_get_records_with_sort_by_duration_asc(self, db: Session, event_repo: EventRecordRepository) -> None:
        """Test sorting event records by duration ascending."""
        # Arrange
        user = create_user(db)
        mapping = create_external_device_mapping(db, user=user)

        event1 = create_event_record(db, mapping=mapping, duration_seconds=7200)
        event2 = create_event_record(db, mapping=mapping, duration_seconds=1800)
        event3 = create_event_record(db, mapping=mapping, duration_seconds=3600)

        query_params = EventRecordQueryParams(
            category="workout",
            sort_by="duration_seconds",
            sort_order="asc",
            limit=10,
            offset=0,
        )

        # Act
        results, _ = event_repo.get_records_with_filters(db, query_params, str(user.id))

        # Assert
        assert len(results) >= 3
        result_events = [event for event, _ in results]
        # Shortest duration first
        assert result_events[0].id == event2.id  # 1800
        assert result_events[1].id == event3.id  # 3600
        assert result_events[2].id == event1.id  # 7200

    def test_get_count_by_workout_type(self, db: Session, event_repo: EventRecordRepository) -> None:
        """Test aggregating workout counts by type."""
        # Arrange
        mapping = create_external_device_mapping(db)

        create_event_record(db, mapping=mapping, category="workout", type_="running")
        create_event_record(db, mapping=mapping, category="workout", type_="running")
        create_event_record(db, mapping=mapping, category="workout", type_="running")
        create_event_record(db, mapping=mapping, category="workout", type_="cycling")
        create_event_record(db, mapping=mapping, category="workout", type_="cycling")
        create_event_record(db, mapping=mapping, category="sleep", type_="deep")  # Should be excluded

        # Act
        results = event_repo.get_count_by_workout_type(db)

        # Assert
        # Convert to dict for easier testing
        counts_dict = dict(results)
        assert counts_dict.get("running", 0) >= 3
        assert counts_dict.get("cycling", 0) >= 2
        # Sleep should not be included
        assert "deep" not in counts_dict or counts_dict["deep"] == 0

    def test_get_count_by_workout_type_ordered(self, db: Session, event_repo: EventRecordRepository) -> None:
        """Test that workout type counts are ordered by count descending."""
        # Arrange
        mapping = create_external_device_mapping(db)

        # Create more running than cycling workouts
        for _ in range(5):
            create_event_record(db, mapping=mapping, category="workout", type_="running")
        for _ in range(2):
            create_event_record(db, mapping=mapping, category="workout", type_="cycling")

        # Act
        results = event_repo.get_count_by_workout_type(db)

        # Assert
        # Find our test types
        test_types = [
            (workout_type, count) for workout_type, count in results if workout_type in ["running", "cycling"]
        ]
        assert len(test_types) >= 2
        # Running should come first (higher count)
        running_idx = next(i for i, (t, _) in enumerate(test_types) if t == "running")
        cycling_idx = next(i for i, (t, _) in enumerate(test_types) if t == "cycling")
        assert running_idx < cycling_idx

    def test_get_records_filters_by_user_id(self, db: Session, event_repo: EventRecordRepository) -> None:
        """Test that records are filtered by user ID."""
        # Arrange
        user1 = create_user(db)
        user2 = create_user(db)
        mapping1 = create_external_device_mapping(db, user=user1)
        mapping2 = create_external_device_mapping(db, user=user2)

        create_event_record(db, mapping=mapping1, category="workout")
        create_event_record(db, mapping=mapping1, category="workout")
        create_event_record(db, mapping=mapping2, category="workout")

        query_params = EventRecordQueryParams(category="workout", limit=10, offset=0)

        # Act
        results, total_count = event_repo.get_records_with_filters(db, query_params, str(user1.id))

        # Assert
        assert total_count == 2
        for _, mapping in results:
            assert mapping.user_id == user1.id

    def test_delete(self, db: Session, event_repo: EventRecordRepository) -> None:
        """Test deleting an event record."""
        # Arrange
        event = create_event_record(db)
        event_id = event.id

        # Act
        event_repo.delete(db, event)

        # Assert
        db.expire_all()
        deleted_event = event_repo.get(db, event_id)
        assert deleted_event is None

    def test_complex_filter_combination(self, db: Session, event_repo: EventRecordRepository) -> None:
        """Test combining multiple filters."""
        # Arrange
        user = create_user(db)
        mapping = create_external_device_mapping(db, user=user, provider_id="apple", device_id="watch1")

        now = datetime.now(timezone.utc)
        yesterday = now - timedelta(days=1)

        # Create matching record
        create_event_record(
            db,
            mapping=mapping,
            category="workout",
            type_="running",
            source_name="Apple Watch",
            start_datetime=yesterday,
            end_datetime=yesterday + timedelta(hours=1),
            duration_seconds=3600,
        )

        # Create non-matching records
        create_event_record(db, mapping=mapping, category="sleep")  # Wrong category
        other_mapping = create_external_device_mapping(db, user=user, device_id="watch2")
        create_event_record(db, mapping=other_mapping, category="workout")  # Wrong device

        query_params = EventRecordQueryParams(
            category="workout",
            record_type="running",
            device_id="watch1",
            provider_id="apple",
            source_name="Apple",
            min_duration=3000,
            limit=10,
            offset=0,
        )

        # Act
        results, total_count = event_repo.get_records_with_filters(db, query_params, str(user.id))

        # Assert
        assert total_count == 1
        event, mapping_result = results[0]
        assert event.category == "workout"
        assert "running" in event.type
        assert mapping_result.device_id == "watch1"
