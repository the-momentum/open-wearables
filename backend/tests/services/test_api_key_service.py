"""
Tests for ApiKeyService.

Tests cover:
- Creating API keys: raw key returned once, only hash + prefix persisted
- Listing API keys ordered by creation date
- Rotating API keys (delete old, create new with the same name)
- Validating raw API keys against stored hashes
- Key generation format
"""

from datetime import datetime, timedelta, timezone
from typing import NoReturn
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.services.api_key_service import KEY_PREFIX_LENGTH, api_key_service
from app.utils.security import hash_api_key
from tests.factories import ApiKeyFactory, DeveloperFactory


class TestApiKeyServiceCreateApiKey:
    """Test API key creation with proper format."""

    def test_create_api_key_returns_raw_key_with_sk_prefix(self, db: Session) -> None:
        """Should return the raw key with sk- prefix alongside the persisted record."""
        # Arrange
        developer = DeveloperFactory()

        # Act
        api_key, raw_key = api_key_service.create_api_key(db, developer.id, "Test Key")

        # Assert
        assert raw_key.startswith("sk-")
        assert api_key.name == "Test Key"
        assert api_key.created_by == developer.id

    def test_create_api_key_raw_key_has_correct_length(self, db: Session) -> None:
        """Should generate key with correct format: sk- + 32 hex chars."""
        # Arrange
        developer = DeveloperFactory()

        # Act
        _, raw_key = api_key_service.create_api_key(db, developer.id)

        # Assert
        # Format: "sk-" (3 chars) + 32 hex chars = 35 total
        assert len(raw_key) == 35
        hex_portion = raw_key[3:]
        assert all(c in "0123456789abcdef" for c in hex_portion)

    def test_create_api_key_persists_only_hash_and_prefix(self, db: Session) -> None:
        """The raw key must not be stored anywhere on the record."""
        # Arrange
        developer = DeveloperFactory()

        # Act
        api_key, raw_key = api_key_service.create_api_key(db, developer.id)

        # Assert
        assert api_key.key_hash == hash_api_key(raw_key)
        assert api_key.key_prefix == raw_key[:KEY_PREFIX_LENGTH]
        assert len(api_key.key_prefix) == KEY_PREFIX_LENGTH
        assert raw_key not in {str(v) for v in vars(api_key).values()}

    def test_create_api_key_default_name(self, db: Session) -> None:
        """Should use default name when not provided."""
        # Arrange
        developer = DeveloperFactory()

        # Act
        api_key, _ = api_key_service.create_api_key(db, developer.id)

        # Assert
        assert api_key.name == "Default"

    def test_create_api_key_without_developer(self, db: Session) -> None:
        """Should create API key with None as created_by."""
        # Act
        api_key, raw_key = api_key_service.create_api_key(db, None, "Anonymous Key")

        # Assert
        assert raw_key.startswith("sk-")
        assert api_key.created_by is None
        assert api_key.name == "Anonymous Key"

    def test_create_api_key_sets_created_at(self, db: Session) -> None:
        """Should set created_at timestamp."""
        # Arrange
        developer = DeveloperFactory()

        # Act
        api_key, _ = api_key_service.create_api_key(db, developer.id, "Timestamped Key")

        # Assert
        assert api_key.created_at is not None
        assert (datetime.now(timezone.utc) - api_key.created_at).total_seconds() < 60

    def test_create_api_key_generates_unique_keys(self, db: Session) -> None:
        """Should generate unique keys for each creation."""
        # Arrange
        developer = DeveloperFactory()

        # Act
        key1, raw1 = api_key_service.create_api_key(db, developer.id, "Key 1")
        key2, raw2 = api_key_service.create_api_key(db, developer.id, "Key 2")

        # Assert
        assert key1.id != key2.id
        assert raw1 != raw2
        assert key1.key_hash != key2.key_hash


