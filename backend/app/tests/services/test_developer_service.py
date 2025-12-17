"""
Tests for DeveloperService.

Tests cover:
- Registering developers with password hashing
- Updating developer info with password re-hashing
- Getting developers by ID
- Deleting developers
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.schemas.developer import DeveloperCreate, DeveloperUpdate
from app.services.developer_service import developer_service
from app.tests.utils.factories import create_developer


class TestDeveloperServiceRegister:
    """Test developer registration with password hashing."""

    def test_register_developer_hashes_password(self, db: Session):
        """Should hash password during registration."""
        # Arrange
        payload = DeveloperCreate(
            email="dev@example.com",
            password="secret_password_123",
        )

        # Act
        developer = developer_service.register(db, payload)

        # Assert
        assert developer.id is not None
        assert developer.email == "dev@example.com"
        assert developer.hashed_password == "hashed_secret_password_123"
        assert developer.created_at is not None
        assert developer.updated_at is not None

    def test_register_developer_does_not_store_plain_password(self, db: Session):
        """Should not store plain password."""
        # Arrange
        payload = DeveloperCreate(
            email="secure@example.com",
            password="my_secret_password",
        )

        # Act
        developer = developer_service.register(db, payload)

        # Assert
        assert developer.hashed_password != "my_secret_password"
        assert "hashed_" in developer.hashed_password

    def test_register_developer_sets_timestamps(self, db: Session):
        """Should set created_at and updated_at timestamps."""
        # Arrange
        payload = DeveloperCreate(
            email="timestamps@example.com",
            password="password123",
        )

        # Act
        developer = developer_service.register(db, payload)

        # Assert
        assert developer.created_at is not None
        assert developer.updated_at is not None
        # Both should be recent (within last minute)
        now = datetime.now(timezone.utc)
        assert (now - developer.created_at).total_seconds() < 60
        assert (now - developer.updated_at).total_seconds() < 60

    def test_register_developer_generates_unique_id(self, db: Session):
        """Should generate unique UUID for each developer."""
        # Arrange
        payload1 = DeveloperCreate(email="dev1@example.com", password="password1")
        payload2 = DeveloperCreate(email="dev2@example.com", password="password2")

        # Act
        dev1 = developer_service.register(db, payload1)
        dev2 = developer_service.register(db, payload2)

        # Assert
        assert dev1.id != dev2.id

    def test_register_developer_persists_to_database(self, db: Session):
        """Should persist developer to database."""
        # Arrange
        payload = DeveloperCreate(
            email="persist@example.com",
            password="password123",
        )

        # Act
        developer = developer_service.register(db, payload)

        # Assert - verify in database
        db_dev = developer_service.get(db, developer.id)
        assert db_dev is not None
        assert db_dev.email == "persist@example.com"
        assert db_dev.hashed_password == "hashed_password123"


class TestDeveloperServiceUpdateDeveloperInfo:
    """Test updating developer information."""

    def test_update_developer_info_email_only(self, db: Session):
        """Should update email without changing password."""
        # Arrange
        developer = create_developer(db, email="old@example.com", password="original_pass")
        original_hash = developer.hashed_password
        update_payload = DeveloperUpdate(email="new@example.com")

        # Act
        updated = developer_service.update_developer_info(db, developer.id, update_payload)

        # Assert
        assert updated is not None
        assert updated.email == "new@example.com"
        assert updated.hashed_password == original_hash  # Unchanged

    def test_update_developer_info_password_only(self, db: Session):
        """Should update and hash new password."""
        # Arrange
        developer = create_developer(db, email="dev@example.com", password="old_password")
        update_payload = DeveloperUpdate(password="new_password_123")

        # Act
        updated = developer_service.update_developer_info(db, developer.id, update_payload)

        # Assert
        assert updated is not None
        assert updated.hashed_password == "hashed_new_password_123"
        assert updated.email == developer.email  # Unchanged

    def test_update_developer_info_email_and_password(self, db: Session):
        """Should update both email and password."""
        # Arrange
        developer = create_developer(db, email="old@example.com", password="old_pass")
        update_payload = DeveloperUpdate(
            email="new@example.com",
            password="new_pass_456",
        )

        # Act
        updated = developer_service.update_developer_info(db, developer.id, update_payload)

        # Assert
        assert updated is not None
        assert updated.email == "new@example.com"
        assert updated.hashed_password == "hashed_new_pass_456"

    def test_update_developer_info_sets_updated_at(self, db: Session):
        """Should update updated_at timestamp."""
        # Arrange
        developer = create_developer(db, email="dev@example.com")
        original_updated_at = developer.updated_at
        update_payload = DeveloperUpdate(email="updated@example.com")

        # Act
        updated = developer_service.update_developer_info(db, developer.id, update_payload)

        # Assert
        assert updated is not None
        assert updated.updated_at > original_updated_at

    def test_update_nonexistent_developer_returns_none(self, db: Session):
        """Should return None when updating non-existent developer."""
        # Arrange
        fake_id = uuid4()
        update_payload = DeveloperUpdate(email="new@example.com")

        # Act
        result = developer_service.update_developer_info(db, fake_id, update_payload, raise_404=False)

        # Assert
        assert result is None

    def test_update_developer_with_raise_404(self, db: Session):
        """Should raise ResourceNotFoundError when updating non-existent developer with raise_404=True."""
        # Arrange
        from app.utils.exceptions import ResourceNotFoundError

        fake_id = uuid4()
        update_payload = DeveloperUpdate(email="new@example.com")

        # Act & Assert
        with pytest.raises(ResourceNotFoundError):
            developer_service.update_developer_info(db, fake_id, update_payload, raise_404=True)

    def test_update_developer_empty_update(self, db: Session):
        """Should handle empty update gracefully."""
        # Arrange
        developer = create_developer(db, email="dev@example.com")
        original_email = developer.email
        original_hash = developer.hashed_password
        update_payload = DeveloperUpdate()

        # Act
        updated = developer_service.update_developer_info(db, developer.id, update_payload)

        # Assert
        assert updated is not None
        assert updated.email == original_email
        assert updated.hashed_password == original_hash
        # updated_at should still be updated
        assert updated.updated_at >= developer.updated_at


class TestDeveloperServiceGet:
    """Test getting developers by ID."""

    def test_get_existing_developer(self, db: Session):
        """Should retrieve existing developer by ID."""
        # Arrange
        developer = create_developer(db, email="get@example.com")

        # Act
        retrieved = developer_service.get(db, developer.id)

        # Assert
        assert retrieved is not None
        assert retrieved.id == developer.id
        assert retrieved.email == developer.email

    def test_get_nonexistent_developer_returns_none(self, db: Session):
        """Should return None for non-existent developer."""
        # Arrange
        fake_id = uuid4()

        # Act
        result = developer_service.get(db, fake_id)

        # Assert
        assert result is None

    def test_get_developer_by_string_id(self, db: Session):
        """Should retrieve developer using string ID."""
        # Arrange
        developer = create_developer(db, email="string@example.com")

        # Act
        retrieved = developer_service.get(db, str(developer.id))

        # Assert
        assert retrieved is not None
        assert retrieved.id == developer.id

    def test_get_developer_returns_hashed_password(self, db: Session):
        """Should return developer with hashed password."""
        # Arrange
        developer = create_developer(db, email="hash@example.com", password="mypass")

        # Act
        retrieved = developer_service.get(db, developer.id)

        # Assert
        assert retrieved is not None
        assert retrieved.hashed_password == "hashed_mypass"


class TestDeveloperServiceDelete:
    """Test developer deletion."""

    def test_delete_existing_developer(self, db: Session):
        """Should delete existing developer."""
        # Arrange
        developer = create_developer(db, email="delete@example.com")
        developer_id = developer.id

        # Act
        developer_service.delete(db, developer_id)

        # Assert - developer should no longer exist
        result = developer_service.get(db, developer_id)
        assert result is None

    def test_delete_nonexistent_developer(self, db: Session):
        """Should handle deleting non-existent developer gracefully."""
        # Arrange
        fake_id = uuid4()

        # Act & Assert - should not raise error
        developer_service.delete(db, fake_id, raise_404=False)

    def test_delete_developer_by_string_id(self, db: Session):
        """Should delete developer using string ID."""
        # Arrange
        developer = create_developer(db, email="delete2@example.com")
        developer_id_str = str(developer.id)

        # Act
        developer_service.delete(db, developer_id_str)

        # Assert
        result = developer_service.get(db, developer_id_str)
        assert result is None
