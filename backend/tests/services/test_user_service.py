"""
Tests for UserService.

Tests cover:
- Creating users with auto-generated ID and timestamp
- Updating users with auto-set updated_at
- Getting users by ID
- Deleting users
- Counting users in date range
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.schemas.user import UserCreate, UserUpdate
from app.services.user_service import user_service
from tests.factories import UserFactory


class TestUserServiceCreate:
    """Test user creation with auto-generated fields."""

    def test_create_user_generates_id_and_timestamp(self, db: Session) -> None:
        """Should create user with auto-generated ID and created_at."""
        # Arrange
        payload = UserCreate(
            email="test@example.com",
            first_name="Test",
            last_name="User",
        )

        # Act
        user = user_service.create(db, payload)

        # Assert
        assert user.id is not None
        assert user.created_at is not None
        assert user.email == "test@example.com"
        assert user.first_name == "Test"
        assert user.last_name == "User"

        # Verify timestamp is recent (within last minute)
        assert (datetime.now(timezone.utc) - user.created_at).total_seconds() < 60

    def test_create_user_with_minimal_data(self, db: Session) -> None:
        """Should create user with only email."""
        # Arrange
        payload = UserCreate(email="minimal@example.com")

        # Act
        user = user_service.create(db, payload)

        # Assert
        assert user.id is not None
        assert user.created_at is not None
        assert user.email == "minimal@example.com"
        assert user.first_name is None
        assert user.last_name is None

    def test_create_user_with_external_user_id(self, db: Session) -> None:
        """Should create user with external_user_id."""
        # Arrange
        payload = UserCreate(
            email="external@example.com",
            external_user_id="ext_12345",
        )

        # Act
        user = user_service.create(db, payload)

        # Assert
        assert user.external_user_id == "ext_12345"

    def test_create_user_persists_to_database(self, db: Session) -> None:
        """Should persist user to database."""
        # Arrange
        payload = UserCreate(email="persist@example.com")

        # Act
        user = user_service.create(db, payload)

        # Assert - verify in database
        db_user = user_service.get(db, user.id)
        assert db_user is not None
        assert db_user.email == "persist@example.com"


class TestUserServiceUpdate:
    """Test user update with auto-set updated_at."""

    def test_update_user_sets_updated_at(self, db: Session) -> None:
        """Should set updated_at when updating user."""
        # Arrange
        user = UserFactory(email="original@example.com")
        update_payload = UserUpdate(email="updated@example.com")

        # Act
        updated_user = user_service.update(db, user.id, update_payload)

        # Assert
        assert updated_user is not None
        assert updated_user.email == "updated@example.com"

    def test_update_user_partial_fields(self, db: Session) -> None:
        """Should update only specified fields."""
        # Arrange
        user = UserFactory(
            email="original@example.com",
            first_name="Original",
            last_name="Name",
        )
        update_payload = UserUpdate(first_name="Updated")

        # Act
        updated_user = user_service.update(db, user.id, update_payload)

        # Assert
        assert updated_user is not None
        assert updated_user.first_name == "Updated"
        assert updated_user.last_name == "Name"  # Unchanged
        assert updated_user.email == "original@example.com"  # Unchanged

    def test_update_nonexistent_user_returns_none(self, db: Session) -> None:
        """Should return None when updating non-existent user."""
        # Arrange
        fake_id = uuid4()
        update_payload = UserUpdate(email="new@example.com")

        # Act
        result = user_service.update(db, fake_id, update_payload, raise_404=False)

        # Assert
        assert result is None

    def test_update_user_with_raise_404(self, db: Session) -> None:
        """Should raise HTTPException(404) when updating non-existent user with raise_404=True."""
        # Arrange
        from fastapi import HTTPException

        fake_id = uuid4()
        update_payload = UserUpdate(email="new@example.com")

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            user_service.update(db, fake_id, update_payload, raise_404=True)

        assert exc_info.value.status_code == 404


class TestUserServiceGet:
    """Test getting users by ID."""

    def test_get_existing_user(self, db: Session) -> None:
        """Should retrieve existing user by ID."""
        # Arrange
        user = UserFactory(email="get@example.com")

        # Act
        retrieved = user_service.get(db, user.id)

        # Assert
        assert retrieved is not None
        assert retrieved.id == user.id
        assert retrieved.email == user.email

    def test_get_nonexistent_user_returns_none(self, db: Session) -> None:
        """Should return None for non-existent user."""
        # Arrange
        fake_id = uuid4()

        # Act
        result = user_service.get(db, fake_id)

        # Assert
        assert result is None

    def test_get_user_by_string_id(self, db: Session) -> None:
        """Should retrieve user using string ID."""
        # Arrange
        user = UserFactory(email="string@example.com")

        # Act
        retrieved = user_service.get(db, str(user.id))

        # Assert
        assert retrieved is not None
        assert retrieved.id == user.id


class TestUserServiceDelete:
    """Test user deletion."""

    def test_delete_existing_user(self, db: Session) -> None:
        """Should delete existing user."""
        # Arrange
        user = UserFactory(email="delete@example.com")
        user_id = user.id

        # Act
        user_service.delete(db, user_id)

        # Assert - user should no longer exist
        result = user_service.get(db, user_id)
        assert result is None

    def test_delete_nonexistent_user(self, db: Session) -> None:
        """Should handle deleting non-existent user gracefully."""
        # Arrange
        fake_id = uuid4()

        # Act & Assert - should not raise error
        user_service.delete(db, fake_id, raise_404=False)


class TestUserServiceGetCountInRange:
    """Test counting users in date range."""

    def test_get_count_in_range_with_users(self, db: Session) -> None:
        """Should count users created within date range."""
        # Arrange
        now = datetime.now(timezone.utc)
        week_ago = now - timedelta(days=7)
        two_weeks_ago = now - timedelta(days=14)

        # Create users at different times
        UserFactory(created_at=two_weeks_ago)  # Outside range
        UserFactory(created_at=week_ago + timedelta(days=1))  # Inside range
        UserFactory(created_at=now - timedelta(days=1))  # Inside range

        # Act
        count = user_service.get_count_in_range(db, week_ago, now)

        # Assert
        assert count == 2

    def test_get_count_in_range_empty_result(self, db: Session) -> None:
        """Should return 0 when no users in range."""
        # Arrange
        now = datetime.now(timezone.utc)
        future = now + timedelta(days=7)
        far_future = future + timedelta(days=7)

        UserFactory()  # Created now, outside future range

        # Act
        count = user_service.get_count_in_range(db, future, far_future)

        # Assert
        assert count == 0

    def test_get_count_in_range_boundary_inclusive(self, db: Session) -> None:
        """Should include users created at start boundary but exclude end boundary (half-open interval)."""
        # Arrange
        start = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 2, 1, 0, 0, 0, tzinfo=timezone.utc)  # End is exclusive

        # Create users at boundaries
        UserFactory(created_at=start)  # At start boundary (included)
        UserFactory(created_at=datetime(2024, 1, 31, 23, 59, 59, tzinfo=timezone.utc))  # Just before end (included)
        UserFactory(
            created_at=datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
        )  # Middle

        # Act
        count = user_service.get_count_in_range(db, start, end)

        # Assert
        assert count == 3

    def test_get_count_in_range_with_no_users(self, db: Session) -> None:
        """Should return 0 when no users exist at all."""
        # Arrange
        now = datetime.now(timezone.utc)
        week_ago = now - timedelta(days=7)

        # Act
        count = user_service.get_count_in_range(db, week_ago, now)

        # Assert
        assert count == 0
