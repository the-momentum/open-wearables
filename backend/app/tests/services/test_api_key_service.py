"""
Tests for ApiKeyService.

Tests cover:
- Creating API keys with sk- prefix
- Listing API keys ordered by creation date
- Rotating API keys (delete old, create new)
- Validating API keys
- Key generation format
"""

import pytest
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException
from sqlalchemy.orm import Session
from uuid import uuid4

from app.services.api_key_service import api_key_service
from app.tests.utils.factories import create_api_key, create_developer


class TestApiKeyServiceCreateApiKey:
    """Test API key creation with proper format."""

    def test_create_api_key_generates_sk_prefix(self, db: Session):
        """Should generate API key with sk- prefix."""
        # Arrange
        developer = create_developer(db)

        # Act
        api_key = api_key_service.create_api_key(db, developer.id, "Test Key")

        # Assert
        assert api_key.id.startswith("sk-")
        assert api_key.name == "Test Key"
        assert api_key.created_by == developer.id

    def test_create_api_key_has_correct_length(self, db: Session):
        """Should generate key with correct format: sk- + 32 hex chars."""
        # Arrange
        developer = create_developer(db)

        # Act
        api_key = api_key_service.create_api_key(db, developer.id)

        # Assert
        # Format: "sk-" (3 chars) + 32 hex chars = 35 total
        assert len(api_key.id) == 35
        # Verify hex portion is valid hexadecimal
        hex_portion = api_key.id[3:]
        assert all(c in "0123456789abcdef" for c in hex_portion)

    def test_create_api_key_default_name(self, db: Session):
        """Should use default name when not provided."""
        # Arrange
        developer = create_developer(db)

        # Act
        api_key = api_key_service.create_api_key(db, developer.id)

        # Assert
        assert api_key.name == "Default"

    def test_create_api_key_without_developer(self, db: Session):
        """Should create API key with None as created_by."""
        # Act
        api_key = api_key_service.create_api_key(db, None, "Anonymous Key")

        # Assert
        assert api_key.id.startswith("sk-")
        assert api_key.created_by is None
        assert api_key.name == "Anonymous Key"

    def test_create_api_key_sets_created_at(self, db: Session):
        """Should set created_at timestamp."""
        # Arrange
        developer = create_developer(db)

        # Act
        api_key = api_key_service.create_api_key(db, developer.id, "Timestamped Key")

        # Assert
        assert api_key.created_at is not None
        # Verify timestamp is recent (within last minute)
        assert (datetime.now(timezone.utc) - api_key.created_at).total_seconds() < 60

    def test_create_api_key_generates_unique_keys(self, db: Session):
        """Should generate unique keys for each creation."""
        # Arrange
        developer = create_developer(db)

        # Act
        key1 = api_key_service.create_api_key(db, developer.id, "Key 1")
        key2 = api_key_service.create_api_key(db, developer.id, "Key 2")

        # Assert
        assert key1.id != key2.id


class TestApiKeyServiceGenerateKeyValue:
    """Test internal key generation method."""

    def test_generate_key_value_format(self):
        """Should generate key with sk- prefix and 32 hex chars."""
        # Act
        key = api_key_service._generate_key_value()

        # Assert
        assert key.startswith("sk-")
        assert len(key) == 35
        hex_portion = key[3:]
        assert all(c in "0123456789abcdef" for c in hex_portion)

    def test_generate_key_value_uniqueness(self):
        """Should generate unique keys on each call."""
        # Act
        keys = [api_key_service._generate_key_value() for _ in range(100)]

        # Assert
        assert len(keys) == len(set(keys))  # All unique


class TestApiKeyServiceListApiKeys:
    """Test listing API keys."""

    def test_list_api_keys_ordered_by_created_at(self, db: Session):
        """Should list API keys ordered by creation date."""
        # Arrange
        developer = create_developer(db)
        now = datetime.now(timezone.utc)

        # Create keys at different times
        key1 = create_api_key(db, developer=developer, name="First", created_at=now - timedelta(days=2))
        key2 = create_api_key(db, developer=developer, name="Second", created_at=now - timedelta(days=1))
        key3 = create_api_key(db, developer=developer, name="Third", created_at=now)

        # Act
        keys = api_key_service.list_api_keys(db)

        # Assert
        assert len(keys) >= 3
        # Find our test keys in the result
        test_keys = [k for k in keys if k.id in [key1.id, key2.id, key3.id]]
        assert len(test_keys) == 3
        # Verify ordering (oldest first based on repository implementation)
        assert test_keys[0].id == key1.id
        assert test_keys[1].id == key2.id
        assert test_keys[2].id == key3.id

    def test_list_api_keys_empty(self, db: Session):
        """Should return empty list when no API keys exist."""
        # Act
        keys = api_key_service.list_api_keys(db)

        # Assert
        assert keys == []

    def test_list_api_keys_multiple_developers(self, db: Session):
        """Should list keys from all developers."""
        # Arrange
        dev1 = create_developer(db, email="dev1@example.com")
        dev2 = create_developer(db, email="dev2@example.com")

        key1 = create_api_key(db, developer=dev1)
        key2 = create_api_key(db, developer=dev2)

        # Act
        keys = api_key_service.list_api_keys(db)

        # Assert
        key_ids = [k.id for k in keys]
        assert key1.id in key_ids
        assert key2.id in key_ids