class TestApiKeyServiceGenerateKeyValue:
    """Test internal key generation method."""

    def test_generate_key_value_format(self) -> None:
        """Should generate key with sk- prefix and 32 hex chars."""
        # Act
        key = api_key_service._generate_key_value()

        # Assert
        assert key.startswith("sk-")
        assert len(key) == 35
        hex_portion = key[3:]
        assert all(c in "0123456789abcdef" for c in hex_portion)

    def test_generate_key_value_uniqueness(self) -> None:
        """Should generate unique keys on each call."""
        # Act
        keys = [api_key_service._generate_key_value() for _ in range(100)]

        # Assert
        assert len(keys) == len(set(keys))


class TestApiKeyServiceListApiKeys:
    """Test listing API keys."""

    def test_list_api_keys_ordered_by_created_at(self, db: Session) -> None:
        """Should list API keys ordered by creation date, newest first."""
        # Arrange
        developer = DeveloperFactory()
        now = datetime.now(timezone.utc)

        key1 = ApiKeyFactory(developer=developer, name="First", created_at=now - timedelta(days=2))
        key2 = ApiKeyFactory(developer=developer, name="Second", created_at=now - timedelta(days=1))
        key3 = ApiKeyFactory(developer=developer, name="Third", created_at=now)

        # Act
        keys = api_key_service.list_api_keys(db)

        # Assert
        test_keys = [k for k in keys if k.id in [key1.id, key2.id, key3.id]]
        assert len(test_keys) == 3
        assert test_keys[0].id == key3.id
        assert test_keys[1].id == key2.id
        assert test_keys[2].id == key1.id

    def test_list_api_keys_empty(self, db: Session) -> None:
        """Should return empty list when no API keys exist."""
        # Act
        keys = api_key_service.list_api_keys(db)

        # Assert
        assert keys == []

    def test_list_api_keys_multiple_developers(self, db: Session) -> None:
        """Keys are global to the deployment: every developer sees all of them."""
        # Arrange
        dev1 = DeveloperFactory(email="dev1@example.com")
        dev2 = DeveloperFactory(email="dev2@example.com")

        key1 = ApiKeyFactory(developer=dev1)
        key2 = ApiKeyFactory(developer=dev2)

        # Act
        keys = api_key_service.list_api_keys(db)

        # Assert
        key_ids = [k.id for k in keys]
        assert key1.id in key_ids
        assert key2.id in key_ids


