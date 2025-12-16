"""
Tests for import data endpoints.

Tests the /api/v1/users/{user_id}/import endpoints including:
- POST /api/v1/users/{user_id}/import/apple/auto-health-export - test import health data
- POST /api/v1/users/{user_id}/import/apple/healthion - test import healthion data
- Authentication and authorization
- Error cases
"""

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.tests.utils import (
    api_key_headers,
    create_api_key,
    create_user,
)


class TestAutoHealthExportImport:
    """Test suite for Auto Health Export import endpoint."""

    def test_import_auto_health_export_json_success(
        self, client: TestClient, db: Session, mock_external_apis
    ):
        """Test successfully importing Auto Health Export JSON data."""
        # Arrange
        user = create_user(db)
        api_key = create_api_key(db)
        headers = api_key_headers(api_key.id)
        headers["Content-Type"] = "application/json"

        # Sample Auto Health Export format
        payload = {
            "data": {
                "workouts": [
                    {
                        "name": "Running",
                        "start": "2025-12-15T10:00:00Z",
                        "end": "2025-12-15T11:00:00Z",
                        "duration": 3600,
                    }
                ],
                "heart_rate": [
                    {"timestamp": "2025-12-15T10:00:00Z", "value": 72},
                    {"timestamp": "2025-12-15T10:01:00Z", "value": 85},
                ],
            }
        }

        # Act
        response = client.post(
            f"/api/v1/users/{user.id}/import/apple/auto-health-export",
            headers=headers,
            json=payload,
        )

        # Assert
        assert response.status_code in [200, 201, 202]
        data = response.json()
        assert "message" in data or "status" in data

    def test_import_auto_health_export_multipart_success(
        self, client: TestClient, db: Session, mock_external_apis
    ):
        """Test successfully importing Auto Health Export as file upload."""
        # Arrange
        user = create_user(db)
        api_key = create_api_key(db)
        headers = api_key_headers(api_key.id)

        payload = {
            "data": {
                "workouts": [
                    {
                        "name": "Cycling",
                        "start": "2025-12-15T14:00:00Z",
                        "end": "2025-12-15T15:30:00Z",
                        "duration": 5400,
                    }
                ]
            }
        }

        file_content = json.dumps(payload).encode("utf-8")
        files = {"file": ("export.json", file_content, "application/json")}

        # Act
        response = client.post(
            f"/api/v1/users/{user.id}/import/apple/auto-health-export",
            headers=headers,
            files=files,
        )

        # Assert
        assert response.status_code in [200, 201, 202]
        data = response.json()
        assert "message" in data or "status" in data

    def test_import_auto_health_export_empty_data(
        self, client: TestClient, db: Session, mock_external_apis
    ):
        """Test importing empty data."""
        # Arrange
        user = create_user(db)
        api_key = create_api_key(db)
        headers = api_key_headers(api_key.id)
        headers["Content-Type"] = "application/json"
        payload = {"data": {}}

        # Act
        response = client.post(
            f"/api/v1/users/{user.id}/import/apple/auto-health-export",
            headers=headers,
            json=payload,
        )

        # Assert
        assert response.status_code in [200, 201, 202, 400]

    def test_import_auto_health_export_missing_api_key(
        self, client: TestClient, db: Session
    ):
        """Test that request without API key is rejected."""
        # Arrange
        user = create_user(db)
        payload = {"data": {"workouts": []}}

        # Act
        response = client.post(
            f"/api/v1/users/{user.id}/import/apple/auto-health-export",
            json=payload,
        )

        # Assert
        assert response.status_code == 401

    def test_import_auto_health_export_invalid_api_key(
        self, client: TestClient, db: Session
    ):
        """Test that request with invalid API key is rejected."""
        # Arrange
        user = create_user(db)
        headers = api_key_headers("invalid-api-key")
        headers["Content-Type"] = "application/json"
        payload = {"data": {"workouts": []}}

        # Act
        response = client.post(
            f"/api/v1/users/{user.id}/import/apple/auto-health-export",
            headers=headers,
            json=payload,
        )

        # Assert
        assert response.status_code == 401

    def test_import_auto_health_export_invalid_user_id(
        self, client: TestClient, db: Session, mock_external_apis
    ):
        """Test handling of invalid user ID format."""
        # Arrange
        api_key = create_api_key(db)
        headers = api_key_headers(api_key.id)
        headers["Content-Type"] = "application/json"
        payload = {"data": {"workouts": []}}

        # Act
        response = client.post(
            "/api/v1/users/not-a-uuid/import/apple/auto-health-export",
            headers=headers,
            json=payload,
        )

        # Assert
        assert response.status_code == 422

    def test_import_auto_health_export_nonexistent_user(
        self, client: TestClient, db: Session, mock_external_apis
    ):
        """Test importing data for a user that doesn't exist."""
        # Arrange
        from uuid import uuid4

        api_key = create_api_key(db)
        headers = api_key_headers(api_key.id)
        headers["Content-Type"] = "application/json"
        nonexistent_user_id = uuid4()
        payload = {"data": {"workouts": []}}

        # Act
        response = client.post(
            f"/api/v1/users/{nonexistent_user_id}/import/apple/auto-health-export",
            headers=headers,
            json=payload,
        )

        # Assert
        # Depending on implementation, might be 404 or 200 with user creation
        assert response.status_code in [200, 201, 202, 404]


