"""
Tests for Garmin webhook handling via the unified provider webhook router.

Tests the /api/v1/providers/garmin/webhooks endpoint including:
- POST /api/v1/providers/garmin/webhooks - PUSH events
- GET /api/v1/providers/garmin/webhooks - subscription challenge (501 for Garmin)
- Authentication and authorization
- Error cases
- userPermissions webhooks
- deregistrations webhooks
"""

from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.schemas.auth import ConnectionStatus
from tests.factories import UserConnectionFactory, UserFactory


class TestGarminCallbackUrlNotification:
    """Garmin PING (callbackURL) is not supported — notifications are skipped."""

    def test_callback_url_activity_is_skipped(
        self,
        client: TestClient,
        db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Activity notification with callbackURL must return status='skipped'."""
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
                    "callbackURL": "https://apis.garmin.com/wellness-api/rest/activities?token=abc",
                },
            ],
        }

        response = client.post("/api/v1/providers/garmin/webhooks", headers=headers, json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["processed"] == 0
        assert data["saved"] == 0
        assert data["activities"][0]["status"] == "skipped"

    def test_callback_url_missing_auth_returns_401(self, client: TestClient, db: Session) -> None:
        """Garmin-client-id is still required even for callbackURL notifications."""
        payload = {"activities": [{"userId": "garmin_user_123", "callbackURL": "https://example.com/cb"}]}
        response = client.post("/api/v1/providers/garmin/webhooks", json=payload)
        assert response.status_code == 401

    def test_callback_url_unknown_user_returns_error(
        self,
        client: TestClient,
        db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Unknown Garmin user is reported in errors before callbackURL check."""
        headers = {"garmin-client-id": "test-client-id"}
        payload = {"activities": [{"userId": "unknown_user", "callbackURL": "https://example.com/cb"}]}

        response = client.post("/api/v1/providers/garmin/webhooks", headers=headers, json=payload)

        assert response.status_code == 200
        data = response.json()
        assert len(data["errors"]) > 0
        assert data["activities"][0]["status"] == "user_not_found"


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
            "/api/v1/providers/garmin/webhooks",
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
            "/api/v1/providers/garmin/webhooks",
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
            "/api/v1/providers/garmin/webhooks",
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
            "/api/v1/providers/garmin/webhooks",
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
            "/api/v1/providers/garmin/webhooks",
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
            "/api/v1/providers/garmin/webhooks",
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
            "/api/v1/providers/garmin/webhooks",
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

    def test_push_webhook_pulseox_data(
        self,
        client: TestClient,
        db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Test push webhook processes pulseox payload key."""
        # Arrange
        user = UserFactory()
        UserConnectionFactory(
            user=user,
            provider="garmin",
            provider_user_id="garmin_user_123",
        )
        headers = {"garmin-client-id": "test-client-id"}
        payload = {
            "pulseox": [
                {
                    "userId": "garmin_user_123",
                    "summaryId": "pulseox-123",
                    "startTimeInSeconds": 1768340715,
                    "startTimeOffsetInSeconds": 3600,
                    "timeOffsetSpo2Values": {
                        "0": 94,
                        "60": 93,
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
        assert "pulseox" in data["wellness"]
        assert data["wellness"]["pulseox"]["processed"] == 1
        assert data["wellness"]["pulseox"]["saved"] > 0

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
            "/api/v1/providers/garmin/webhooks",
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
            "/api/v1/providers/garmin/webhooks",
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
            "/api/v1/providers/garmin/webhooks",
            headers=headers,
            json=payload,
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "wellness" in data
        assert "sleeps" in data["wellness"]
        assert data["wellness"]["sleeps"]["processed"] == 1


class TestGarminWebhookRouting:
    """Test suite for Garmin webhook routing via the unified provider router."""

    def test_get_challenge_returns_501(self, client: TestClient, db: Session) -> None:
        """Garmin does not support GET subscription challenges — expect 501."""
        response = client.get("/api/v1/providers/garmin/webhooks")
        assert response.status_code == 501

    def test_unknown_provider_returns_404(self, client: TestClient, db: Session) -> None:
        """Unknown provider names return 404."""
        response = client.post(
            "/api/v1/providers/unknown_provider/webhooks",
            headers={"garmin-client-id": "x"},
            json={},
        )
        assert response.status_code == 404


class TestGarminUserPermissionsWebhook:
    """Test suite for Garmin userPermissionsChange webhook handling."""

    def test_push_webhook_permissions_scope_expanded(
        self,
        client: TestClient,
        db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Test that scope is expanded when user grants more permissions."""
        # Arrange
        user = UserFactory()
        connection = UserConnectionFactory(
            user=user,
            provider="garmin",
            provider_user_id="garmin_user_123",
            scope="ACTIVITY_EXPORT",
        )
        headers = {"garmin-client-id": "test-client-id"}
        payload = {
            "userPermissionsChange": [
                {
                    "userId": "garmin_user_123",
                    "permissions": ["ACTIVITY_EXPORT", "HEALTH_EXPORT", "WELLNESS_EXPORT"],
                },
            ],
        }

        # Act
        response = client.post(
            "/api/v1/providers/garmin/webhooks",
            headers=headers,
            json=payload,
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "userPermissionsChange" in data
        assert data["userPermissionsChange"]["updated"] == 1
        assert len(data["userPermissionsChange"]["errors"]) == 0

        # Verify DB was updated - scope expanded
        db.refresh(connection)
        assert connection.scope == "ACTIVITY_EXPORT HEALTH_EXPORT WELLNESS_EXPORT"

    def test_push_webhook_permissions_scope_reduced(
        self,
        client: TestClient,
        db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Test that scope is reduced when user revokes permissions."""
        # Arrange
        user = UserFactory()
        connection = UserConnectionFactory(
            user=user,
            provider="garmin",
            provider_user_id="garmin_user_123",
            scope="ACTIVITY_EXPORT HEALTH_EXPORT WELLNESS_EXPORT",
        )
        headers = {"garmin-client-id": "test-client-id"}
        payload = {
            "userPermissionsChange": [
                {
                    "userId": "garmin_user_123",
                    "permissions": ["ACTIVITY_EXPORT"],
                },
            ],
        }

        # Act
        response = client.post(
            "/api/v1/providers/garmin/webhooks",
            headers=headers,
            json=payload,
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "userPermissionsChange" in data
        assert data["userPermissionsChange"]["updated"] == 1
        assert len(data["userPermissionsChange"]["errors"]) == 0

        # Verify DB was updated - scope reduced
        db.refresh(connection)
        assert connection.scope == "ACTIVITY_EXPORT"

    def test_push_webhook_permissions_scope_unchanged(
        self,
        client: TestClient,
        db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Test that scope remains the same when permissions haven't changed."""
        # Arrange
        user = UserFactory()
        connection = UserConnectionFactory(
            user=user,
            provider="garmin",
            provider_user_id="garmin_user_123",
            scope="ACTIVITY_EXPORT HEALTH_EXPORT",
        )
        headers = {"garmin-client-id": "test-client-id"}
        payload = {
            "userPermissionsChange": [
                {
                    "userId": "garmin_user_123",
                    "permissions": ["HEALTH_EXPORT", "ACTIVITY_EXPORT"],
                },
            ],
        }

        # Act
        response = client.post(
            "/api/v1/providers/garmin/webhooks",
            headers=headers,
            json=payload,
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "userPermissionsChange" in data
        assert data["userPermissionsChange"]["updated"] == 1

        # Verify DB scope unchanged (sorted order matches)
        db.refresh(connection)
        assert connection.scope == "ACTIVITY_EXPORT HEALTH_EXPORT"

    def test_push_webhook_user_permissions_unknown_user(
        self,
        client: TestClient,
        db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Test userPermissionsChange webhook with unknown user is a no-op (idempotent)."""
        # Arrange
        headers = {"garmin-client-id": "test-client-id"}
        payload = {
            "userPermissionsChange": [
                {
                    "userId": "unknown_garmin_user",
                    "permissions": ["ACTIVITY_EXPORT"],
                },
            ],
        }

        # Act
        response = client.post(
            "/api/v1/providers/garmin/webhooks",
            headers=headers,
            json=payload,
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "userPermissionsChange" in data
        assert data["userPermissionsChange"]["updated"] == 0
        assert len(data["userPermissionsChange"]["errors"]) == 0

    def test_ping_webhook_user_permissions_updates_scope(
        self,
        client: TestClient,
        db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Test that userPermissionsChange in ping webhook also updates scope."""
        # Arrange
        user = UserFactory()
        connection = UserConnectionFactory(
            user=user,
            provider="garmin",
            provider_user_id="garmin_user_123",
            scope="OLD_SCOPE",
        )
        headers = {"garmin-client-id": "test-client-id"}
        payload = {
            "userPermissionsChange": [
                {
                    "userId": "garmin_user_123",
                    "permissions": ["ACTIVITY_EXPORT", "WELLNESS_EXPORT"],
                },
            ],
        }

        # Act
        response = client.post(
            "/api/v1/providers/garmin/webhooks",
            headers=headers,
            json=payload,
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "userPermissionsChange" in data
        assert data["userPermissionsChange"]["updated"] == 1

        # Verify DB was updated
        db.refresh(connection)
        assert connection.scope == "ACTIVITY_EXPORT WELLNESS_EXPORT"


class TestGarminDeregistrationWebhook:
    """Test suite for Garmin deregistration webhook handling."""

    def test_push_webhook_deregistration_revokes_connection(
        self,
        client: TestClient,
        db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Test that deregistration webhook revokes the connection."""
        # Arrange
        user = UserFactory()
        connection = UserConnectionFactory(
            user=user,
            provider="garmin",
            provider_user_id="garmin_user_123",
        )
        assert connection.status == ConnectionStatus.ACTIVE

        headers = {"garmin-client-id": "test-client-id"}
        payload = {
            "deregistrations": [
                {"userId": "garmin_user_123"},
            ],
        }

        # Act
        response = client.post(
            "/api/v1/providers/garmin/webhooks",
            headers=headers,
            json=payload,
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "deregistrations" in data
        assert data["deregistrations"]["revoked"] == 1
        assert len(data["deregistrations"]["errors"]) == 0

        # Verify DB was updated
        db.refresh(connection)
        assert connection.status == ConnectionStatus.REVOKED

    def test_push_webhook_deregistration_unknown_user(
        self,
        client: TestClient,
        db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Test deregistration webhook with unknown user is a no-op (idempotent)."""
        # Arrange
        headers = {"garmin-client-id": "test-client-id"}
        payload = {
            "deregistrations": [
                {"userId": "unknown_garmin_user"},
            ],
        }

        # Act
        response = client.post(
            "/api/v1/providers/garmin/webhooks",
            headers=headers,
            json=payload,
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "deregistrations" in data
        assert data["deregistrations"]["revoked"] == 0
        assert len(data["deregistrations"]["errors"]) == 0
