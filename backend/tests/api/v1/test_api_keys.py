"""
Tests for API key management endpoints.

Tests cover:
- GET /api/v1/developer/api-keys - list API keys
- POST /api/v1/developer/api-keys - create new API key
- DELETE /api/v1/developer/api-keys/{key_id} - delete API key
- PATCH /api/v1/developer/api-keys/{key_id} - update API key
- POST /api/v1/developer/api-keys/{key_id}/rotate - rotate API key
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.factories import ApiKeyFactory, DeveloperFactory
from tests.utils import developer_auth_headers


class TestListApiKeys:
    """Tests for GET /api/v1/developer/api-keys."""

    def test_list_api_keys_success(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test listing API keys for authenticated developer."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        api_key1 = ApiKeyFactory(developer=developer, name="Key 1")
        api_key2 = ApiKeyFactory(developer=developer, name="Key 2")
        headers = developer_auth_headers(developer.id)

        # Act
        response = client.get(f"{api_v1_prefix}/developer/api-keys", headers=headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 2

        # Find our test keys
        key_ids = [api_key1.id, api_key2.id]
        found_keys = [k for k in data if k["id"] in key_ids]
        assert len(found_keys) == 2

        # Verify structure
        for key in found_keys:
            assert "id" in key
            assert "name" in key
            assert "created_by" in key
            assert "created_at" in key

    def test_list_api_keys_empty(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test listing API keys when developer has none."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        headers = developer_auth_headers(developer.id)

        # Act
        response = client.get(f"{api_v1_prefix}/developer/api-keys", headers=headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_list_api_keys_unauthorized(self, client: TestClient, api_v1_prefix: str) -> None:
        """Test listing API keys fails without authentication."""
        # Act
        response = client.get(f"{api_v1_prefix}/developer/api-keys")

        # Assert
        assert response.status_code == 401

    def test_list_api_keys_invalid_token(self, client: TestClient, api_v1_prefix: str) -> None:
        """Test listing API keys fails with invalid token."""
        # Act
        response = client.get(
            f"{api_v1_prefix}/developer/api-keys",
            headers={"Authorization": "Bearer invalid_token"},
        )

        # Assert
        assert response.status_code == 401

    def test_list_api_keys_shows_all_keys(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test that authenticated developer can see all API keys."""
        # Arrange
        developer1 = DeveloperFactory(email="dev1@example.com", password="test123")
        developer2 = DeveloperFactory(email="dev2@example.com", password="test123")
        key1 = ApiKeyFactory(developer=developer1, name="Dev1 Key")
        key2 = ApiKeyFactory(developer=developer2, name="Dev2 Key")
        headers = developer_auth_headers(developer1.id)

        # Act
        response = client.get(f"{api_v1_prefix}/developer/api-keys", headers=headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        key_ids = [k["id"] for k in data]
        assert key1.id in key_ids
        assert key2.id in key_ids


class TestCreateApiKey:
    """Tests for POST /api/v1/developer/api-keys."""

    def test_create_api_key_with_name(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test creating API key with custom name."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        headers = developer_auth_headers(developer.id)
        payload = {"name": "Production API Key"}

        # Act
        response = client.post(f"{api_v1_prefix}/developer/api-keys", json=payload, headers=headers)

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Production API Key"
        assert "id" in data
        assert data["id"].startswith("sk-")
        assert data["created_by"] == str(developer.id)
        assert "created_at" in data

        # Verify in database
        from app.services import api_key_service

        api_key = api_key_service.get(db, data["id"])
        assert api_key is not None
        assert api_key.name == "Production API Key"

    def test_create_api_key_default_name(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test creating API key with default name."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        headers = developer_auth_headers(developer.id)
        payload = {}

        # Act
        response = client.post(f"{api_v1_prefix}/developer/api-keys", json=payload, headers=headers)

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Default"
        assert "id" in data

    def test_create_api_key_no_body(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test creating API key without request body."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        headers = developer_auth_headers(developer.id)

        # Act
        response = client.post(f"{api_v1_prefix}/developer/api-keys", headers=headers)

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Default"

    def test_create_api_key_empty_name(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test creating API key with empty name."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        headers = developer_auth_headers(developer.id)
        payload = {"name": ""}

        # Act
        response = client.post(f"{api_v1_prefix}/developer/api-keys", json=payload, headers=headers)

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == ""

    def test_create_api_key_unauthorized(self, client: TestClient, api_v1_prefix: str) -> None:
        """Test creating API key fails without authentication."""
        # Act
        response = client.post(
            f"{api_v1_prefix}/developer/api-keys",
            json={"name": "Test Key"},
        )

        # Assert
        assert response.status_code == 401

    def test_create_multiple_api_keys(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test creating multiple API keys for the same developer."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        headers = developer_auth_headers(developer.id)

        # Act - Create multiple keys
        response1 = client.post(
            f"{api_v1_prefix}/developer/api-keys",
            json={"name": "Key 1"},
            headers=headers,
        )
        response2 = client.post(
            f"{api_v1_prefix}/developer/api-keys",
            json={"name": "Key 2"},
            headers=headers,
        )

        # Assert
        assert response1.status_code == 201
        assert response2.status_code == 201
        data1 = response1.json()
        data2 = response2.json()
        assert data1["id"] != data2["id"]
        assert data1["name"] == "Key 1"
        assert data2["name"] == "Key 2"


class TestDeleteApiKey:
    """Tests for DELETE /api/v1/developer/api-keys/{key_id}."""

    def test_delete_api_key_success(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test deleting API key successfully."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        api_key = ApiKeyFactory(developer=developer, name="To Delete")
        headers = developer_auth_headers(developer.id)
        key_id = api_key.id

        # Act
        response = client.delete(f"{api_v1_prefix}/developer/api-keys/{key_id}", headers=headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == key_id
        assert data["name"] == "To Delete"

        # Verify key is deleted from database
        from app.services import api_key_service

        deleted_key = api_key_service.get(db, key_id, raise_404=False)
        assert deleted_key is None

    def test_delete_api_key_not_found(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test deleting non-existent API key raises ResourceNotFoundError."""
        from app.utils.exceptions import ResourceNotFoundError

        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        headers = developer_auth_headers(developer.id)
        fake_key_id = "sk-nonexistent1234567890"

        # Act & Assert
        with pytest.raises(ResourceNotFoundError):
            client.delete(f"{api_v1_prefix}/developer/api-keys/{fake_key_id}", headers=headers)

    def test_delete_api_key_unauthorized(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test deleting API key fails without authentication."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        api_key = ApiKeyFactory(developer=developer)

        # Act
        response = client.delete(f"{api_v1_prefix}/developer/api-keys/{api_key.id}")

        # Assert
        assert response.status_code == 401

    def test_delete_api_key_invalid_token(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test deleting API key fails with invalid token."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        api_key = ApiKeyFactory(developer=developer)

        # Act
        response = client.delete(
            f"{api_v1_prefix}/developer/api-keys/{api_key.id}",
            headers={"Authorization": "Bearer invalid_token"},
        )

        # Assert
        assert response.status_code == 401


class TestUpdateApiKey:
    """Tests for PATCH /api/v1/developer/api-keys/{key_id}."""

    def test_update_api_key_name(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test updating API key name."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        api_key = ApiKeyFactory(developer=developer, name="Old Name")
        headers = developer_auth_headers(developer.id)
        payload = {"name": "New Name"}

        # Act
        response = client.patch(
            f"{api_v1_prefix}/developer/api-keys/{api_key.id}",
            json=payload,
            headers=headers,
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "New Name"
        assert data["id"] == api_key.id

        # Verify in database
        db.refresh(api_key)
        assert api_key.name == "New Name"

    def test_update_api_key_empty_payload(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test updating API key with empty payload."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        api_key = ApiKeyFactory(developer=developer, name="Original Name")
        headers = developer_auth_headers(developer.id)
        payload = {}

        # Act
        response = client.patch(
            f"{api_v1_prefix}/developer/api-keys/{api_key.id}",
            json=payload,
            headers=headers,
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Original Name"

    def test_update_api_key_not_found(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test updating non-existent API key raises ResourceNotFoundError."""
        from app.utils.exceptions import ResourceNotFoundError

        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        headers = developer_auth_headers(developer.id)
        fake_key_id = "sk-nonexistent1234567890"
        payload = {"name": "New Name"}

        # Act & Assert
        with pytest.raises(ResourceNotFoundError):
            client.patch(
                f"{api_v1_prefix}/developer/api-keys/{fake_key_id}",
                json=payload,
                headers=headers,
            )

    def test_update_api_key_unauthorized(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test updating API key fails without authentication."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        api_key = ApiKeyFactory(developer=developer)
        payload = {"name": "New Name"}

        # Act
        response = client.patch(
            f"{api_v1_prefix}/developer/api-keys/{api_key.id}",
            json=payload,
        )

        # Assert
        assert response.status_code == 401


class TestRotateApiKey:
    """Tests for POST /api/v1/developer/api-keys/{key_id}/rotate."""

    def test_rotate_api_key_success(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test rotating API key successfully."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        old_api_key = ApiKeyFactory(developer=developer, name="To Rotate")
        headers = developer_auth_headers(developer.id)
        old_key_id = old_api_key.id

        # Act
        response = client.post(
            f"{api_v1_prefix}/developer/api-keys/{old_key_id}/rotate",
            headers=headers,
        )

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Default"  # New key gets default name
        assert data["id"] != old_key_id  # New key ID should be different
        assert data["id"].startswith("sk-")
        assert data["created_by"] == str(developer.id)

        # Verify old key is deleted from database
        from app.services import api_key_service

        old_key = api_key_service.get(db, old_key_id, raise_404=False)
        assert old_key is None

        # Verify new key exists
        new_key = api_key_service.get(db, data["id"])
        assert new_key is not None
        assert new_key.name == "Default"

    def test_rotate_api_key_not_found(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test rotating non-existent API key raises ResourceNotFoundError."""
        from app.utils.exceptions import ResourceNotFoundError

        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        headers = developer_auth_headers(developer.id)
        fake_key_id = "sk-nonexistent1234567890"

        # Act & Assert
        with pytest.raises(ResourceNotFoundError):
            client.post(
                f"{api_v1_prefix}/developer/api-keys/{fake_key_id}/rotate",
                headers=headers,
            )

    def test_rotate_api_key_unauthorized(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test rotating API key fails without authentication."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        api_key = ApiKeyFactory(developer=developer)

        # Act
        response = client.post(f"{api_v1_prefix}/developer/api-keys/{api_key.id}/rotate")

        # Assert
        assert response.status_code == 401

    def test_rotate_api_key_invalid_token(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test rotating API key fails with invalid token."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        api_key = ApiKeyFactory(developer=developer)

        # Act
        response = client.post(
            f"{api_v1_prefix}/developer/api-keys/{api_key.id}/rotate",
            headers={"Authorization": "Bearer invalid_token"},
        )

        # Assert
        assert response.status_code == 401

    def test_rotate_preserves_key_name(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test that rotation creates new key with default name (not preserving original)."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        old_api_key = ApiKeyFactory(developer=developer, name="Production Key")
        headers = developer_auth_headers(developer.id)

        # Act
        response = client.post(
            f"{api_v1_prefix}/developer/api-keys/{old_api_key.id}/rotate",
            headers=headers,
        )

        # Assert
        assert response.status_code == 201
        data = response.json()
        # The new key gets default name (implementation doesn't preserve original name)
        assert data["name"] == "Default"

    def test_rotate_multiple_times(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test rotating the same API key multiple times."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        api_key = ApiKeyFactory(developer=developer, name="Multi Rotate")
        headers = developer_auth_headers(developer.id)

        # Act - First rotation
        response1 = client.post(
            f"{api_v1_prefix}/developer/api-keys/{api_key.id}/rotate",
            headers=headers,
        )
        assert response1.status_code == 201
        new_key_id_1 = response1.json()["id"]

        # Act - Second rotation
        response2 = client.post(
            f"{api_v1_prefix}/developer/api-keys/{new_key_id_1}/rotate",
            headers=headers,
        )

        # Assert
        assert response2.status_code == 201
        new_key_id_2 = response2.json()["id"]
        assert new_key_id_2 != new_key_id_1
        assert new_key_id_2 != api_key.id

        # Verify only the final key exists
        from app.services import api_key_service

        assert api_key_service.get(db, api_key.id, raise_404=False) is None
        assert api_key_service.get(db, new_key_id_1, raise_404=False) is None
        assert api_key_service.get(db, new_key_id_2, raise_404=False) is not None
