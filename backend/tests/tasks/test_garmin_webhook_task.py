"""
Tests for Garmin webhook Celery tasks.

Tests process_push and process_ping tasks for:
- Activity saving and user-not-found handling
- Wellness data (HRV, dailies, sleeps, epochs) saving
- userPermissionsChange scope updates (DB state verified)
- Deregistration connection revocation (DB state verified)
- Ping callback URL fetching and error handling
"""

from unittest.mock import MagicMock, patch

import pytest
from celery.exceptions import Retry
from sqlalchemy.orm import Session

from app.integrations.celery.tasks.garmin_webhook_task import process_ping, process_push
from app.schemas.auth import ConnectionStatus
from tests.factories import UserConnectionFactory, UserFactory

MODULE = "app.integrations.celery.tasks.garmin_webhook_task"


@pytest.fixture(autouse=True)
def _backfill_patches() -> None:
    """Patch Redis-dependent backfill helpers to return safe defaults for all tests."""
    with (
        patch(f"{MODULE}.get_backfill_status", return_value={"overall_status": "idle"}),
        patch(f"{MODULE}.get_trace_id", return_value=None),
        patch(f"{MODULE}.mark_type_success", return_value=False),
    ):
        yield


@pytest.fixture
def task_db(db: Session) -> Session:
    """
    Patch SessionLocal to return the test database session so that tasks
    operate on the same transaction as the test, and wrap close() to prevent
    premature session teardown.
    """
    with (
        patch(f"{MODULE}.SessionLocal", return_value=db),
        patch.object(db, "close", MagicMock()),
    ):
        yield db


