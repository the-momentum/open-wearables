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

from tests.factories import UserConnectionFactory, UserFactory


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
        user = UserFactory()
        UserConnectionFactory(
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
        user = UserFactory()
        UserConnectionFactory(
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
        user1 = UserFactory()
        user2 = UserFactory()
        UserConnectionFactory(
            user=user1,
            provider="garmin",
            provider_user_id="garmin_user_1",
        )
        UserConnectionFactory(
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
        user = UserFactory()
        UserConnectionFactory(
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
        user = UserFactory()
        UserConnectionFactory(
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
        """Test successfully receiving and saving Garmin push notification."""
        # Arrange
        user = UserFactory()
        UserConnectionFactory(
            user=user,
            provider="garmin",
            provider_user_id="garmin_user_123",
        )
        headers = {"garmin-client-id": "test-client-id"}
        payload = {
            "activities": [
                {
                    "userId": "garmin_user_123",
                    "summaryId": "21047282990",
                    "activityId": 21047282990,
                    "activityName": "Morning Run",
                    "startTimeInSeconds": 1763597760,
                    "durationInSeconds": 3600,
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
        assert data["processed"] == 1
        assert data["saved"] == 1
        assert "errors" in data
        assert len(data["errors"]) == 0
        assert "activities" in data
        assert data["activities"][0]["status"] == "saved"
        assert "record_ids" in data["activities"][0]

    def test_push_webhook_user_not_found(
        self,
        client: TestClient,
        db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Test push webhook with unknown Garmin user."""
        # Arrange - no user connection created
        headers = {"garmin-client-id": "test-client-id"}
        payload = {
            "activities": [
                {
                    "userId": "unknown_garmin_user",
                    "activityId": 12345,
                    "activityName": "Test Activity",
                    "activityType": "RUNNING",
                    "startTimeInSeconds": 1763597760,
                    "durationInSeconds": 3600,
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
        assert data["processed"] == 0
        assert data["saved"] == 0
        assert len(data["errors"]) == 1
        assert data["activities"][0]["status"] == "user_not_found"

    def test_push_webhook_missing_client_id(self, client: TestClient, db: Session) -> None:
        """Test that push webhook requires garmin-client-id header."""
        # Arrange
        payload = {
            "activities": [
                {
                    "userId": "garmin_user_123",
                    "activityId": 12345,
                    "activityName": "Test Activity",
                    "activityType": "RUNNING",
                    "startTimeInSeconds": 1763597760,
                    "durationInSeconds": 3600,
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
        """Test push webhook with multiple activities from different users."""
        # Arrange
        user1 = UserFactory()
        user2 = UserFactory()
        UserConnectionFactory(
            user=user1,
            provider="garmin",
            provider_user_id="garmin_user_1",
        )
        UserConnectionFactory(
            user=user2,
            provider="garmin",
            provider_user_id="garmin_user_2",
        )
        headers = {"garmin-client-id": "test-client-id"}
        payload = {
            "activities": [
                {
                    "userId": "garmin_user_1",
                    "activityId": 12345,
                    "activityName": "Morning Run",
                    "activityType": "RUNNING",
                    "startTimeInSeconds": 1763597760,
                    "durationInSeconds": 3600,
                },
                {
                    "userId": "garmin_user_2",
                    "activityId": 67890,
                    "activityName": "Evening Bike",
                    "activityType": "CYCLING",
                    "startTimeInSeconds": 1763601360,
                    "durationInSeconds": 7200,
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
        assert data["processed"] == 2
        assert data["saved"] == 2
        assert len(data["activities"]) == 2

    def test_push_webhook_different_activity_types(
        self,
        client: TestClient,
        db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Test push webhook with different activity types."""
        # Arrange
        user = UserFactory()
        UserConnectionFactory(
            user=user,
            provider="garmin",
            provider_user_id="garmin_user_123",
        )
        headers = {"garmin-client-id": "test-client-id"}
        activity_types = ["RUNNING", "CYCLING", "SWIMMING", "WALKING"]
        payload = {
            "activities": [
                {
                    "userId": "garmin_user_123",
                    "activityId": 12345 + i,
                    "activityName": f"Activity {i}",
                    "activityType": activity_type,
                    "startTimeInSeconds": 1763597760 + (i * 3600),
                    "durationInSeconds": 1800,
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
        assert data["saved"] == len(activity_types)

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
        assert data["saved"] == 0


class TestGarminPushWebhookWellness:
    """Test suite for Garmin push webhook wellness data (HRV, sleeps, dailies, epochs)."""

    def test_push_webhook_hrv_data(
        self,
        client: TestClient,
        db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Test push webhook with HRV data."""
        # Arrange
        user = UserFactory()
        UserConnectionFactory(
            user=user,
            provider="garmin",
            provider_user_id="garmin_user_123",
        )
        headers = {"garmin-client-id": "test-client-id"}
        payload = {
            "hrv": [
                {
                    "userId": "garmin_user_123",
                    "summaryId": "x5b70ccc-6966bceb",
                    "calendarDate": "2026-01-14",
                    "lastNightAvg": 84,
                    "lastNight5MinHigh": 124,
                    "startTimeOffsetInSeconds": 3600,
                    "durationInSeconds": 36565,
                    "startTimeInSeconds": 1768340715,
                    "hrvValues": {
                        "265": 70,
                        "565": 73,
                        "865": 68,
                    },
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
        assert "wellness" in data
        assert "hrv" in data["wellness"]
        assert data["wellness"]["hrv"]["processed"] == 1
        assert data["wellness"]["hrv"]["saved"] > 0

    def test_push_webhook_epochs_batch_logging(
        self,
        client: TestClient,
        db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Test push webhook with multiple epochs (batch processing)."""
        # Arrange
        user = UserFactory()
        UserConnectionFactory(
            user=user,
            provider="garmin",
            provider_user_id="garmin_user_123",
        )
        headers = {"garmin-client-id": "test-client-id"}
        # Create 10 epochs to test batch processing
        payload = {
            "epochs": [
                {
                    "userId": "garmin_user_123",
                    "summaryId": f"epoch-{i}",
                    "activityType": "WALKING",
                    "activeKilocalories": 10,
                    "steps": 100 + i,
                    "distanceInMeters": 80.0,
                    "durationInSeconds": 900,
                    "activeTimeInSeconds": 300,
                    "startTimeInSeconds": 1768295700 + (i * 900),
                    "startTimeOffsetInSeconds": 3600,
                    "met": 2.5,
                    "intensity": "ACTIVE",
                }
                for i in range(10)
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
        assert "wellness" in data
        assert "epochs" in data["wellness"]
        assert data["wellness"]["epochs"]["processed"] == 10
        # Should log once per batch, not per epoch

    def test_push_webhook_dailies_data(
        self,
        client: TestClient,
        db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Test push webhook with dailies data."""
        # Arrange
        user = UserFactory()
        UserConnectionFactory(
            user=user,
            provider="garmin",
            provider_user_id="garmin_user_123",
        )
        headers = {"garmin-client-id": "test-client-id"}
        payload = {
            "dailies": [
                {
                    "userId": "garmin_user_123",
                    "summaryId": "daily-123",
                    "calendarDate": "2026-01-13",
                    "activityType": "GENERIC",
                    "activeKilocalories": 503,
                    "bmrKilocalories": 1825,
                    "steps": 7694,
                    "distanceInMeters": 6688.0,
                    "durationInSeconds": 77040,
                    "activeTimeInSeconds": 4821,
                    "startTimeInSeconds": 1768258800,
                    "startTimeOffsetInSeconds": 3600,
                    "moderateIntensityDurationInSeconds": 720,
                    "vigorousIntensityDurationInSeconds": 1680,
                    "floorsClimbed": 5,
                    "minHeartRateInBeatsPerMinute": 40,
                    "maxHeartRateInBeatsPerMinute": 167,
                    "averageHeartRateInBeatsPerMinute": 62,
                    "restingHeartRateInBeatsPerMinute": 43,
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
        assert "wellness" in data
        assert "dailies" in data["wellness"]
        assert data["wellness"]["dailies"]["processed"] == 1

    def test_push_webhook_sleeps_data(
        self,
        client: TestClient,
        db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Test push webhook with sleep data."""
        # Arrange
        user = UserFactory()
        UserConnectionFactory(
            user=user,
            provider="garmin",
            provider_user_id="garmin_user_123",
        )
        headers = {"garmin-client-id": "test-client-id"}
        payload = {
            "sleeps": [
                {
                    "userId": "garmin_user_123",
                    "summaryId": "sleep-123",
                    "calendarDate": "2026-01-13",
                    "startTimeInSeconds": 1768290000,
                    "durationInSeconds": 28800,
                    "startTimeOffsetInSeconds": 3600,
                    "validation": "AUTO_TENTATIVE",
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
        assert "wellness" in data
        assert "sleeps" in data["wellness"]
        assert data["wellness"]["sleeps"]["processed"] == 1


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
