"""Tests for DeviceTypePriorityRepository."""

import pytest
from sqlalchemy.orm import Session

from app.repositories.device_type_priority_repository import DeviceTypePriorityRepository
from app.schemas.device_type import DeviceType


class TestDeviceTypePriorityRepository:
    """Test DeviceTypePriorityRepository methods."""

    @pytest.fixture
    def repo(self) -> DeviceTypePriorityRepository:
        """Create DeviceTypePriorityRepository instance."""
        return DeviceTypePriorityRepository()

    @pytest.fixture
    def seeded_priorities(self, db: Session, repo: DeviceTypePriorityRepository) -> None:
        """Seed device type priorities for testing."""
        repo.upsert(db, DeviceType.WATCH, 1)
        repo.upsert(db, DeviceType.BAND, 2)
        repo.upsert(db, DeviceType.RING, 3)
        repo.upsert(db, DeviceType.PHONE, 4)
        repo.upsert(db, DeviceType.SCALE, 5)
        repo.upsert(db, DeviceType.OTHER, 6)
        db.commit()

    def test_upsert_creates_new_priority(self, db: Session, repo: DeviceTypePriorityRepository) -> None:
        """Should create a new device type priority."""
        # Act
        priority = repo.upsert(db, DeviceType.WATCH, 1)

        # Assert
        assert priority is not None
        assert priority.device_type == DeviceType.WATCH.value
        assert priority.priority == 1

        # Verify in database
        db_priority = repo.get_by_device_type(db, DeviceType.WATCH)
        assert db_priority is not None
        assert db_priority.device_type == DeviceType.WATCH.value

    def test_upsert_updates_existing_priority(self, db: Session, repo: DeviceTypePriorityRepository) -> None:
        """Should update existing device type priority."""
        # Arrange - create initial priority
        initial = repo.upsert(db, DeviceType.BAND, 2)
        db.commit()

        # Act - update with new priority
        updated = repo.upsert(db, DeviceType.BAND, 10)

        # Assert
        assert updated.device_type == DeviceType.BAND.value
        assert updated.priority == 10
        assert updated.id == initial.id  # Same record updated

    def test_get_all_returns_seeded_priorities(
        self, db: Session, repo: DeviceTypePriorityRepository, seeded_priorities: None
    ) -> None:
        """Should return all device type priorities ordered by priority."""
        # Act
        all_priorities = repo.get_all_ordered(db)

        # Assert
        assert len(all_priorities) >= 3

        # Check that device types are present
        device_types = [p.device_type for p in all_priorities]
        assert DeviceType.WATCH.value in device_types
        assert DeviceType.BAND.value in device_types
        assert DeviceType.RING.value in device_types

        # Verify ordering by priority (ascending)
        priorities_values = [p.priority for p in all_priorities]
        assert priorities_values == sorted(priorities_values)

    def test_get_by_device_type(self, db: Session, repo: DeviceTypePriorityRepository, seeded_priorities: None) -> None:
        """Should retrieve priority for specific device type."""
        # Act
        watch_priority = repo.get_by_device_type(db, DeviceType.WATCH)

        # Assert
        assert watch_priority is not None
        assert watch_priority.device_type == DeviceType.WATCH.value
        assert isinstance(watch_priority.priority, int)

    def test_get_by_device_type_returns_none_if_not_exists(
        self, db: Session, repo: DeviceTypePriorityRepository
    ) -> None:
        """Should return None if device type priority doesn't exist."""
        # Act
        priority = repo.get_by_device_type(db, DeviceType.WATCH)

        # Assert
        assert priority is None

    def test_priorities_are_unique_per_device_type(
        self, db: Session, repo: DeviceTypePriorityRepository, seeded_priorities: None
    ) -> None:
        """Should have only one priority record per device type."""
        # Act
        all_priorities = repo.get_all_ordered(db)

        # Assert - check uniqueness
        device_types = [p.device_type for p in all_priorities]
        assert len(device_types) == len(set(device_types))

    def test_watch_has_highest_priority(
        self, db: Session, repo: DeviceTypePriorityRepository, seeded_priorities: None
    ) -> None:
        """Watch should have the highest priority (lowest number)."""
        # Act
        all_priorities = repo.get_all_ordered(db)

        # Assert
        watch_priority = next(p for p in all_priorities if p.device_type == DeviceType.WATCH.value)
        other_priorities = [p.priority for p in all_priorities if p.device_type != DeviceType.WATCH.value]

        if other_priorities:
            assert watch_priority.priority <= min(other_priorities)

    def test_get_priority_order_returns_mapping(
        self, db: Session, repo: DeviceTypePriorityRepository, seeded_priorities: None
    ) -> None:
        """Should return a mapping of device types to priorities."""
        # Act
        priority_order = repo.get_priority_order(db)

        # Assert
        assert isinstance(priority_order, dict)
        assert DeviceType.WATCH in priority_order
        assert DeviceType.BAND in priority_order
        assert priority_order[DeviceType.WATCH] == 1
        assert priority_order[DeviceType.BAND] == 2