class TestHealthionImport:
    """Test suite for Healthion import endpoint."""

    def test_import_healthion_json_success(
        self, client: TestClient, db: Session, mock_external_apis
    ):
        """Test successfully importing Healthion JSON data."""
        # Arrange
        user = create_user(db)
        api_key = create_api_key(db)
        headers = api_key_headers(api_key.id)
        headers["Content-Type"] = "application/json"

        # Sample Healthion format
        payload = {
            "workouts": [
                {
                    "type": "HKWorkoutActivityTypeRunning",
                    "startDate": "2025-12-15T10:00:00Z",
                    "endDate": "2025-12-15T11:00:00Z",
                    "duration": 3600,
                }
            ],
            "records": [
                {
                    "type": "HKQuantityTypeIdentifierHeartRate",
                    "startDate": "2025-12-15T10:00:00Z",
                    "value": 72,
                    "unit": "count/min",
                }
            ],
        }

        # Act
        response = client.post(
            f"/api/v1/users/{user.id}/import/apple/healthion",
            headers=headers,
            json=payload,
        )

        # Assert
        assert response.status_code in [200, 201, 202]
        data = response.json()
        assert "message" in data or "status" in data

    def test_import_healthion_multipart_success(
        self, client: TestClient, db: Session, mock_external_apis
    ):
        """Test successfully importing Healthion as file upload."""
        # Arrange
        user = create_user(db)
        api_key = create_api_key(db)
        headers = api_key_headers(api_key.id)

        payload = {
            "workouts": [
                {
                    "type": "HKWorkoutActivityTypeCycling",
                    "startDate": "2025-12-15T14:00:00Z",
                    "endDate": "2025-12-15T15:30:00Z",
                    "duration": 5400,
                }
            ]
        }

        file_content = json.dumps(payload).encode("utf-8")
        files = {"file": ("healthion.json", file_content, "application/json")}

        # Act
        response = client.post(
            f"/api/v1/users/{user.id}/import/apple/healthion",
            headers=headers,
            files=files,
        )

        # Assert
        assert response.status_code in [200, 201, 202]
        data = response.json()
        assert "message" in data or "status" in data

    def test_import_healthion_empty_data(
        self, client: TestClient, db: Session, mock_external_apis
    ):
        """Test importing empty Healthion data."""
        # Arrange
        user = create_user(db)
        api_key = create_api_key(db)
        headers = api_key_headers(api_key.id)
        headers["Content-Type"] = "application/json"
        payload = {"workouts": [], "records": []}

        # Act
        response = client.post(
            f"/api/v1/users/{user.id}/import/apple/healthion",
            headers=headers,
            json=payload,
        )

        # Assert
        assert response.status_code in [200, 201, 202, 400]

    def test_import_healthion_missing_api_key(self, client: TestClient, db: Session):
        """Test that request without API key is rejected."""
        # Arrange
        user = create_user(db)
        payload = {"workouts": [], "records": []}

        # Act
        response = client.post(
            f"/api/v1/users/{user.id}/import/apple/healthion",
            json=payload,
        )

        # Assert
        assert response.status_code == 401

    def test_import_healthion_invalid_api_key(self, client: TestClient, db: Session):
        """Test that request with invalid API key is rejected."""
        # Arrange
        user = create_user(db)
        headers = api_key_headers("invalid-api-key")
        headers["Content-Type"] = "application/json"
        payload = {"workouts": [], "records": []}

        # Act
        response = client.post(
            f"/api/v1/users/{user.id}/import/apple/healthion",
            headers=headers,
            json=payload,
        )

        # Assert
        assert response.status_code == 401

    def test_import_healthion_invalid_user_id(
        self, client: TestClient, db: Session, mock_external_apis
    ):
        """Test handling of invalid user ID format."""
        # Arrange
        api_key = create_api_key(db)
        headers = api_key_headers(api_key.id)
        headers["Content-Type"] = "application/json"
        payload = {"workouts": [], "records": []}

        # Act
        response = client.post(
            "/api/v1/users/not-a-uuid/import/apple/healthion",
            headers=headers,
            json=payload,
        )

        # Assert
        assert response.status_code == 422

    def test_import_healthion_large_dataset(
        self, client: TestClient, db: Session, mock_external_apis
    ):
        """Test importing a large dataset."""
        # Arrange
        user = create_user(db)
        api_key = create_api_key(db)
        headers = api_key_headers(api_key.id)
        headers["Content-Type"] = "application/json"

        # Create a large payload with many records
        payload = {
            "workouts": [
                {
                    "type": "HKWorkoutActivityTypeRunning",
                    "startDate": f"2025-12-{15 - i:02d}T10:00:00Z",
                    "endDate": f"2025-12-{15 - i:02d}T11:00:00Z",
                    "duration": 3600,
                }
                for i in range(10)
            ],
            "records": [
                {
                    "type": "HKQuantityTypeIdentifierHeartRate",
                    "startDate": f"2025-12-15T10:{i:02d}:00Z",
                    "value": 70 + i,
                    "unit": "count/min",
                }
                for i in range(50)
            ],
        }

        # Act
        response = client.post(
            f"/api/v1/users/{user.id}/import/apple/healthion",
            headers=headers,
            json=payload,
        )

        # Assert
        assert response.status_code in [200, 201, 202]


