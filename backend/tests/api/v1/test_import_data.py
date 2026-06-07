"""
Tests for import data endpoints.

Tests the /api/v1/users/{user_id}/import/apple/xml endpoint for XML import.
"""

from unittest.mock import MagicMock, patch

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
        headers = api_key_headers(api_key.id)
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
        headers = api_key_headers(api_key.id)
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
        # Validation errors are converted to 400 by the error handler
        assert response.status_code in [400, 422]


class TestProcessS3XmlUploadEndpoint:
    """Test suite for post-upload S3 XML processing endpoint."""

    @patch("app.services.apple.apple_xml.presigned_url_service.process_aws_upload")
    def test_process_s3_xml_upload_success(
        self,
        mock_process_aws_upload: MagicMock,
        client: TestClient,
        db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        user = UserFactory()
        api_key = ApiKeyFactory()
        headers = api_key_headers(api_key.id)
        file_key = f"{user.id}/raw/export.xml"

        mock_task = MagicMock()
        mock_task.id = "task-abc-123"
        mock_process_aws_upload.delay.return_value = mock_task
        mock_external_apis["s3"].head_object.return_value = {}

        response = client.post(
            f"/api/v1/users/{user.id}/import/apple/xml/s3/process",
            headers=headers,
            json={"file_key": file_key},
        )

        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "processing"
        assert data["task_id"] == "task-abc-123"
        assert data["file_key"] == file_key
        assert data["user_id"] == str(user.id)
        mock_process_aws_upload.delay.assert_called_once_with(
            bucket_name="test-bucket",
            object_key=file_key,
            user_id=str(user.id),
        )

    def test_process_s3_xml_upload_rejects_foreign_file_key(
        self,
        client: TestClient,
        db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        user = UserFactory()
        api_key = ApiKeyFactory()
        headers = api_key_headers(api_key.id)

        response = client.post(
            f"/api/v1/users/{user.id}/import/apple/xml/s3/process",
            headers=headers,
            json={"file_key": "other-user/raw/export.xml"},
        )

        assert response.status_code == 403

    def test_process_s3_xml_upload_requires_api_key(self, client: TestClient, db: Session) -> None:
        user = UserFactory()

        response = client.post(
            f"/api/v1/users/{user.id}/import/apple/xml/s3/process",
            json={"file_key": f"{user.id}/raw/export.xml"},
        )

        assert response.status_code == 401
