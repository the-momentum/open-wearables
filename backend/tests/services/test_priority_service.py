"""
Tests for PriorityService.

Tests cover:
- Getting provider priorities
- Updating individual provider priority (with commit)
- Bulk updating provider priorities (with commit)
- Getting device type priorities
- Updating individual device type priority (with commit)
- Bulk updating device type priorities (with commit)
"""

from logging import getLogger
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from app.schemas.device_type import DeviceType
from app.schemas.device_type_priority import DeviceTypePriorityBase, DeviceTypePriorityBulkUpdate
from app.schemas.oauth import ProviderName
from app.schemas.provider_priority import ProviderPriorityBase, ProviderPriorityBulkUpdate
from app.services.priority_service import PriorityService


@pytest.fixture
def priority_service() -> PriorityService:
    """Create PriorityService instance."""
    return PriorityService(log=getLogger(__name__))


class TestPriorityServiceGetProviderPriorities:
    """Test getting provider priorities."""

    @pytest.mark.asyncio
    async def test_get_provider_priorities_empty(self, db: Session, priority_service: PriorityService) -> None:
        """Should return empty list when no priorities exist."""
        result = await priority_service.get_provider_priorities(db)
        assert result.items == []

    @pytest.mark.asyncio
    async def test_get_provider_priorities_ordered(self, db: Session, priority_service: PriorityService) -> None:
        """Should return priorities ordered by priority value."""
        # Arrange - create priorities in non-sequential order
        await priority_service.update_provider_priority(db, ProviderName.GARMIN, 2)
        await priority_service.update_provider_priority(db, ProviderName.APPLE, 1)
        await priority_service.update_provider_priority(db, ProviderName.POLAR, 3)

        # Act
        result = await priority_service.get_provider_priorities(db)

        # Assert
        assert len(result.items) == 3
        assert result.items[0].provider == ProviderName.APPLE
        assert result.items[0].priority == 1
        assert result.items[1].provider == ProviderName.GARMIN
        assert result.items[1].priority == 2
        assert result.items[2].provider == ProviderName.POLAR
        assert result.items[2].priority == 3


class TestPriorityServiceUpdateProviderPriority:
    """Test updating individual provider priority."""

    @pytest.mark.asyncio
    async def test_update_provider_priority_creates_new(self, db: Session, priority_service: PriorityService) -> None:
        """Should create new priority if it doesn't exist."""
        result = await priority_service.update_provider_priority(db, ProviderName.APPLE, 1)

        assert result.provider == ProviderName.APPLE
        assert result.priority == 1

    @pytest.mark.asyncio
    async def test_update_provider_priority_updates_existing(
        self, db: Session, priority_service: PriorityService
    ) -> None:
        """Should update existing priority."""
        # Arrange
        await priority_service.update_provider_priority(db, ProviderName.APPLE, 1)

        # Act
        result = await priority_service.update_provider_priority(db, ProviderName.APPLE, 5)

        # Assert
        assert result.provider == ProviderName.APPLE
        assert result.priority == 5

    @pytest.mark.asyncio
    async def test_update_provider_priority_commits_transaction(
        self, db: Session, priority_service: PriorityService
    ) -> None:
        """Should commit transaction after update."""
        # Arrange
        mock_commit = MagicMock()
        original_commit = db.commit
        db.commit = mock_commit

        try:
            # Act
            await priority_service.update_provider_priority(db, ProviderName.APPLE, 1)

            # Assert
            mock_commit.assert_called_once()
        finally:
            db.commit = original_commit