class TestXMLImportEndpoint:
    """Test suite for XML import endpoint (presigned URL generation)."""

    def test_generate_presigned_url_success(
        self, client: TestClient, db: Session, mock_external_apis
    ):
        """Test successfully generating presigned URL for XML upload."""
        # Arrange
        user = create_user(db)
        api_key = create_api_key(db)
        headers = api_key_headers(api_key.id)
        payload = {
            "file_name": "export.xml",
            "content_type": "application/xml",
        }

        # Act
        response = client.post(
            f"/api/v1/users/{user.id}/import/apple/xml",
            headers=headers,
            json=payload,
        )

        # Assert
        assert response.status_code in [200, 201]
        data = response.json()
        assert "presigned_url" in data or "url" in data
        assert "expires_in" in data or "expires_at" in data

    def test_generate_presigned_url_missing_api_key(
        self, client: TestClient, db: Session
    ):
        """Test that presigned URL generation requires API key."""
        # Arrange
        user = create_user(db)
        payload = {
            "file_name": "export.xml",
            "content_type": "application/xml",
        }

        # Act
        response = client.post(
            f"/api/v1/users/{user.id}/import/apple/xml",
            json=payload,
        )

        # Assert
        assert response.status_code == 401

    def test_generate_presigned_url_invalid_payload(
        self, client: TestClient, db: Session, mock_external_apis
    ):
        """Test presigned URL generation with invalid payload."""
        # Arrange
        user = create_user(db)
        api_key = create_api_key(db)
        headers = api_key_headers(api_key.id)
        payload = {}  # Missing required fields

        # Act
        response = client.post(
            f"/api/v1/users/{user.id}/import/apple/xml",
            headers=headers,
            json=payload,
        )

        # Assert
        assert response.status_code == 422
