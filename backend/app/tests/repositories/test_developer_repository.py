"""
Tests for DeveloperRepository.

Tests cover:
- CRUD operations (create, get, get_all, update, delete)
- Email filtering
- Pagination and sorting
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.models import Developer
from app.repositories.developer_repository import DeveloperRepository
from app.schemas.developer import DeveloperCreateInternal, DeveloperUpdateInternal
from app.tests.utils.factories import create_developer


class TestDeveloperRepository:
    """Test suite for DeveloperRepository."""

    @pytest.fixture
    def developer_repo(self) -> DeveloperRepository:
        """Create DeveloperRepository instance."""
        return DeveloperRepository(Developer)

    def test_create(self, db: Session, developer_repo: DeveloperRepository):
        """Test creating a new developer."""
        # Arrange
        now = datetime.now(timezone.utc)
        developer_data = DeveloperCreateInternal(
            id=uuid4(),
            email="dev@example.com",
            hashed_password="hashed_password123",
            created_at=now,
            updated_at=now,
        )

        # Act
        result = developer_repo.create(db, developer_data)

        # Assert
        assert result.id == developer_data.id
        assert result.email == "dev@example.com"
        assert result.hashed_password == "hashed_password123"
        assert result.created_at == now
        assert result.updated_at == now

        # Verify in database
        db.expire_all()
        db_developer = developer_repo.get(db, developer_data.id)
        assert db_developer is not None
        assert db_developer.email == "dev@example.com"

    def test_get(self, db: Session, developer_repo: DeveloperRepository):
        """Test retrieving a developer by ID."""
        # Arrange
        developer = create_developer(db, email="test@example.com")

        # Act
        result = developer_repo.get(db, developer.id)

        # Assert
        assert result is not None
        assert result.id == developer.id
        assert result.email == "test@example.com"

    def test_get_nonexistent(self, db: Session, developer_repo: DeveloperRepository):
        """Test retrieving a nonexistent developer returns None."""
        # Act
        result = developer_repo.get(db, uuid4())

        # Assert
        assert result is None

    def test_get_all(self, db: Session, developer_repo: DeveloperRepository):
        """Test listing all developers."""
        # Arrange
        dev1 = create_developer(db, email="dev1@example.com")
        dev2 = create_developer(db, email="dev2@example.com")
        dev3 = create_developer(db, email="dev3@example.com")

        # Act
        results = developer_repo.get_all(db, filters={}, offset=0, limit=10, sort_by=None)

        # Assert
        assert len(results) >= 3
        developer_ids = [d.id for d in results]
        assert dev1.id in developer_ids
        assert dev2.id in developer_ids
        assert dev3.id in developer_ids

    def test_get_all_with_email_filter(self, db: Session, developer_repo: DeveloperRepository):
        """Test filtering developers by email."""
        # Arrange
        dev1 = create_developer(db, email="target@example.com")
        create_developer(db, email="other1@example.com")
        create_developer(db, email="other2@example.com")

        # Act
        results = developer_repo.get_all(
            db,
            filters={"email": "target@example.com"},
            offset=0,
            limit=10,
            sort_by=None,
        )

        # Assert
        assert len(results) == 1
        assert results[0].email == "target@example.com"
        assert results[0].id == dev1.id

    def test_get_all_with_pagination(self, db: Session, developer_repo: DeveloperRepository):
        """Test pagination with offset and limit."""
        # Arrange
        for i in range(5):
            create_developer(db, email=f"dev{i}@example.com")

        # Act - Get first 2 developers
        page1 = developer_repo.get_all(db, filters={}, offset=0, limit=2, sort_by=None)

        # Act - Get next 2 developers
        page2 = developer_repo.get_all(db, filters={}, offset=2, limit=2, sort_by=None)

        # Assert
        assert len(page1) == 2
        assert len(page2) == 2
        # Verify different results
        page1_ids = {d.id for d in page1}
        page2_ids = {d.id for d in page2}
        assert len(page1_ids & page2_ids) == 0  # No overlap

    def test_get_all_with_sort(self, db: Session, developer_repo: DeveloperRepository):
        """Test sorting developers by email."""
        # Arrange
        create_developer(db, email="charlie@example.com")
        create_developer(db, email="alice@example.com")
        create_developer(db, email="bob@example.com")

        # Act
        results = developer_repo.get_all(db, filters={}, offset=0, limit=10, sort_by="email")

        # Assert
        assert len(results) >= 3
        # Verify alphabetical order (at least for our test developers)
        emails = [
            d.email for d in results if d.email in ["alice@example.com", "bob@example.com", "charlie@example.com"]
        ]
        assert emails == sorted(emails)

    def test_update(self, db: Session, developer_repo: DeveloperRepository):
        """Test updating an existing developer."""
        # Arrange
        developer = create_developer(db, email="old@example.com", password="old_password")
        update_data = DeveloperUpdateInternal(
            email="new@example.com",
            hashed_password="hashed_new_password",
        )

        # Act
        result = developer_repo.update(db, developer, update_data)

        # Assert
        assert result.email == "new@example.com"
        assert result.hashed_password == "hashed_new_password"
        assert result.updated_at > developer.created_at  # Updated timestamp should change

        # Verify in database
        db.expire_all()
        db_developer = developer_repo.get(db, developer.id)
        assert db_developer.email == "new@example.com"
        assert db_developer.hashed_password == "hashed_new_password"

    def test_update_email_only(self, db: Session, developer_repo: DeveloperRepository):
        """Test updating only the email."""
        # Arrange
        developer = create_developer(db, email="old@example.com", password="password123")
        original_password = developer.hashed_password
        update_data = DeveloperUpdateInternal(email="new@example.com")

        # Act
        result = developer_repo.update(db, developer, update_data)

        # Assert
        assert result.email == "new@example.com"
        assert result.hashed_password == original_password  # Password unchanged

    def test_update_password_only(self, db: Session, developer_repo: DeveloperRepository):
        """Test updating only the password."""
        # Arrange
        developer = create_developer(db, email="dev@example.com", password="old_password")
        update_data = DeveloperUpdateInternal(hashed_password="hashed_new_password")

        # Act
        result = developer_repo.update(db, developer, update_data)

        # Assert
        assert result.email == "dev@example.com"  # Email unchanged
        assert result.hashed_password == "hashed_new_password"

    def test_delete(self, db: Session, developer_repo: DeveloperRepository):
        """Test deleting a developer."""
        # Arrange
        developer = create_developer(db)
        developer_id = developer.id

        # Act
        developer_repo.delete(db, developer)

        # Assert
        db.expire_all()
        deleted_developer = developer_repo.get(db, developer_id)
        assert deleted_developer is None

    def test_create_multiple_developers(self, db: Session, developer_repo: DeveloperRepository):
        """Test creating multiple developers with unique emails."""
        # Arrange
        emails = ["dev1@example.com", "dev2@example.com", "dev3@example.com"]

        # Act
        created_developers = []
        for email in emails:
            developer_data = DeveloperCreateInternal(
                id=uuid4(),
                email=email,
                hashed_password=f"hashed_{email}",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            created_developers.append(developer_repo.create(db, developer_data))

        # Assert
        assert len(created_developers) == 3
        created_emails = {d.email for d in created_developers}
        assert created_emails == set(emails)

    def test_filter_by_id(self, db: Session, developer_repo: DeveloperRepository):
        """Test filtering developers by ID."""
        # Arrange
        dev = create_developer(db, email="test@example.com")

        # Act
        results = developer_repo.get_all(
            db,
            filters={"id": str(dev.id)},
            offset=0,
            limit=10,
            sort_by=None,
        )

        # Assert
        # The filter works with string representation of UUID
        assert len(results) == 1
        assert results[0].id == dev.id

    def test_timestamps_on_create(self, db: Session, developer_repo: DeveloperRepository):
        """Test that created_at and updated_at are set correctly on creation."""
        # Arrange
        now = datetime.now(timezone.utc)
        developer_data = DeveloperCreateInternal(
            id=uuid4(),
            email="dev@example.com",
            hashed_password="hashed_password",
            created_at=now,
            updated_at=now,
        )

        # Act
        result = developer_repo.create(db, developer_data)

        # Assert
        assert result.created_at == now
        assert result.updated_at == now

    def test_timestamps_on_update(self, db: Session, developer_repo: DeveloperRepository):
        """Test that updated_at changes on update."""
        # Arrange
        developer = create_developer(db, email="dev@example.com")
        original_created_at = developer.created_at
        original_updated_at = developer.updated_at

        # Wait a tiny bit to ensure timestamp difference
        import time

        time.sleep(0.01)

        update_data = DeveloperUpdateInternal(email="updated@example.com")

        # Act
        result = developer_repo.update(db, developer, update_data)

        # Assert
        assert result.created_at == original_created_at  # Created timestamp unchanged
        assert result.updated_at > original_updated_at  # Updated timestamp changed
