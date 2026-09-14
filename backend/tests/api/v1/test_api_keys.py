"""
Tests for API key management endpoints.

Tests cover:
- GET /api/v1/developer/api-keys - list API keys (prefix only, never the raw key)
- POST /api/v1/developer/api-keys - create new API key (raw key returned once)
- DELETE /api/v1/developer/api-keys/{key_id} - delete API key
- PATCH /api/v1/developer/api-keys/{key_id} - update API key
- POST /api/v1/developer/api-keys/{key_id}/rotate - rotate API key (raw key returned once)
"""

from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.services import api_key_service
from tests.factories import ApiKeyFactory, DeveloperFactory
from tests.utils import api_key_headers, developer_auth_headers

READ_FIELDS = {"id", "name", "key_prefix", "created_by", "created_at"}


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

        found_keys = [k for k in data if k["id"] in {str(api_key1.id), str(api_key2.id)}]
        assert len(found_keys) == 2
        for key in found_keys:
            assert set(key) == READ_FIELDS

    def test_list_api_keys_never_exposes_raw_key(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """The response must contain only a prefix - not the raw key, nor its hash."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        api_key = ApiKeyFactory(developer=developer, name="Secret Key")
        headers = developer_auth_headers(developer.id)

        # Act
        response = client.get(f"{api_v1_prefix}/developer/api-keys", headers=headers)

        # Assert
        assert response.status_code == 200
        body = response.text
        assert api_key.plain_key not in body
        assert api_key.key_hash not in body
        item = next(k for k in response.json() if k["id"] == str(api_key.id))
        assert item["key_prefix"] == api_key.plain_key[:10]

    def test_list_api_keys_empty(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test listing API keys when there are none."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        headers = developer_auth_headers(developer.id)

        # Act
        response = client.get(f"{api_v1_prefix}/developer/api-keys", headers=headers)

        # Assert
        assert response.status_code == 200
        assert response.json() == []

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
        """Keys are global to the deployment: every developer sees all of them (prefix only)."""
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
        key_ids = [k["id"] for k in response.json()]
        assert str(key1.id) in key_ids
        assert str(key2.id) in key_ids
        assert key2.plain_key not in response.text


class TestCreateApiKey:
    """Tests for POST /api/v1/developer/api-keys."""

    def test_create_api_key_with_name(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test creating API key returns the raw key exactly once."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        headers = developer_auth_headers(developer.id)
        payload = {"name": "Production API Key"}

        # Act
        response = client.post(f"{api_v1_prefix}/developer/api-keys", json=payload, headers=headers)

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert set(data) == READ_FIELDS | {"key"}
        assert data["name"] == "Production API Key"
        assert data["key"].startswith("sk-")
        assert data["key_prefix"] == data["key"][:10]
        assert data["created_by"] == str(developer.id)

        # Verify in database: only the hash is stored
        api_key = api_key_service.get(db, UUID(data["id"]))
        assert api_key is not None
        assert api_key.name == "Production API Key"
        assert api_key.key_hash != data["key"]

    def test_created_key_authenticates_and_is_not_listed_again(
        self, client: TestClient, db: Session, api_v1_prefix: str
    ) -> None:
        """The raw key works for API auth, but never shows up in the list afterwards."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        headers = developer_auth_headers(developer.id)
        raw_key = client.post(f"{api_v1_prefix}/developer/api-keys", headers=headers).json()["key"]

        # Act
        auth_response = client.get(f"{api_v1_prefix}/users", headers=api_key_headers(raw_key))
        list_response = client.get(f"{api_v1_prefix}/developer/api-keys", headers=headers)

        # Assert
        assert auth_response.status_code == 200
        assert raw_key not in list_response.text

    def test_create_api_key_default_name(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test creating API key with default name."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        headers = developer_auth_headers(developer.id)

        # Act
        response = client.post(f"{api_v1_prefix}/developer/api-keys", json={}, headers=headers)

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Default"
        assert "key" in data

    def test_create_api_key_no_body(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test creating API key without request body."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        headers = developer_auth_headers(developer.id)

        # Act
        response = client.post(f"{api_v1_prefix}/developer/api-keys", headers=headers)

        # Assert
        assert response.status_code == 201
        assert response.json()["name"] == "Default"

    def test_create_api_key_empty_name(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test creating API key with empty name."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        headers = developer_auth_headers(developer.id)

        # Act
        response = client.post(f"{api_v1_prefix}/developer/api-keys", json={"name": ""}, headers=headers)

        # Assert
        assert response.status_code == 201
        assert response.json()["name"] == ""

    def test_create_api_key_unauthorized(self, client: TestClient, api_v1_prefix: str) -> None:
        """Test creating API key fails without authentication."""
        # Act
        response = client.post(f"{api_v1_prefix}/developer/api-keys", json={"name": "Test Key"})

        # Assert
        assert response.status_code == 401

    def test_create_multiple_api_keys(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test creating multiple API keys yields distinct keys."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        headers = developer_auth_headers(developer.id)

        # Act
        response1 = client.post(f"{api_v1_prefix}/developer/api-keys", json={"name": "Key 1"}, headers=headers)
        response2 = client.post(f"{api_v1_prefix}/developer/api-keys", json={"name": "Key 2"}, headers=headers)

        # Assert
        assert response1.status_code == 201
        assert response2.status_code == 201
        data1, data2 = response1.json(), response2.json()
        assert data1["id"] != data2["id"]
        assert data1["key"] != data2["key"]
        assert data1["name"] == "Key 1"
        assert data2["name"] == "Key 2"


class TestDeleteApiKey:
    """Tests for DELETE /api/v1/developer/api-keys/{key_id}."""

    def test_delete_api_key_success(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test deleting API key successfully revokes it."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        api_key = ApiKeyFactory(developer=developer, name="To Delete")
        headers = developer_auth_headers(developer.id)
        key_id = api_key.id
        raw_key = api_key.plain_key

        # Act
        response = client.delete(f"{api_v1_prefix}/developer/api-keys/{key_id}", headers=headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(key_id)
        assert data["name"] == "To Delete"
        assert "key" not in data

        assert api_key_service.get(db, key_id, raise_404=False) is None
        assert client.get(f"{api_v1_prefix}/users", headers=api_key_headers(raw_key)).status_code == 401

    def test_delete_api_key_not_found(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test deleting non-existent API key returns 404."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        headers = developer_auth_headers(developer.id)

        # Act
        response = client.delete(f"{api_v1_prefix}/developer/api-keys/{uuid4()}", headers=headers)

        # Assert
        assert response.status_code == 404

    def test_delete_api_key_by_raw_value_is_rejected(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Keys are addressed by UUID now, so the raw value is not a valid path parameter."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        api_key = ApiKeyFactory(developer=developer)
        headers = developer_auth_headers(developer.id)

        # Act
        response = client.delete(f"{api_v1_prefix}/developer/api-keys/{api_key.plain_key}", headers=headers)

        # Assert
        assert response.status_code == 400  # validation errors are mapped to 400 by the app
        assert api_key_service.get(db, api_key.id) is not None

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

        # Act
        response = client.patch(
            f"{api_v1_prefix}/developer/api-keys/{api_key.id}",
            json={"name": "New Name"},
            headers=headers,
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "New Name"
        assert data["id"] == str(api_key.id)
        assert "key" not in data

        db.refresh(api_key)
        assert api_key.name == "New Name"

    def test_update_api_key_empty_payload(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test updating API key with empty payload keeps the name."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        api_key = ApiKeyFactory(developer=developer, name="Original Name")
        headers = developer_auth_headers(developer.id)

        # Act
        response = client.patch(f"{api_v1_prefix}/developer/api-keys/{api_key.id}", json={}, headers=headers)

        # Assert
        assert response.status_code == 200
        assert response.json()["name"] == "Original Name"

    def test_update_api_key_not_found(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test updating non-existent API key returns 404."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        headers = developer_auth_headers(developer.id)

        # Act
        response = client.patch(
            f"{api_v1_prefix}/developer/api-keys/{uuid4()}",
            json={"name": "New Name"},
            headers=headers,
        )

        # Assert
        assert response.status_code == 404

    def test_update_api_key_unauthorized(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test updating API key fails without authentication."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        api_key = ApiKeyFactory(developer=developer)

        # Act
        response = client.patch(f"{api_v1_prefix}/developer/api-keys/{api_key.id}", json={"name": "New Name"})

        # Assert
        assert response.status_code == 401


class TestRotateApiKey:
    """Tests for POST /api/v1/developer/api-keys/{key_id}/rotate."""

    def test_rotate_api_key_success(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test rotating API key returns a fresh raw key once and revokes the old one."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        old_api_key = ApiKeyFactory(developer=developer, name="Production Key")
        headers = developer_auth_headers(developer.id)
        old_key_id = old_api_key.id
        old_raw_key = old_api_key.plain_key

        # Act
        response = client.post(f"{api_v1_prefix}/developer/api-keys/{old_key_id}/rotate", headers=headers)

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert set(data) == READ_FIELDS | {"key"}
        assert data["name"] == "Production Key"
        assert data["id"] != str(old_key_id)
        assert data["key"].startswith("sk-")
        assert data["key"] != old_raw_key
        assert data["created_by"] == str(developer.id)

        assert api_key_service.get(db, old_key_id, raise_404=False) is None
        new_key = api_key_service.get(db, UUID(data["id"]))
        assert new_key is not None
        assert new_key.name == "Production Key"

        assert client.get(f"{api_v1_prefix}/users", headers=api_key_headers(old_raw_key)).status_code == 401
        assert client.get(f"{api_v1_prefix}/users", headers=api_key_headers(data["key"])).status_code == 200

    def test_rotate_api_key_not_found(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test rotating non-existent API key returns 404."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        headers = developer_auth_headers(developer.id)

        # Act
        response = client.post(f"{api_v1_prefix}/developer/api-keys/{uuid4()}/rotate", headers=headers)

        # Assert
        assert response.status_code == 404

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

    def test_rotate_multiple_times(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        """Test rotating the same API key multiple times leaves only the final key."""
        # Arrange
        developer = DeveloperFactory(email="test@example.com", password="test123")
        api_key = ApiKeyFactory(developer=developer, name="Multi Rotate")
        headers = developer_auth_headers(developer.id)

        # Act
        response1 = client.post(f"{api_v1_prefix}/developer/api-keys/{api_key.id}/rotate", headers=headers)
        assert response1.status_code == 201
        new_key_id_1 = UUID(response1.json()["id"])

        response2 = client.post(f"{api_v1_prefix}/developer/api-keys/{new_key_id_1}/rotate", headers=headers)

        # Assert
        assert response2.status_code == 201
        new_key_id_2 = UUID(response2.json()["id"])
        assert new_key_id_2 != new_key_id_1
        assert new_key_id_2 != api_key.id

        assert api_key_service.get(db, api_key.id, raise_404=False) is None
        assert api_key_service.get(db, new_key_id_1, raise_404=False) is None
        assert api_key_service.get(db, new_key_id_2, raise_404=False) is not None