class TestPriorityServiceBulkUpdateProviderPriorities:
    """Test bulk updating provider priorities."""

    @pytest.mark.asyncio
    async def test_bulk_update_creates_new_priorities(self, db: Session, priority_service: PriorityService) -> None:
        """Should create new priorities for all items."""
        update = ProviderPriorityBulkUpdate(
            priorities=[
                ProviderPriorityBase(provider=ProviderName.APPLE, priority=1),
                ProviderPriorityBase(provider=ProviderName.GARMIN, priority=2),
                ProviderPriorityBase(provider=ProviderName.POLAR, priority=3),
            ]
        )

        result = await priority_service.bulk_update_priorities(db, update)

        assert len(result.items) == 3

    @pytest.mark.asyncio
    async def test_bulk_update_updates_existing_priorities(
        self, db: Session, priority_service: PriorityService
    ) -> None:
        """Should update existing priorities."""
        # Arrange - create initial priorities
        initial_update = ProviderPriorityBulkUpdate(
            priorities=[
                ProviderPriorityBase(provider=ProviderName.APPLE, priority=1),
                ProviderPriorityBase(provider=ProviderName.GARMIN, priority=2),
            ]
        )
        await priority_service.bulk_update_priorities(db, initial_update)

        # Act - swap priorities
        swap_update = ProviderPriorityBulkUpdate(
            priorities=[
                ProviderPriorityBase(provider=ProviderName.APPLE, priority=2),
                ProviderPriorityBase(provider=ProviderName.GARMIN, priority=1),
            ]
        )
        result = await priority_service.bulk_update_priorities(db, swap_update)

        # Assert - should be ordered by priority
        assert len(result.items) == 2
        assert result.items[0].provider == ProviderName.GARMIN
        assert result.items[0].priority == 1
        assert result.items[1].provider == ProviderName.APPLE
        assert result.items[1].priority == 2

    @pytest.mark.asyncio
    async def test_bulk_update_commits_transaction(self, db: Session, priority_service: PriorityService) -> None:
        """Should commit transaction after bulk update.

        This is the critical test that would have caught the missing commit bug.
        """
        # Arrange
        mock_commit = MagicMock()
        original_commit = db.commit
        db.commit = mock_commit

        update = ProviderPriorityBulkUpdate(
            priorities=[
                ProviderPriorityBase(provider=ProviderName.APPLE, priority=1),
                ProviderPriorityBase(provider=ProviderName.GARMIN, priority=2),
            ]
        )

        try:
            # Act
            await priority_service.bulk_update_priorities(db, update)

            # Assert
            mock_commit.assert_called_once()
        finally:
            db.commit = original_commit

    @pytest.mark.asyncio
    async def test_bulk_update_persists_to_database(self, db: Session, priority_service: PriorityService) -> None:
        """Should persist changes to database so they survive session refresh."""
        # Arrange
        update = ProviderPriorityBulkUpdate(
            priorities=[
                ProviderPriorityBase(provider=ProviderName.APPLE, priority=3),
                ProviderPriorityBase(provider=ProviderName.GARMIN, priority=1),
                ProviderPriorityBase(provider=ProviderName.POLAR, priority=2),
            ]
        )

        # Act
        await priority_service.bulk_update_priorities(db, update)

        # Clear session cache to force re-fetch from database
        db.expire_all()

        # Assert - verify data persisted correctly
        result = await priority_service.get_provider_priorities(db)
        assert len(result.items) == 3
        # Should be ordered by priority
        assert result.items[0].provider == ProviderName.GARMIN
        assert result.items[0].priority == 1
        assert result.items[1].provider == ProviderName.POLAR
        assert result.items[1].priority == 2
        assert result.items[2].provider == ProviderName.APPLE
        assert result.items[2].priority == 3


