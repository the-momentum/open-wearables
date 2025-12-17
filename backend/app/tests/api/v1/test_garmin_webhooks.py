"""
Tests for Garmin webhook endpoints.

Tests the /api/v1/garmin/webhooks endpoints including:
- POST /api/v1/garmin/webhooks/ping - test ping webhook
- POST /api/v1/garmin/webhooks/push - test push webhook
- GET /api/v1/garmin/webhooks/health - test health check
- Authentication and authorization
- Error cases
"""

from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.tests.utils import (
    create_user,
    create_user_connection,
)


class TestGarminPingWebhook:
    """Test suite for Garmin ping webhook endpoint."""

    def test_ping_webhook_success(
        self,
        client: TestClient,
        db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Test successfully receiving Garmin ping notification."""
        # Arrange
        user = create_user(db)
        create_user_connection(
            db,
            user=user,
            provider="garmin",
            provider_user_id="garmin_user_123",
        )
        headers = {"garmin-client-id": "test-client-id"}
        payload = {
            "activities": [
                {
                    "userId": "garmin_user_123",
                    "callbackURL": "https://apis.garmin.com/wellness-api/rest/activities?uploadStartTimeInSeconds=1234567890&uploadEndTimeInSeconds=1234567900&token=abc123",
                },
            ],
        }

        # Mock httpx response for callback URL
        mock_httpx = mock_external_apis["httpx"]
        mock_response = mock_httpx.return_value.__aenter__.return_value.get.return_value
        mock_response.__aenter__.return_value.status_code = 200
        mock_response.__aenter__.return_value.json.return_value = [
            {
                "activityId": 12345,
                "activityName": "Morning Run",
                "startTimeInSeconds": 1234567890,
            },
        ]

        # Act
        response = client.post(
            "/api/v1/garmin/webhooks/ping",
            headers=headers,
            json=payload,
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "processed" in data
        assert "errors" in data
        assert "activities" in data

    def test_ping_webhook_missing_client_id(self, client: TestClient, db: Session) -> None:
        """Test that ping webhook requires garmin-client-id header."""
        # Arrange
        payload = {
            "activities": [
                {
                    "userId": "garmin_user_123",
                    "callbackURL": "https://example.com/callback",
                },
            ],
        }

        # Act
        response = client.post(
            "/api/v1/garmin/webhooks/ping",
            json=payload,
        )

        # Assert
        assert response.status_code == 401

    def test_ping_webhook_unknown_user(
        self,
        client: TestClient,
        db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Test ping webhook with unknown Garmin user."""
        # Arrange
        headers = {"garmin-client-id": "test-client-id"}
        payload = {
            "activities": [
                {
                    "userId": "unknown_garmin_user",
                    "callbackURL": "https://example.com/callback",
                },
            ],
        }

        # Act
        response = client.post(
            "/api/v1/garmin/webhooks/ping",
            headers=headers,
            json=payload,
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "errors" in data
        assert len(data["errors"]) > 0

    def test_ping_webhook_no_callback_url(
        self,
        client: TestClient,
        db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Test ping webhook with missing callback URL."""
        # Arrange
        user = create_user(db)
        create_user_connection(
            db,
            user=user,
            provider="garmin",
            provider_user_id="garmin_user_123",
        )
        headers = {"garmin-client-id": "test-client-id"}
        payload = {
            "activities": [
                {
                    "userId": "garmin_user_123",
                    # Missing callbackURL
                },
            ],
        }

        # Act
        response = client.post(
            "/api/v1/garmin/webhooks/ping",
            headers=headers,
            json=payload,
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "processed" in data

    def test_ping_webhook_multiple_activities(
        self,
        client: TestClient,
        db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Test ping webhook with multiple activities."""
        # Arrange
        user1 = create_user(db)
        user2 = create_user(db)
        create_user_connection(
            db,
            user=user1,
            provider="garmin",
            provider_user_id="garmin_user_1",
        )
        create_user_connection(
            db,
            user=user2,
            provider="garmin",
            provider_user_id="garmin_user_2",
        )
        headers = {"garmin-client-id": "test-client-id"}
        payload = {
            "activities": [
                {
                    "userId": "garmin_user_1",
                    "callbackURL": "https://apis.garmin.com/wellness-api/rest/activities?token=token1",
                },
                {
                    "userId": "garmin_user_2",
                    "callbackURL": "https://apis.garmin.com/wellness-api/rest/activities?token=token2",
                },
            ],
        }

        # Mock httpx response
        mock_httpx = mock_external_apis["httpx"]
        mock_response = mock_httpx.return_value.__aenter__.return_value.get.return_value
        mock_response.__aenter__.return_value.status_code = 200
        mock_response.__aenter__.return_value.json.return_value = [{"activityId": 12345}]

        # Act
        response = client.post(
            "/api/v1/garmin/webhooks/ping",
            headers=headers,
            json=payload,
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "processed" in data
        assert "activities" in data

    def test_ping_webhook_with_summary_types(
        self,
        client: TestClient,
        db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Test ping webhook with different summary types."""
        # Arrange
        user = create_user(db)
        create_user_connection(
            db,
            user=user,
            provider="garmin",
            provider_user_id="garmin_user_123",
        )
        headers = {"garmin-client-id": "test-client-id"}
        payload = {
            "activities": [],
            "activityDetails": [{"userId": "garmin_user_123"}],
            "dailies": [{"userId": "garmin_user_123"}],
            "sleeps": [{"userId": "garmin_user_123"}],
        }

        # Act
        response = client.post(
            "/api/v1/garmin/webhooks/ping",
            headers=headers,
            json=payload,
        )

        # Assert
        assert response.status_code == 200

    def test_ping_webhook_callback_fetch_error(
        self,
        client: TestClient,
        db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Test ping webhook when callback URL fetch fails."""
        # Arrange
        user = create_user(db)
        create_user_connection(
            db,
            user=user,
            provider="garmin",
            provider_user_id="garmin_user_123",
        )
        headers = {"garmin-client-id": "test-client-id"}
        payload = {
            "activities": [
                {
                    "userId": "garmin_user_123",
                    "callbackURL": "https://apis.garmin.com/wellness-api/rest/activities?token=abc123",
                },
            ],
        }

        # Mock httpx to raise an error
        import httpx

        mock_httpx = mock_external_apis["httpx"]
        mock_response = mock_httpx.return_value.__aenter__.return_value.get
        mock_response.side_effect = httpx.HTTPError("Connection failed")

        # Act
        response = client.post(
            "/api/v1/garmin/webhooks/ping",
            headers=headers,
            json=payload,
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "errors" in data


class TestGarminPushWebhook:
    """Test suite for Garmin push webhook endpoint."""

    def test_push_webhook_success(
        self,
        client: TestClient,
        db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Test successfully receiving Garmin push notification."""
        # Arrange
        headers = {"garmin-client-id": "test-client-id"}
        payload = {
            "activities": [
                {
                    "userId": "garmin_user_123",
                    "summaryId": "21047282990",
                    "activityId": 21047282990,
                    "activityName": "Morning Run",
                    "startTimeInSeconds": 1763597760,
                    "startTimeOffsetInSeconds": 3600,
                    "activityType": "RUNNING",
                    "deviceName": "Forerunner 965",
                    "manual": False,
                    "isWebUpload": False,
                },
            ],
        }

        # Act
        response = client.post(
            "/api/v1/garmin/webhooks/push",
            headers=headers,
            json=payload,
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "processed" in data
        assert "errors" in data
        assert "activities" in data

    def test_push_webhook_missing_client_id(self, client: TestClient, db: Session) -> None:
        """Test that push webhook requires garmin-client-id header."""
        # Arrange
        payload = {
            "activities": [
                {
                    "userId": "garmin_user_123",
                    "activityId": 12345,
                    "activityName": "Test Activity",
                },
            ],
        }

        # Act
        response = client.post(
            "/api/v1/garmin/webhooks/push",
            json=payload,
        )

        # Assert
        assert response.status_code == 401

    def test_push_webhook_multiple_activities(
        self,
        client: TestClient,
        db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Test push webhook with multiple activities."""
        # Arrange
        headers = {"garmin-client-id": "test-client-id"}
        payload = {
            "activities": [
                {
                    "userId": "garmin_user_1",
                    "activityId": 12345,
                    "activityName": "Morning Run",
                    "activityType": "RUNNING",
                },
                {
                    "userId": "garmin_user_2",
                    "activityId": 67890,
                    "activityName": "Evening Bike",
                    "activityType": "CYCLING",
                },
            ],
        }

        # Act
        response = client.post(
            "/api/v1/garmin/webhooks/push",
            headers=headers,
            json=payload,
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "processed" in data
        assert data["processed"] == 2
        assert len(data["activities"]) == 2

    def test_push_webhook_different_activity_types(
        self,
        client: TestClient,
        db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Test push webhook with different activity types."""
        # Arrange
        headers = {"garmin-client-id": "test-client-id"}
        activity_types = ["RUNNING", "CYCLING", "SWIMMING", "WALKING"]
        payload = {
            "activities": [
                {
                    "userId": "garmin_user_123",
                    "activityId": 12345 + i,
                    "activityName": f"Activity {i}",
                    "activityType": activity_type,
                }
                for i, activity_type in enumerate(activity_types)
            ],
        }

        # Act
        response = client.post(
            "/api/v1/garmin/webhooks/push",
            headers=headers,
            json=payload,
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["processed"] == len(activity_types)

    def test_push_webhook_empty_activities(
        self,
        client: TestClient,
        db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Test push webhook with empty activities list."""
        # Arrange
        headers = {"garmin-client-id": "test-client-id"}
        payload = {"activities": []}

        # Act
        response = client.post(
            "/api/v1/garmin/webhooks/push",
            headers=headers,
            json=payload,
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["processed"] == 0


class TestGarminWebhookHealth:
    """Test suite for Garmin webhook health check endpoint."""

    def test_health_check_success(self, client: TestClient, db: Session) -> None:
        """Test that health check returns OK."""
        # Act
        response = client.get("/api/v1/garmin/webhooks/health")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "service" in data
        assert data["service"] == "garmin-webhooks"

    def test_health_check_no_auth_required(self, client: TestClient, db: Session) -> None:
        """Test that health check doesn't require authentication."""
        # Act - no headers
        response = client.get("/api/v1/garmin/webhooks/health")

        # Assert
        assert response.status_code == 200

    def test_health_check_response_structure(self, client: TestClient, db: Session) -> None:
        """Test health check response structure."""
        # Act
        response = client.get("/api/v1/garmin/webhooks/health")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        assert "status" in data
        assert "service" in data
