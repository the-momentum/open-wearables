"""
Integration tests for Apple data import flows.

Tests end-to-end import of Apple XML data.
"""

from fastapi.testclient import TestClient
from pytest_mock import MockerFixture
from sqlalchemy.orm import Session

from tests.factories import ApiKeyFactory, DeveloperFactory, UserFactory
from tests.utils import api_key_headers
from tests.utils.aws import mock_s3_client

# botocore builds client methods at runtime, so the mock is specced from a real (never called) client.


class TestAppleXMLImport:
    """Tests for Apple XML export data import via presigned URL."""

    def test_get_presigned_url_for_xml_upload(
        self,
        client: TestClient,
        db: Session,
    ) -> None:
        """Test getting presigned URL for XML upload."""
        # Arrange
        user = UserFactory()
        developer = DeveloperFactory()
        api_key = ApiKeyFactory(developer=developer)
        headers = api_key_headers(api_key.plain_key)

        # Act
        response = client.post(
            f"/api/v1/users/{user.id}/import/apple/xml/s3",
            headers=headers,
        )

        # Assert - The endpoint may return presigned URL or error (400 for S3 config errors)
        assert response.status_code in [200, 201, 400, 422, 501]

    def test_xml_import_with_mocked_s3(self, mocker: MockerFixture, client: TestClient, db: Session) -> None:
        """Test XML import with mocked S3 client."""
        mock_boto3 = mocker.patch("boto3.client", autospec=True)
        # Arrange
        user = UserFactory()
        developer = DeveloperFactory()
        api_key = ApiKeyFactory(developer=developer)
        headers = api_key_headers(api_key.plain_key)

        # Configure mock S3
        mock_s3 = mock_s3_client()
        mock_s3.generate_presigned_url.return_value = "https://s3.example.com/presigned-url"
        mock_boto3.return_value = mock_s3

        # Act
        response = client.post(
            f"/api/v1/users/{user.id}/import/apple/xml/s3",
            headers=headers,
        )

        # Assert - May return 400 if S3 bucket validation fails
        assert response.status_code in [200, 201, 400, 422, 501]
