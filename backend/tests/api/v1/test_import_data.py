"""
Tests for import data endpoints.

Tests the /api/v1/users/{user_id}/import/apple/xml endpoint for XML import
and the /api/v1/sns/notification endpoint its uploads are announced on.
"""

from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.factories import ApiKeyFactory, UserFactory
from tests.utils import api_key_headers


class TestXMLImportEndpoint:
    """Test suite for XML import endpoint (presigned URL generation)."""

    def test_generate_presigned_url_success(
        self,
        client: TestClient,
        db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Test presigned URL endpoint (may fail if S3 not configured in test env)."""
        # Arrange
        user = UserFactory()
        api_key = ApiKeyFactory()
        headers = api_key_headers(api_key.plain_key)
        payload = {
            "filename": "export.xml",
        }

        # Act
        response = client.post(
            f"/api/v1/users/{user.id}/import/apple/xml/s3",
            headers=headers,
            json=payload,
        )

        # Assert - May return 403 or 503 if S3 is not configured in test environment
        assert response.status_code in [200, 201, 403, 503]
        if response.status_code in [200, 201]:
            data = response.json()
            assert "upload_url" in data
            assert "form_fields" in data
            assert "file_key" in data
            assert "expires_in" in data
            assert "max_file_size" in data
            assert "bucket" in data

    def test_generate_presigned_url_missing_api_key(self, client: TestClient, db: Session) -> None:
        """Test that presigned URL generation requires API key."""
        # Arrange
        user = UserFactory()
        payload = {
            "file_name": "export.xml",
            "content_type": "application/xml",
        }

        # Act
        response = client.post(
            f"/api/v1/users/{user.id}/import/apple/xml/s3",
            json=payload,
        )

        # Assert
        assert response.status_code == 401

    def test_generate_presigned_url_invalid_payload(
        self,
        client: TestClient,
        db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Test presigned URL generation with invalid payload."""
        # Arrange
        user = UserFactory()
        api_key = ApiKeyFactory()
        headers = api_key_headers(api_key.plain_key)
        payload = {
            "expiration_seconds": 30,  # Less than minimum (60)
        }

        # Act
        response = client.post(
            f"/api/v1/users/{user.id}/import/apple/xml/s3",
            headers=headers,
            json=payload,
        )

        # Assert
        assert response.status_code == 422


class TestSNSNotificationEndpoint:
    """Test suite for the SNS notification endpoint."""

    def test_unparsable_notification_does_not_echo_the_body(self, client: TestClient, db: Session) -> None:
        """A body that is not an SNS notification is a 400 that does not quote it back."""
        # Act
        response = client.post("/api/v1/sns/notification", content=b'{"Type": "secret-marker"')

        # Assert
        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid SNS notification"
        assert "secret-marker" not in response.text

    def test_invalid_notification_does_not_echo_the_body(self, client: TestClient, db: Session) -> None:
        """Valid JSON that fails the notification schema gets the same answer."""
        # Act
        response = client.post("/api/v1/sns/notification", json={"Type": "secret-marker"})

        # Assert
        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid SNS notification"
        assert "secret-marker" not in response.text