class TestGarminPushWebhook:
    """Tests for process_push Celery task — activities and wellness data types."""

    def test_push_webhook_success(
        self,
        task_db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Test successfully receiving and saving a Garmin push activity."""
        # Arrange
        user = UserFactory()
        UserConnectionFactory(
            user=user,
            provider="garmin",
            provider_user_id="garmin_user_123",
        )
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
        result = process_push.run(payload, "trace-001")

        # Assert
        assert result["processed"] == 1
        assert result["saved"] == 1
        assert len(result["errors"]) == 0
        assert result["activities"][0]["status"] == "saved"
        assert "record_ids" in result["activities"][0]

    def test_push_webhook_user_not_found(
        self,
        task_db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Test push webhook with unknown Garmin user."""
        # Arrange - no user connection created
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
        result = process_push.run(payload, "trace-002")

        # Assert
        assert result["processed"] == 0
        assert result["saved"] == 0
        assert len(result["errors"]) == 1
        assert result["activities"][0]["status"] == "user_not_found"

    def test_push_webhook_multiple_activities(
        self,
        task_db: Session,
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
        result = process_push.run(payload, "trace-003")

        # Assert
        assert result["processed"] == 2
        assert result["saved"] == 2
        assert len(result["activities"]) == 2

    def test_push_webhook_different_activity_types(
        self,
        task_db: Session,
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
        result = process_push.run(payload, "trace-004")

        # Assert
        assert result["processed"] == len(activity_types)
        assert result["saved"] == len(activity_types)

    def test_push_webhook_empty_activities(
        self,
        task_db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Test push webhook with empty activities list."""
        # Arrange
        payload = {"activities": []}

        # Act
        result = process_push.run(payload, "trace-005")

        # Assert
        assert result["processed"] == 0
        assert result["saved"] == 0

    def test_push_webhook_activity_validation_error(
        self,
        task_db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Activity missing required fields triggers ValidationError → status validation_error."""
        # Arrange
        user = UserFactory()
        UserConnectionFactory(
            user=user,
            provider="garmin",
            provider_user_id="garmin_user_123",
        )
        # Missing required `durationInSeconds` → GarminActivityJSON raises ValidationError
        payload = {
            "activities": [
                {
                    "userId": "garmin_user_123",
                    "activityId": 99999,
                    "activityName": "Bad Activity",
                    "activityType": "RUNNING",
                    "startTimeInSeconds": 1763597760,
                    # durationInSeconds intentionally omitted
                },
            ],
        }

        # Act
        result = process_push.run(payload, "trace-006")

        # Assert
        assert result["activities"][0]["status"] == "validation_error"
        assert len(result["errors"]) == 1

    def test_push_webhook_workouts_service_unavailable(
        self,
        task_db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Push task returns an error dict when GarminWorkouts service is unavailable."""
        with patch(f"{MODULE}.ProviderFactory") as mock_factory:
            mock_strategy = MagicMock()
            # workouts is not a GarminWorkouts instance → triggers early return
            mock_strategy.workouts = object()
            mock_factory.return_value.get_provider.return_value = mock_strategy

            result = process_push.run({"activities": []}, "trace-007")

        assert result == {"error": "Garmin workouts service not available"}

    def test_push_webhook_hrv_data(
        self,
        task_db: Session,
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
                    "hrvValues": {"265": 70, "565": 73, "865": 68},
                },
            ],
        }

        # Act
        result = process_push.run(payload, "trace-010")

        # Assert
        assert "wellness" in result
        assert "hrv" in result["wellness"]
        assert result["wellness"]["hrv"]["processed"] == 1
        assert result["wellness"]["hrv"]["saved"] > 0

    def test_push_webhook_epochs_batch_logging(
        self,
        task_db: Session,
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
        result = process_push.run(payload, "trace-011")

        # Assert
        assert "wellness" in result
        assert "epochs" in result["wellness"]
        assert result["wellness"]["epochs"]["processed"] == 10

    def test_push_webhook_dailies_data(
        self,
        task_db: Session,
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
        result = process_push.run(payload, "trace-012")

        # Assert
        assert "wellness" in result
        assert "dailies" in result["wellness"]
        assert result["wellness"]["dailies"]["processed"] == 1

    def test_push_webhook_sleeps_data(
        self,
        task_db: Session,
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
        result = process_push.run(payload, "trace-013")

        # Assert
        assert "wellness" in result
        assert "sleeps" in result["wellness"]
        assert result["wellness"]["sleeps"]["processed"] == 1

    def test_push_webhook_wellness_unknown_user_skipped(
        self,
        task_db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Wellness data for unknown Garmin user is skipped — processed==1, saved==0."""
        # No connection created — user is unknown
        payload = {
            "dailies": [
                {
                    "userId": "unknown_garmin_user",
                    "summaryId": "daily-999",
                    "calendarDate": "2026-01-14",
                    "activityType": "GENERIC",
                    "activeKilocalories": 100,
                    "bmrKilocalories": 1500,
                    "steps": 1000,
                    "distanceInMeters": 800.0,
                    "durationInSeconds": 77040,
                    "activeTimeInSeconds": 1000,
                    "startTimeInSeconds": 1768258800,
                    "startTimeOffsetInSeconds": 3600,
                },
            ],
        }

        # Act
        result = process_push.run(payload, "trace-014")

        # Assert — item is counted as processed but nothing was saved
        assert "wellness" in result
        assert "dailies" in result["wellness"]
        assert result["wellness"]["dailies"]["processed"] == 1
        assert result["wellness"]["dailies"]["saved"] == 0

    def test_push_webhook_backfill_chaining_triggered(
        self,
        task_db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Backfill next type is triggered when a new type success occurs during active backfill."""
        user = UserFactory()
        UserConnectionFactory(
            user=user,
            provider="garmin",
            provider_user_id="garmin_user_123",
        )
        payload = {
            "dailies": [
                {
                    "userId": "garmin_user_123",
                    "summaryId": "daily-backfill",
                    "calendarDate": "2026-01-14",
                    "activityType": "GENERIC",
                    "activeKilocalories": 503,
                    "bmrKilocalories": 1825,
                    "steps": 7694,
                    "distanceInMeters": 6688.0,
                    "durationInSeconds": 77040,
                    "activeTimeInSeconds": 4821,
                    "startTimeInSeconds": 1768258800,
                    "startTimeOffsetInSeconds": 3600,
                },
            ],
        }

        # Act — override autouse patches to simulate an active backfill
        with (
            patch(f"{MODULE}.mark_type_success", return_value=True),
            patch(
                f"{MODULE}.get_backfill_status",
                return_value={"overall_status": "in_progress", "current_window": 1, "total_windows": 5},
            ),
            patch(f"{MODULE}.trigger_next_pending_type") as mock_trigger,
        ):
            result = process_push.run(payload, "trace-015")

        # Assert — backfill chaining was triggered
        assert len(result["backfill_chained"]) == 1
        mock_trigger.delay.assert_called_once()


class TestGarminUserPermissionsWebhook:
    """Tests for userPermissionsChange handling — both process_push and process_ping."""

    def test_push_webhook_permissions_scope_expanded(
        self,
        task_db: Session,
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
        payload = {
            "userPermissionsChange": [
                {
                    "userId": "garmin_user_123",
                    "permissions": ["ACTIVITY_EXPORT", "HEALTH_EXPORT", "WELLNESS_EXPORT"],
                },
            ],
        }

        # Act
        result = process_push.run(payload, "trace-020")

        # Assert
        assert "userPermissionsChange" in result
        assert result["userPermissionsChange"]["updated"] == 1
        assert len(result["userPermissionsChange"]["errors"]) == 0

        # Verify DB was updated - scope expanded
        task_db.refresh(connection)
        assert connection.scope == "ACTIVITY_EXPORT HEALTH_EXPORT WELLNESS_EXPORT"

    def test_push_webhook_permissions_scope_reduced(
        self,
        task_db: Session,
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
        payload = {
            "userPermissionsChange": [
                {
                    "userId": "garmin_user_123",
                    "permissions": ["ACTIVITY_EXPORT"],
                },
            ],
        }

        # Act
        result = process_push.run(payload, "trace-021")

        # Assert
        assert "userPermissionsChange" in result
        assert result["userPermissionsChange"]["updated"] == 1
        assert len(result["userPermissionsChange"]["errors"]) == 0

        # Verify DB was updated - scope reduced
        task_db.refresh(connection)
        assert connection.scope == "ACTIVITY_EXPORT"

    def test_push_webhook_permissions_scope_unchanged(
        self,
        task_db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Test that scope remains functionally the same when permissions haven't changed."""
        # Arrange
        user = UserFactory()
        connection = UserConnectionFactory(
            user=user,
            provider="garmin",
            provider_user_id="garmin_user_123",
            scope="ACTIVITY_EXPORT HEALTH_EXPORT",
        )
        payload = {
            "userPermissionsChange": [
                {
                    "userId": "garmin_user_123",
                    "permissions": ["HEALTH_EXPORT", "ACTIVITY_EXPORT"],
                },
            ],
        }

        # Act
        result = process_push.run(payload, "trace-022")

        # Assert
        assert "userPermissionsChange" in result
        assert result["userPermissionsChange"]["updated"] == 1

        # Verify DB scope is set to sorted permissions
        task_db.refresh(connection)
        assert connection.scope == "ACTIVITY_EXPORT HEALTH_EXPORT"

    def test_push_webhook_user_permissions_unknown_user(
        self,
        task_db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Test userPermissionsChange with unknown user returns 200 with error info."""
        # Arrange - no user connection created
        payload = {
            "userPermissionsChange": [
                {
                    "userId": "unknown_garmin_user",
                    "permissions": ["ACTIVITY_EXPORT"],
                },
            ],
        }

        # Act
        result = process_push.run(payload, "trace-023")

        # Assert
        assert "userPermissionsChange" in result
        assert result["userPermissionsChange"]["updated"] == 0
        assert len(result["userPermissionsChange"]["errors"]) == 1

    def test_ping_webhook_user_permissions_updates_scope(
        self,
        task_db: Session,
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
        payload = {
            "userPermissionsChange": [
                {
                    "userId": "garmin_user_123",
                    "permissions": ["ACTIVITY_EXPORT", "WELLNESS_EXPORT"],
                },
            ],
        }

        # Act
        result = process_ping.run(payload, "trace-024")

        # Assert
        assert "userPermissionsChange" in result
        assert result["userPermissionsChange"]["updated"] == 1

        # Verify DB was updated
        task_db.refresh(connection)
        assert connection.scope == "ACTIVITY_EXPORT WELLNESS_EXPORT"

    def test_push_webhook_permissions_invalid_entries(
        self,
        task_db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Malformed permission entries (non-dict, missing userId) are skipped with errors."""
        payload = {
            "userPermissionsChange": [
                "not_a_dict",  # Invalid — not a dict
                {"permissions": ["ACTIVITY_EXPORT"]},  # Missing userId
            ],
        }

        # Act
        result = process_push.run(payload, "trace-025")

        # Assert — invalid entries produce errors, no update
        assert "userPermissionsChange" in result
        assert result["userPermissionsChange"]["updated"] == 0
        assert len(result["userPermissionsChange"]["errors"]) == 2

    def test_push_webhook_permissions_not_a_list(
        self,
        task_db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Non-list userPermissionsChange payload is rejected with a format error."""
        result = process_push.run({"userPermissionsChange": "not_a_list"}, "trace-026b")

        assert result["userPermissionsChange"]["updated"] == 0
        assert result["userPermissionsChange"]["errors"] == ["Invalid userPermissions payload format"]

    def test_ping_webhook_permissions_not_a_list(
        self,
        task_db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Ping: non-list userPermissionsChange payload is rejected with a format error."""
        result = process_ping.run({"userPermissionsChange": "not_a_list"}, "trace-027b")

        assert result["userPermissionsChange"]["updated"] == 0
        assert result["userPermissionsChange"]["errors"] == ["Invalid userPermissions payload format"]

    def test_ping_webhook_permissions_unknown_user(
        self,
        task_db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Ping webhook returns error info for unknown user in userPermissionsChange."""
        payload = {
            "userPermissionsChange": [
                {
                    "userId": "unknown_garmin_user",
                    "permissions": ["ACTIVITY_EXPORT"],
                },
            ],
        }

        result = process_ping.run(payload, "trace-026")

        assert "userPermissionsChange" in result
        assert result["userPermissionsChange"]["updated"] == 0
        assert len(result["userPermissionsChange"]["errors"]) == 1


class TestGarminDeregistrationWebhook:
    """Tests for deregistration handling — both process_push and process_ping."""

    def test_push_webhook_deregistration_revokes_connection(
        self,
        task_db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Test that deregistration revokes the connection."""
        # Arrange
        user = UserFactory()
        connection = UserConnectionFactory(
            user=user,
            provider="garmin",
            provider_user_id="garmin_user_123",
        )
        assert connection.status == ConnectionStatus.ACTIVE

        payload = {
            "deregistrations": [
                {"userId": "garmin_user_123"},
            ],
        }

        # Act
        result = process_push.run(payload, "trace-030")

        # Assert
        assert "deregistrations" in result
        assert result["deregistrations"]["revoked"] == 1
        assert len(result["deregistrations"]["errors"]) == 0

        # Verify DB was updated
        task_db.refresh(connection)
        assert connection.status == ConnectionStatus.REVOKED

    def test_push_webhook_deregistration_unknown_user(
        self,
        task_db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Test deregistration with unknown user returns 200 with error info."""
        # Arrange - no user connection created
        payload = {
            "deregistrations": [
                {"userId": "unknown_garmin_user"},
            ],
        }

        # Act
        result = process_push.run(payload, "trace-031")

        # Assert
        assert "deregistrations" in result
        assert result["deregistrations"]["revoked"] == 0
        assert len(result["deregistrations"]["errors"]) == 1

    def test_push_webhook_deregistration_invalid_entries(
        self,
        task_db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Malformed deregistration entries (non-dict, missing userId) are skipped with errors."""
        payload = {
            "deregistrations": [
                "not_a_dict",  # Invalid — not a dict
                {"otherField": "x"},  # Missing userId
            ],
        }

        # Act
        result = process_push.run(payload, "trace-032")

        # Assert
        assert "deregistrations" in result
        assert result["deregistrations"]["revoked"] == 0
        assert len(result["deregistrations"]["errors"]) == 2

    def test_push_webhook_deregistration_not_a_list(
        self,
        task_db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Non-list deregistrations payload is rejected with a format error."""
        result = process_push.run({"deregistrations": "not_a_list"}, "trace-035b")

        assert result["deregistrations"]["revoked"] == 0
        assert result["deregistrations"]["errors"] == ["Invalid deregistrations payload format"]

    def test_ping_webhook_deregistration_not_a_list(
        self,
        task_db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Ping: non-list deregistrations payload is rejected with a format error."""
        result = process_ping.run({"deregistrations": "not_a_list"}, "trace-036b")

        assert result["deregistrations"]["revoked"] == 0
        assert result["deregistrations"]["errors"] == ["Invalid deregistrations payload format"]

    def test_ping_webhook_deregistration_revokes_connection(
        self,
        task_db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Ping webhook revokes a known user's connection on deregistration."""
        user = UserFactory()
        connection = UserConnectionFactory(
            user=user,
            provider="garmin",
            provider_user_id="garmin_user_123",
        )
        assert connection.status == ConnectionStatus.ACTIVE

        payload = {
            "deregistrations": [
                {"userId": "garmin_user_123"},
            ],
        }

        result = process_ping.run(payload, "trace-033")

        assert "deregistrations" in result
        assert result["deregistrations"]["revoked"] == 1
        assert len(result["deregistrations"]["errors"]) == 0

        task_db.refresh(connection)
        assert connection.status == ConnectionStatus.REVOKED

    def test_ping_webhook_deregistration_unknown_user(
        self,
        task_db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Ping webhook returns error info when deregistering an unknown user."""
        payload = {
            "deregistrations": [
                {"userId": "unknown_garmin_user"},
            ],
        }

        result = process_ping.run(payload, "trace-034")

        assert "deregistrations" in result
        assert result["deregistrations"]["revoked"] == 0
        assert len(result["deregistrations"]["errors"]) == 1


class TestGarminPingWebhookTask:
    """Tests for process_ping Celery task."""

    def test_ping_webhook_success(
        self,
        task_db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Test successfully fetching callback URL for a known user."""
        # Arrange
        user = UserFactory()
        UserConnectionFactory(
            user=user,
            provider="garmin",
            provider_user_id="garmin_user_123",
        )
        payload = {
            "activities": [
                {
                    "userId": "garmin_user_123",
                    "callbackURL": "https://apis.garmin.com/wellness-api/rest/activities?uploadStartTimeInSeconds=1234567890&uploadEndTimeInSeconds=1234567900&token=abc123",
                },
            ],
        }

        # Mock sync httpx.get used by the task
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "activityId": 12345,
                "activityName": "Morning Run",
                "startTimeInSeconds": 1234567890,
            },
        ]

        # Act
        with patch(f"{MODULE}.httpx") as mock_httpx:
            mock_httpx.get.return_value = mock_response
            mock_httpx.HTTPError = Exception

            result = process_ping.run(payload, "trace-040")

        # Assert
        assert result["processed"] == 1
        assert len(result["errors"]) == 0
        assert result["activities"][0]["status"] == "fetched"

    def test_ping_webhook_unknown_user(
        self,
        task_db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Test ping webhook with unknown Garmin user."""
        # Arrange - no user connection created
        payload = {
            "activities": [
                {
                    "userId": "unknown_garmin_user",
                    "callbackURL": "https://apis.garmin.com/wellness-api/rest/activities?token=abc",
                },
            ],
        }

        # Act
        with patch(f"{MODULE}.httpx") as mock_httpx:
            mock_httpx.HTTPError = Exception

            result = process_ping.run(payload, "trace-041")

        # Assert
        assert result["processed"] == 0
        assert len(result["errors"]) == 1

    def test_ping_webhook_no_callback_url(
        self,
        task_db: Session,
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
        payload = {
            "activities": [
                {
                    "userId": "garmin_user_123",
                    # Missing callbackURL
                },
            ],
        }

        # Act
        with patch(f"{MODULE}.httpx") as mock_httpx:
            mock_httpx.HTTPError = Exception

            result = process_ping.run(payload, "trace-042")

        # Assert - no callback URL means the entry is skipped (no error, no processed)
        assert result["processed"] == 0
        assert len(result["errors"]) == 0

    def test_ping_webhook_multiple_activities(
        self,
        task_db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Test ping webhook with multiple activities from different users."""
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

        mock_response = MagicMock()
        mock_response.json.return_value = [{"activityId": 12345}]

        # Act
        with patch(f"{MODULE}.httpx") as mock_httpx:
            mock_httpx.get.return_value = mock_response
            mock_httpx.HTTPError = Exception

            result = process_ping.run(payload, "trace-043")

        # Assert
        assert result["processed"] == 2
        assert len(result["activities"]) == 2

    def test_ping_webhook_callback_fetch_error(
        self,
        task_db: Session,
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
        payload = {
            "activities": [
                {
                    "userId": "garmin_user_123",
                    "callbackURL": "https://apis.garmin.com/wellness-api/rest/activities?token=abc123",
                },
            ],
        }

        # Act
        with patch(f"{MODULE}.httpx") as mock_httpx:

            class _FakeHTTPError(Exception):
                pass

            mock_httpx.HTTPError = _FakeHTTPError
            mock_httpx.get.side_effect = _FakeHTTPError("Connection failed")

            result = process_ping.run(payload, "trace-044")

        # Assert
        assert result["processed"] == 0
        assert len(result["errors"]) == 1
        assert "HTTP error" in result["errors"][0]

    def test_ping_webhook_wellness_via_callback(
        self,
        task_db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Ping payload with wellness callbackURL fetches and saves data via _process_wellness_notification."""
        # Arrange
        user = UserFactory()
        UserConnectionFactory(
            user=user,
            provider="garmin",
            provider_user_id="garmin_user_123",
        )
        payload = {
            "dailies": [
                {
                    "userId": "garmin_user_123",
                    "callbackURL": "https://apis.garmin.com/wellness-api/rest/dailies?uploadStartTimeInSeconds=1768258800&token=abc",
                },
            ],
        }

        # Mock sync httpx.get used by _process_wellness_notification
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "userId": "garmin_user_123",
                "summaryId": "daily-cb-1",
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
            },
        ]

        # Act
        with patch(f"{MODULE}.httpx") as mock_httpx:
            mock_httpx.get.return_value = mock_response
            mock_httpx.HTTPError = Exception

            result = process_ping.run(payload, "trace-050")

        # Assert
        assert "wellness" in result
        assert "dailies" in result["wellness"]
        assert result["wellness"]["dailies"]["processed"] == 1
        assert result["wellness"]["dailies"]["saved"] > 0

    def test_ping_webhook_wellness_unknown_user(
        self,
        task_db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Ping wellness notification for unknown user is skipped with error."""
        # No connection created
        payload = {
            "dailies": [
                {
                    "userId": "unknown_garmin_user",
                    "callbackURL": "https://apis.garmin.com/wellness-api/rest/dailies?token=abc",
                },
            ],
        }

        # Act
        with patch(f"{MODULE}.httpx") as mock_httpx:
            mock_httpx.HTTPError = Exception

            result = process_ping.run(payload, "trace-051")

        # Assert
        assert "wellness" in result
        assert "dailies" in result["wellness"]
        assert result["wellness"]["dailies"]["errors"][0].startswith("User unknown_garmin_user")

    def test_ping_webhook_wellness_callback_http_error(
        self,
        task_db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """HTTPError fetching a wellness callback URL is recorded in errors."""
        user = UserFactory()
        UserConnectionFactory(
            user=user,
            provider="garmin",
            provider_user_id="garmin_user_123",
        )
        payload = {
            "dailies": [
                {
                    "userId": "garmin_user_123",
                    "callbackURL": "https://apis.garmin.com/wellness-api/rest/dailies?token=abc",
                },
            ],
        }

        with patch(f"{MODULE}.httpx") as mock_httpx:

            class _FakeHTTPError(Exception):
                pass

            mock_httpx.HTTPError = _FakeHTTPError
            mock_httpx.get.side_effect = _FakeHTTPError("Connection reset by peer")

            result = process_ping.run(payload, "trace-052")

        assert "dailies" in result["wellness"]
        assert len(result["wellness"]["dailies"]["errors"]) == 1
        assert "HTTP error" in result["wellness"]["dailies"]["errors"][0]

    def test_ping_webhook_wellness_callback_generic_error(
        self,
        task_db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Generic exception fetching a wellness callback is caught and recorded."""
        user = UserFactory()
        UserConnectionFactory(
            user=user,
            provider="garmin",
            provider_user_id="garmin_user_123",
        )
        payload = {
            "dailies": [
                {
                    "userId": "garmin_user_123",
                    "callbackURL": "https://apis.garmin.com/wellness-api/rest/dailies?token=abc",
                },
            ],
        }

        with patch(f"{MODULE}.httpx") as mock_httpx:

            class _FakeHTTPError(Exception):
                pass

            mock_httpx.HTTPError = _FakeHTTPError
            # RuntimeError is not a _FakeHTTPError → falls through to generic except
            mock_httpx.get.side_effect = RuntimeError("unexpected data corruption")

            result = process_ping.run(payload, "trace-053")

        assert "dailies" in result["wellness"]
        assert len(result["wellness"]["dailies"]["errors"]) == 1
        assert "Error:" in result["wellness"]["dailies"]["errors"][0]

    def test_ping_webhook_activity_unexpected_exception(
        self,
        task_db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Non-HTTPError exception inside activity iteration is caught by outer except (line 421)."""
        user = UserFactory()
        UserConnectionFactory(
            user=user,
            provider="garmin",
            provider_user_id="garmin_user_123",
        )
        payload = {
            "activities": [
                {
                    "userId": "garmin_user_123",
                    "callbackURL": "https://apis.garmin.com/wellness-api/rest/activities?token=abc",
                },
            ],
        }

        with patch(f"{MODULE}.httpx") as mock_httpx:

            class _FakeHTTPError(Exception):
                pass

            mock_httpx.HTTPError = _FakeHTTPError
            # RuntimeError is not _FakeHTTPError → bypasses inner catch, hits outer except per line 421
            mock_httpx.get.side_effect = RuntimeError("unexpected crash in activity fetch")

            result = process_ping.run(payload, "trace-045b")

        assert result["processed"] == 0
        assert len(result["errors"]) == 1
        assert "unexpected crash" in result["errors"][0]


class TestGarminTaskRetry:
    """Tests that process_ping and process_push call self.retry on unhandled exceptions."""

    def test_ping_retries_on_unexpected_error(
        self,
        task_db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Unhandled exception in process_ping triggers self.retry, raising Retry."""
        retry_exc = Retry("will retry", RuntimeError("critical failure"))
        with (
            patch.object(process_ping, "retry", return_value=retry_exc) as mock_retry,
            patch(f"{MODULE}.ProviderFactory") as mock_factory,
        ):
            mock_factory.side_effect = RuntimeError("critical failure")
            with pytest.raises(Retry):
                process_ping.run({}, "trace-retry-ping")
        mock_retry.assert_called_once()

    def test_push_retries_on_unexpected_error(
        self,
        task_db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Unhandled exception in process_push triggers self.retry, raising Retry."""
        retry_exc = Retry("will retry", RuntimeError("critical failure"))
        with (
            patch.object(process_push, "retry", return_value=retry_exc) as mock_retry,
            patch(f"{MODULE}.ProviderFactory") as mock_factory,
        ):
            mock_factory.side_effect = RuntimeError("critical failure")
            with pytest.raises(Retry):
                process_push.run({}, "trace-retry-push")
        mock_retry.assert_called_once()
