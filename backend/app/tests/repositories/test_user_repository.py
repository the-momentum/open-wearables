"""
Tests for UserRepository.

Tests cover:
- CRUD operations (create, get, get_all, update, delete)
- Count queries (get_total_count, get_count_in_range)
- Filtering and pagination
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.models import User
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserCreateInternal, UserUpdateInternal
from app.tests.utils.factories import create_user


class TestUserRepository:
    """Test suite for UserRepository."""

    @pytest.fixture
    def user_repo(self) -> UserRepository:
        """Create UserRepository instance."""
        return UserRepository(User)

    def test_create(self, db: Session, user_repo: UserRepository):
        """Test creating a new user."""
        # Arrange
        user_data = UserCreateInternal(
            id=uuid4(),
            created_at=datetime.now(timezone.utc),
            email="test@example.com",
            first_name="John",
            last_name="Doe",
            external_user_id="ext_123",
        )

        # Act
        result = user_repo.create(db, user_data)

        # Assert
        assert result.id == user_data.id
        assert result.email == "test@example.com"
        assert result.first_name == "John"
        assert result.last_name == "Doe"
        assert result.external_user_id == "ext_123"

        # Verify in database
        db.expire_all()
        db_user = user_repo.get(db, user_data.id)
        assert db_user is not None
        assert db_user.email == "test@example.com"

    def test_create_minimal_fields(self, db: Session, user_repo: UserRepository):
        """Test creating a user with only required fields."""
        # Arrange
        user_data = UserCreateInternal(
            id=uuid4(),
            created_at=datetime.now(timezone.utc),
        )

        # Act
        result = user_repo.create(db, user_data)

        # Assert
        assert result.id == user_data.id
        assert result.email is None
        assert result.first_name is None
        assert result.last_name is None
        assert result.external_user_id is None

    def test_get(self, db: Session, user_repo: UserRepository):
        """Test retrieving a user by ID."""
        # Arrange
        user = create_user(db, email="test@example.com", first_name="Jane")

        # Act
        result = user_repo.get(db, user.id)

        # Assert
        assert result is not None
        assert result.id == user.id
        assert result.email == "test@example.com"
        assert result.first_name == "Jane"

    def test_get_nonexistent(self, db: Session, user_repo: UserRepository):
        """Test retrieving a nonexistent user returns None."""
        # Act
        result = user_repo.get(db, uuid4())

        # Assert
        assert result is None

    def test_get_all(self, db: Session, user_repo: UserRepository):
        """Test listing all users."""
        # Arrange
        user1 = create_user(db, email="user1@example.com")
        user2 = create_user(db, email="user2@example.com")
        user3 = create_user(db, email="user3@example.com")

        # Act
        results = user_repo.get_all(db, filters={}, offset=0, limit=10, sort_by=None)

        # Assert
        assert len(results) >= 3
        user_ids = [u.id for u in results]
        assert user1.id in user_ids
        assert user2.id in user_ids
        assert user3.id in user_ids

    def test_get_all_with_email_filter(self, db: Session, user_repo: UserRepository):
        """Test filtering users by email."""
        # Arrange
        user1 = create_user(db, email="test1@example.com")
        create_user(db, email="test2@example.com")
        create_user(db, email="test3@example.com")

        # Act
        results = user_repo.get_all(
            db,
            filters={"email": "test1@example.com"},
            offset=0,
            limit=10,
            sort_by=None,
        )

        # Assert
        assert len(results) == 1
        assert results[0].email == "test1@example.com"
        assert results[0].id == user1.id

    def test_get_all_with_pagination(self, db: Session, user_repo: UserRepository):
        """Test pagination with offset and limit."""
        # Arrange
        for i in range(5):
            create_user(db, email=f"user{i}@example.com")

        # Act - Get first 2 users
        page1 = user_repo.get_all(db, filters={}, offset=0, limit=2, sort_by=None)

        # Act - Get next 2 users
        page2 = user_repo.get_all(db, filters={}, offset=2, limit=2, sort_by=None)

        # Assert
        assert len(page1) == 2
        assert len(page2) == 2
        # Verify different results
        page1_ids = {u.id for u in page1}
        page2_ids = {u.id for u in page2}
        assert len(page1_ids & page2_ids) == 0  # No overlap

    def test_get_all_with_sort(self, db: Session, user_repo: UserRepository):
        """Test sorting users by a field."""
        # Arrange
        create_user(db, email="charlie@example.com", first_name="Charlie")
        create_user(db, email="alice@example.com", first_name="Alice")
        create_user(db, email="bob@example.com", first_name="Bob")

        # Act
        results = user_repo.get_all(db, filters={}, offset=0, limit=10, sort_by="first_name")

        # Assert
        assert len(results) >= 3
        # Verify alphabetical order (at least for our test users)
        first_names = [u.first_name for u in results if u.first_name in ["Alice", "Bob", "Charlie"]]
        assert first_names == sorted(first_names)

    def test_update(self, db: Session, user_repo: UserRepository):
        """Test updating an existing user."""
        # Arrange
        user = create_user(db, first_name="Original", last_name="Name")
        update_data = UserUpdateInternal(
            first_name="Updated",
            last_name="NewName",
        )

        # Act
        result = user_repo.update(db, user, update_data)

        # Assert
        assert result.first_name == "Updated"
        assert result.last_name == "NewName"

        # Verify in database
        db.expire_all()
        db_user = user_repo.get(db, user.id)
        assert db_user.first_name == "Updated"
        assert db_user.last_name == "NewName"

    def test_update_partial(self, db: Session, user_repo: UserRepository):
        """Test updating only some fields."""
        # Arrange
        user = create_user(db, email="old@example.com", first_name="John", last_name="Doe")
        update_data = UserUpdateInternal(email="new@example.com")

        # Act
        result = user_repo.update(db, user, update_data)

        # Assert
        assert result.email == "new@example.com"
        assert result.first_name == "John"  # Unchanged
        assert result.last_name == "Doe"  # Unchanged

    def test_delete(self, db: Session, user_repo: UserRepository):
        """Test deleting a user."""
        # Arrange
        user = create_user(db)
        user_id = user.id

        # Act
        user_repo.delete(db, user)

        # Assert
        db.expire_all()
        deleted_user = user_repo.get(db, user_id)
        assert deleted_user is None

    def test_get_total_count(self, db: Session, user_repo: UserRepository):
        """Test counting total users."""
        # Arrange
        initial_count = user_repo.get_total_count(db)
        create_user(db)
        create_user(db)
        create_user(db)

        # Act
        result = user_repo.get_total_count(db)

        # Assert
        assert result == initial_count + 3

    def test_get_count_in_range(self, db: Session, user_repo: UserRepository):
        """Test counting users created within a date range."""
        # Arrange
        now = datetime.now(timezone.utc)
        two_days_ago = now - timedelta(days=2)
        one_day_ago = now - timedelta(days=1)
        now + timedelta(days=1)

        # Create users at different times
        create_user(db, created_at=two_days_ago)
        create_user(db, created_at=one_day_ago)
        create_user(db, created_at=one_day_ago)
        create_user(db, created_at=now)

        # Act - Count users created yesterday
        result = user_repo.get_count_in_range(db, one_day_ago, now)

        # Assert
        assert result == 2  # Two users created on one_day_ago

    def test_get_count_in_range_empty(self, db: Session, user_repo: UserRepository):
        """Test counting users in a range with no results."""
        # Arrange
        now = datetime.now(timezone.utc)
        future_start = now + timedelta(days=10)
        future_end = now + timedelta(days=20)

        create_user(db)

        # Act
        result = user_repo.get_count_in_range(db, future_start, future_end)

        # Assert
        assert result == 0

    def test_get_count_in_range_inclusive_start(self, db: Session, user_repo: UserRepository):
        """Test that start date is inclusive."""
        # Arrange
        now = datetime.now(timezone.utc)
        tomorrow = now + timedelta(days=1)

        create_user(db, created_at=now)

        # Act
        result = user_repo.get_count_in_range(db, now, tomorrow)

        # Assert
        assert result >= 1  # Should include user created at exact start time

    def test_get_count_in_range_exclusive_end(self, db: Session, user_repo: UserRepository):
        """Test that end date is exclusive."""
        # Arrange
        now = datetime.now(timezone.utc)
        tomorrow = now + timedelta(days=1)

        create_user(db, created_at=tomorrow)

        # Act
        result = user_repo.get_count_in_range(db, now, tomorrow)

        # Assert
        assert result == 0  # Should NOT include user created at exact end time

    def test_multiple_filters(self, db: Session, user_repo: UserRepository):
        """Test filtering with multiple criteria."""
        # Arrange
        create_user(db, email="test@example.com", first_name="John")
        create_user(db, email="other@example.com", first_name="John")
        create_user(db, email="test@example.com", first_name="Jane")

        # Act
        results = user_repo.get_all(
            db,
            filters={"email": "test@example.com", "first_name": "John"},
            offset=0,
            limit=10,
            sort_by=None,
        )

        # Assert
        assert len(results) == 1
        assert results[0].email == "test@example.com"
        assert results[0].first_name == "John"