class TestApiKeyServiceRotateApiKey:
    """Test API key rotation."""

    def test_rotate_api_key_deletes_old_creates_new(self, db: Session):
        """Should delete old key and create new one."""
        # Arrange
        developer = create_developer(db)
        old_key = create_api_key(db, developer=developer, name="Old Key")
        old_key_id = old_key.id

        # Act
        new_key = api_key_service.rotate_api_key(db, old_key_id, developer.id)

        # Assert
        assert new_key.id != old_key_id
        assert new_key.id.startswith("sk-")
        assert new_key.created_by == developer.id

        # Verify old key is deleted
        assert api_key_service.get(db, old_key_id) is None

    def test_rotate_api_key_with_none_creator(self, db: Session):
        """Should rotate key with None as creator."""
        # Arrange
        old_key = create_api_key(db, developer=None)
        old_key_id = old_key.id

        # Act
        new_key = api_key_service.rotate_api_key(db, old_key_id, None)

        # Assert
        assert new_key.id != old_key_id
        assert new_key.created_by is None

    def test_rotate_nonexistent_key_raises_404(self, db: Session):
        """Should raise 404 when rotating non-existent key."""
        # Arrange
        fake_key = "sk-nonexistent"
        developer = create_developer(db)

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            api_key_service.rotate_api_key(db, fake_key, developer.id)

        assert exc_info.value.status_code == 404


class TestApiKeyServiceValidateApiKey:
    """Test API key validation."""

    def test_validate_api_key_existing_key(self, db: Session):
        """Should validate and return existing API key."""
        # Arrange
        developer = create_developer(db)
        api_key = create_api_key(db, developer=developer)

        # Act
        validated = api_key_service.validate_api_key(db, api_key.id)

        # Assert
        assert validated.id == api_key.id
        assert validated.created_by == developer.id

    def test_validate_api_key_nonexistent_raises_401(self, db: Session):
        """Should raise 401 for non-existent key."""
        # Arrange
        fake_key = "sk-nonexistent12345678901234567890"

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            api_key_service.validate_api_key(db, fake_key)

        assert exc_info.value.status_code == 401
        assert "Invalid or missing API key" in exc_info.value.detail

    def test_validate_api_key_empty_string_raises_401(self, db: Session):
        """Should raise 401 for empty key."""
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            api_key_service.validate_api_key(db, "")

        assert exc_info.value.status_code == 401


class TestApiKeyServiceGet:
    """Test getting API key by ID."""

    def test_get_existing_api_key(self, db: Session):
        """Should retrieve existing API key."""
        # Arrange
        developer = create_developer(db)
        api_key = create_api_key(db, developer=developer, name="Test Key")

        # Act
        retrieved = api_key_service.get(db, api_key.id)

        # Assert
        assert retrieved is not None
        assert retrieved.id == api_key.id
        assert retrieved.name == "Test Key"

    def test_get_nonexistent_api_key_returns_none(self, db: Session):
        """Should return None for non-existent key."""
        # Arrange
        fake_key = "sk-doesnotexist123456789012345678"

        # Act
        result = api_key_service.get(db, fake_key)

        # Assert
        assert result is None


class TestApiKeyServiceDelete:
    """Test API key deletion."""

    def test_delete_existing_api_key(self, db: Session):
        """Should delete existing API key."""
        # Arrange
        developer = create_developer(db)
        api_key = create_api_key(db, developer=developer)
        key_id = api_key.id

        # Act
        api_key_service.delete(db, key_id)

        # Assert
        result = api_key_service.get(db, key_id)
        assert result is None

    def test_delete_nonexistent_api_key(self, db: Session):
        """Should handle deleting non-existent key gracefully."""
        # Arrange
        fake_key = "sk-doesnotexist123456789012345678"

        # Act & Assert - should not raise error
        api_key_service.delete(db, fake_key, raise_404=False)