class TestPriorityServiceGetDeviceTypePriorities:
    """Test getting device type priorities."""

    @pytest.mark.asyncio
    async def test_get_device_type_priorities_empty(self, db: Session, priority_service: PriorityService) -> None:
        """Should return empty list when no priorities exist."""
        result = await priority_service.get_device_type_priorities(db)
        assert result.items == []

    @pytest.mark.asyncio
    async def test_get_device_type_priorities_ordered(self, db: Session, priority_service: PriorityService) -> None:
        """Should return priorities ordered by priority value."""
        # Arrange
        await priority_service.update_device_type_priority(db, DeviceType.BAND, 2)
        await priority_service.update_device_type_priority(db, DeviceType.WATCH, 1)
        await priority_service.update_device_type_priority(db, DeviceType.RING, 3)

        # Act
        result = await priority_service.get_device_type_priorities(db)

        # Assert
        assert len(result.items) == 3
        assert result.items[0].device_type == DeviceType.WATCH
        assert result.items[0].priority == 1
        assert result.items[1].device_type == DeviceType.BAND
        assert result.items[1].priority == 2
        assert result.items[2].device_type == DeviceType.RING
        assert result.items[2].priority == 3


class TestPriorityServiceUpdateDeviceTypePriority:
    """Test updating individual device type priority."""

    @pytest.mark.asyncio
    async def test_update_device_type_priority_creates_new(
        self, db: Session, priority_service: PriorityService
    ) -> None:
        """Should create new priority if it doesn't exist."""
        result = await priority_service.update_device_type_priority(db, DeviceType.WATCH, 1)

        assert result.device_type == DeviceType.WATCH
        assert result.priority == 1

    @pytest.mark.asyncio
    async def test_update_device_type_priority_commits_transaction(
        self, db: Session, priority_service: PriorityService
    ) -> None:
        """Should commit transaction after update."""
        mock_commit = MagicMock()
        original_commit = db.commit
        db.commit = mock_commit

        try:
            await priority_service.update_device_type_priority(db, DeviceType.WATCH, 1)
            mock_commit.assert_called_once()
        finally:
            db.commit = original_commit


class TestPriorityServiceBulkUpdateDeviceTypePriorities:
    """Test bulk updating device type priorities."""

    @pytest.mark.asyncio
    async def test_bulk_update_device_types_creates_new(self, db: Session, priority_service: PriorityService) -> None:
        """Should create new priorities for all items."""
        update = DeviceTypePriorityBulkUpdate(
            priorities=[
                DeviceTypePriorityBase(device_type=DeviceType.WATCH, priority=1),
                DeviceTypePriorityBase(device_type=DeviceType.BAND, priority=2),
                DeviceTypePriorityBase(device_type=DeviceType.RING, priority=3),
            ]
        )

        result = await priority_service.bulk_update_device_type_priorities(db, update)

        assert len(result.items) == 3

    @pytest.mark.asyncio
    async def test_bulk_update_device_types_commits_transaction(
        self, db: Session, priority_service: PriorityService
    ) -> None:
        """Should commit transaction after bulk update."""
        mock_commit = MagicMock()
        original_commit = db.commit
        db.commit = mock_commit

        update = DeviceTypePriorityBulkUpdate(
            priorities=[
                DeviceTypePriorityBase(device_type=DeviceType.WATCH, priority=1),
                DeviceTypePriorityBase(device_type=DeviceType.BAND, priority=2),
            ]
        )

        try:
            await priority_service.bulk_update_device_type_priorities(db, update)
            mock_commit.assert_called_once()
        finally:
            db.commit = original_commit

    @pytest.mark.asyncio
    async def test_bulk_update_device_types_persists_to_database(
        self, db: Session, priority_service: PriorityService
    ) -> None:
        """Should persist changes to database so they survive session refresh."""
        update = DeviceTypePriorityBulkUpdate(
            priorities=[
                DeviceTypePriorityBase(device_type=DeviceType.WATCH, priority=2),
                DeviceTypePriorityBase(device_type=DeviceType.RING, priority=1),
            ]
        )

        await priority_service.bulk_update_device_type_priorities(db, update)

        # Clear session cache
        db.expire_all()

        # Verify data persisted
        result = await priority_service.get_device_type_priorities(db)
        assert len(result.items) == 2
        assert result.items[0].device_type == DeviceType.RING
        assert result.items[0].priority == 1
        assert result.items[1].device_type == DeviceType.WATCH
        assert result.items[1].priority == 2