class TestApiKeyServiceRotateApiKey:
    """Test API key rotation."""

    def test_rotate_api_key_deletes_old_creates_new(self, db: Session) -> None:
        """Should delete old key and create a new one that keeps the name."""
        # Arrange
        developer = DeveloperFactory()
        old_key = ApiKeyFactory(developer=developer, name="Production Key")
        old_key_id = old_key.id
        old_raw_key = old_key.plain_key

        # Act
        new_key, raw_key = api_key_service.rotate_api_key(db, old_key_id, developer.id)

        # Assert
        assert new_key.id != old_key_id
        assert new_key.name == "Production Key"
        assert new_key.created_by == developer.id
        assert raw_key.startswith("sk-")
        assert raw_key != old_raw_key

        # Old key is gone and no longer authenticates
        assert api_key_service.get(db, old_key_id) is None
        with pytest.raises(HTTPException):
            api_key_service.validate_api_key(db, old_raw_key)

        # New raw key authenticates
        assert api_key_service.validate_api_key(db, raw_key).id == new_key.id

    def test_rotate_api_key_with_none_creator(self, db: Session) -> None:
        """Should rotate key with None as creator."""
        # Arrange
        old_key = ApiKeyFactory()
        old_key_id = old_key.id

        # Act
        new_key, _ = api_key_service.rotate_api_key(db, old_key_id, None)

        # Assert
        assert new_key.id != old_key_id
        assert new_key.created_by is None

    def test_rotate_api_key_keeps_old_key_when_replacement_fails(
        self, db: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Should leave the old key intact and valid if creating the replacement fails."""
        # Arrange
        developer = DeveloperFactory()
        old_key = ApiKeyFactory(developer=developer, name="Production Key")
        old_key_id = old_key.id
        old_raw_key = old_key.plain_key
        # The factory only flushes; commit so the rollback inside rotate cannot undo the arrange step
        db.commit()

        def _fail(*_args: object, **_kwargs: object) -> NoReturn:
            raise RuntimeError("boom")

        monkeypatch.setattr(api_key_service, "create_api_key", _fail)

        # Act
        with pytest.raises(RuntimeError):
            api_key_service.rotate_api_key(db, old_key_id, developer.id)

        # Assert - the delete was rolled back together with the failed create
        assert api_key_service.get(db, old_key_id) is not None
        assert api_key_service.validate_api_key(db, old_raw_key).id == old_key_id
        assert len(api_key_service.list_api_keys(db)) == 1

    def test_rotate_nonexistent_key_raises_404(self, db: Session) -> None:
        """Should raise HTTPException(404) when rotating non-existent key."""
        # Arrange
        developer = DeveloperFactory()

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            api_key_service.rotate_api_key(db, uuid4(), developer.id)

        assert exc_info.value.status_code == 404


class TestApiKeyServiceValidateApiKey:
    """Test API key validation."""

    def test_validate_api_key_existing_key(self, db: Session) -> None:
        """Should validate the raw key and return the matching record."""
        # Arrange
        developer = DeveloperFactory()
        api_key = ApiKeyFactory(developer=developer)

        # Act
        validated = api_key_service.validate_api_key(db, api_key.plain_key)

        # Assert
        assert validated.id == api_key.id
        assert validated.created_by == developer.id

    def test_validate_api_key_rejects_hash_as_credential(self, db: Session) -> None:
        """Presenting the stored hash instead of the raw key must not authenticate."""
        # Arrange
        api_key = ApiKeyFactory()

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            api_key_service.validate_api_key(db, api_key.key_hash)

        assert exc_info.value.status_code == 401

    def test_validate_api_key_rejects_prefix_as_credential(self, db: Session) -> None:
        """The displayed prefix alone must not authenticate."""
        # Arrange
        api_key = ApiKeyFactory()

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            api_key_service.validate_api_key(db, api_key.key_prefix)

        assert exc_info.value.status_code == 401

    def test_validate_api_key_nonexistent_raises_401(self, db: Session) -> None:
        """Should raise 401 for non-existent key."""
        # Arrange
        fake_key = "sk-nonexistent12345678901234567890"

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            api_key_service.validate_api_key(db, fake_key)

        assert exc_info.value.status_code == 401
        assert "Invalid or missing API key" in exc_info.value.detail

    def test_validate_api_key_empty_string_raises_401(self, db: Session) -> None:
        """Should raise 401 for empty key."""
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            api_key_service.validate_api_key(db, "")

        assert exc_info.value.status_code == 401


class TestApiKeyServiceGet:
    """Test getting API key by ID."""

    def test_get_existing_api_key(self, db: Session) -> None:
        """Should retrieve existing API key."""
        # Arrange
        developer = DeveloperFactory()
        api_key = ApiKeyFactory(developer=developer, name="Test Key")

        # Act
        retrieved = api_key_service.get(db, api_key.id)

        # Assert
        assert retrieved is not None
        assert retrieved.id == api_key.id
        assert retrieved.name == "Test Key"

    def test_get_nonexistent_api_key_returns_none(self, db: Session) -> None:
        """Should return None for non-existent key."""
        # Act
        result = api_key_service.get(db, uuid4())

        # Assert
        assert result is None


class TestApiKeyServiceDelete:
    """Test API key deletion."""

    def test_delete_existing_api_key(self, db: Session) -> None:
        """Should delete existing API key."""
        # Arrange
        developer = DeveloperFactory()
        api_key = ApiKeyFactory(developer=developer)
        key_id = api_key.id

        # Act
        api_key_service.delete(db, key_id)

        # Assert
        assert api_key_service.get(db, key_id) is None

    def test_delete_nonexistent_api_key(self, db: Session) -> None:
        """Should handle deleting non-existent key gracefully."""
        # Act & Assert - should not raise error
        api_key_service.delete(db, uuid4(), raise_404=False)
