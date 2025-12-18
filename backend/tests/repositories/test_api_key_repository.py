"""
Tests for ApiKeyRepository.

Tests cover:
- CRUD operations (create, get, get_all, delete)
- get_all_ordered method (ordered by created_at descending)
- API key specific behaviors (string ID)
"""

from datetime import datetime, timedelta, timezone
from typing import cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session

from app.models import ApiKey
from app.repositories.api_key_repository import ApiKeyRepository
from app.schemas.api_key import ApiKeyCreate, ApiKeyUpdate
from tests.factories import ApiKeyFactory, DeveloperFactory


def _str_id_as_uuid(str_id: str) -> UUID:
    """Cast string ID to UUID for type checker (ApiKey uses string IDs)."""
    return cast(UUID, str_id)


class TestApiKeyRepository:
    """Test suite for ApiKeyRepository."""

    @pytest.fixture
    def api_key_repo(self) -> ApiKeyRepository:
        """Create ApiKeyRepository instance."""
        return ApiKeyRepository(ApiKey)

    def test_create(self, db: Session, api_key_repo: ApiKeyRepository) -> None:
        """Test creating a new API key."""
        # Arrange
        developer = DeveloperFactory()
        key_id = f"sk-{uuid4().hex[:32]}"
        api_key_data = ApiKeyCreate(
            id=key_id,
            name="Test API Key",
            created_by=developer.id,
            created_at=datetime.now(timezone.utc),
        )

        # Act
        result = api_key_repo.create(db, api_key_data)

        # Assert
        assert result.id == key_id
        assert result.name == "Test API Key"
        assert result.created_by == developer.id
        assert isinstance(result.created_at, datetime)

        # Verify in database
        db.expire_all()
        db_api_key = api_key_repo.get(db, _str_id_as_uuid(key_id))
        assert db_api_key is not None
        assert db_api_key.name == "Test API Key"

    def test_create_without_developer(self, db: Session, api_key_repo: ApiKeyRepository) -> None:
        """Test creating an API key without a developer (orphaned key)."""
        # Arrange
        key_id = f"sk-{uuid4().hex[:32]}"
        api_key_data = ApiKeyCreate(
            id=key_id,
            name="Orphaned Key",
            created_by=None,
        )

        # Act
        result = api_key_repo.create(db, api_key_data)

        # Assert
        assert result.id == key_id
        assert result.name == "Orphaned Key"
        assert result.created_by is None

    def test_get(self, db: Session, api_key_repo: ApiKeyRepository) -> None:
        """Test retrieving an API key by ID."""
        # Arrange
        api_key = ApiKeyFactory(name="My Test Key")

        # Act
        result = api_key_repo.get(db, _str_id_as_uuid(api_key.id))

        # Assert
        assert result is not None
        assert result.id == api_key.id
        assert result.name == "My Test Key"

    def test_get_nonexistent(self, db: Session, api_key_repo: ApiKeyRepository) -> None:
        """Test retrieving a nonexistent API key returns None."""
        # Act
        result = api_key_repo.get(db, _str_id_as_uuid("sk-nonexistent-key-12345"))

        # Assert
        assert result is None

    def test_get_all(self, db: Session, api_key_repo: ApiKeyRepository) -> None:
        """Test listing all API keys."""
        # Arrange
        key1 = ApiKeyFactory(name="Key 1")
        key2 = ApiKeyFactory(name="Key 2")
        key3 = ApiKeyFactory(name="Key 3")

        # Act
        results = api_key_repo.get_all(db, filters={}, offset=0, limit=10, sort_by=None)

        # Assert
        assert len(results) >= 3
        key_ids = [k.id for k in results]
        assert key1.id in key_ids
        assert key2.id in key_ids
        assert key3.id in key_ids

    def test_get_all_with_name_filter(self, db: Session, api_key_repo: ApiKeyRepository) -> None:
        """Test filtering API keys by name."""
        # Arrange
        key1 = ApiKeyFactory(name="Production Key")
        ApiKeyFactory(name="Development Key")
        ApiKeyFactory(name="Test Key")

        # Act
        results = api_key_repo.get_all(
            db,
            filters={"name": "Production Key"},
            offset=0,
            limit=10,
            sort_by=None,
        )

        # Assert
        assert len(results) == 1
        assert results[0].name == "Production Key"
        assert results[0].id == key1.id

    def test_get_all_with_developer_filter(self, db: Session, api_key_repo: ApiKeyRepository) -> None:
        """Test filtering API keys by developer."""
        # Arrange
        dev1 = DeveloperFactory(email="dev1@example.com")
        dev2 = DeveloperFactory(email="dev2@example.com")

        ApiKeyFactory(developer=dev1, name="Dev1 Key")
        ApiKeyFactory(developer=dev2, name="Dev2 Key")

        # Act
        results = api_key_repo.get_all(
            db,
            filters={"created_by": str(dev1.id)},
            offset=0,
            limit=10,
            sort_by=None,
        )

        # Assert
        # created_by filter works - string ID is converted to UUID properly
        assert len(results) == 1
        assert results[0].name == "Dev1 Key"

    def test_get_all_with_pagination(self, db: Session, api_key_repo: ApiKeyRepository) -> None:
        """Test pagination with offset and limit."""
        # Arrange
        for i in range(5):
            ApiKeyFactory(name=f"Key {i}")

        # Act - Get first 2 keys
        page1 = api_key_repo.get_all(db, filters={}, offset=0, limit=2, sort_by=None)

        # Act - Get next 2 keys
        page2 = api_key_repo.get_all(db, filters={}, offset=2, limit=2, sort_by=None)

        # Assert
        assert len(page1) == 2
        assert len(page2) == 2
        # Verify different results
        page1_ids = {k.id for k in page1}
        page2_ids = {k.id for k in page2}
        assert len(page1_ids & page2_ids) == 0  # No overlap

    def test_get_all_ordered(self, db: Session, api_key_repo: ApiKeyRepository) -> None:
        """Test getting all API keys ordered by creation date (most recent first)."""
        # Arrange
        now = datetime.now(timezone.utc)
        three_days_ago = now - timedelta(days=3)
        two_days_ago = now - timedelta(days=2)
        one_day_ago = now - timedelta(days=1)

        key1 = ApiKeyFactory(name="Oldest Key", created_at=three_days_ago)
        key2 = ApiKeyFactory(name="Middle Key", created_at=two_days_ago)
        key3 = ApiKeyFactory(name="Recent Key", created_at=one_day_ago)
        key4 = ApiKeyFactory(name="Newest Key", created_at=now)

        # Act
        results = api_key_repo.get_all_ordered(db)

        # Assert
        assert len(results) >= 4
        # Find our test keys in results
        test_keys = [k for k in results if k.id in [key1.id, key2.id, key3.id, key4.id]]
        assert len(test_keys) == 4
        # Verify descending order (newest first)
        assert test_keys[0].id == key4.id  # Newest
        assert test_keys[1].id == key3.id  # Recent
        assert test_keys[2].id == key2.id  # Middle
        assert test_keys[3].id == key1.id  # Oldest

    def test_delete(self, db: Session, api_key_repo: ApiKeyRepository) -> None:
        """Test deleting an API key."""
        # Arrange
        api_key = ApiKeyFactory(name="Key to Delete")
        key_id = api_key.id

        # Act
        api_key_repo.delete(db, api_key)

        # Assert
        db.expire_all()
        deleted_key = api_key_repo.get(db, _str_id_as_uuid(key_id))
        assert deleted_key is None

    def test_update_not_implemented(self, db: Session, api_key_repo: ApiKeyRepository) -> None:
        """Test that update works (though ApiKey doesn't have a custom update schema)."""
        # Arrange
        api_key = ApiKeyFactory(name="Original Name")
        update_data = ApiKeyUpdate(name="Updated Name")

        # Act
        result = api_key_repo.update(db, api_key, update_data)

        # Assert
        assert result.name == "Updated Name"

        # Verify in database
        db.expire_all()
        db_key = api_key_repo.get(db, _str_id_as_uuid(api_key.id))
        assert db_key is not None
        assert db_key.name == "Updated Name"

    def test_create_with_custom_timestamp(self, db: Session, api_key_repo: ApiKeyRepository) -> None:
        """Test creating an API key with a specific timestamp."""
        # Arrange
        custom_time = datetime(2023, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        key_id = f"sk-{uuid4().hex[:32]}"
        api_key_data = ApiKeyCreate(
            id=key_id,
            name="Historical Key",
            created_at=custom_time,
        )

        # Act
        result = api_key_repo.create(db, api_key_data)

        # Assert
        assert result.created_at == custom_time

    def test_multiple_keys_same_developer(self, db: Session, api_key_repo: ApiKeyRepository) -> None:
        """Test that a developer can have multiple API keys."""
        # Arrange
        developer = DeveloperFactory()
        ApiKeyFactory(developer=developer, name="Key 1")
        ApiKeyFactory(developer=developer, name="Key 2")
        ApiKeyFactory(developer=developer, name="Key 3")

        # Act - Get all keys (we can't filter by UUID properly, so get all)
        all_keys = api_key_repo.get_all(db, filters={}, offset=0, limit=100, sort_by=None)

        # Assert
        developer_keys = [k for k in all_keys if k.created_by == developer.id]
        assert len(developer_keys) >= 3
        key_names = {k.name for k in developer_keys}
        assert "Key 1" in key_names
        assert "Key 2" in key_names
        assert "Key 3" in key_names

    def test_api_key_id_format(self, db: Session, api_key_repo: ApiKeyRepository) -> None:
        """Test that API key IDs are stored correctly (string format)."""
        # Arrange
        key_id = "sk-test-custom-key-id-12345"
        api_key_data = ApiKeyCreate(
            id=key_id,
            name="Custom ID Key",
        )

        # Act
        result = api_key_repo.create(db, api_key_data)

        # Assert
        assert isinstance(result.id, str)
        assert result.id == key_id
        assert result.id.startswith("sk-")

    def test_get_all_ordered_empty_database(self, db: Session, api_key_repo: ApiKeyRepository) -> None:
        """Test get_all_ordered with no API keys."""
        # Arrange - Delete all keys if any exist
        all_keys = api_key_repo.get_all_ordered(db)
        for key in all_keys:
            api_key_repo.delete(db, key)

        # Act
        results = api_key_repo.get_all_ordered(db)

        # Assert
        assert results == []

    def test_sort_by_name(self, db: Session, api_key_repo: ApiKeyRepository) -> None:
        """Test sorting API keys by name."""
        # Arrange
        ApiKeyFactory(name="Zebra Key")
        ApiKeyFactory(name="Alpha Key")
        ApiKeyFactory(name="Beta Key")

        # Act
        results = api_key_repo.get_all(db, filters={}, offset=0, limit=10, sort_by="name")

        # Assert
        assert len(results) >= 3
        # Verify alphabetical order (at least for our test keys)
        names = [k.name for k in results if k.name in ["Alpha Key", "Beta Key", "Zebra Key"]]
        assert names == sorted(names)
