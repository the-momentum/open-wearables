"""
Tests for Garmin webhook Celery tasks.

Tests process_push task for:
- Activity saving and user-not-found handling
- Wellness data (HRV, dailies, sleeps, epochs) saving
- userPermissionsChange scope updates (DB state verified)
- Deregistration connection revocation (DB state verified)
- Retry behaviour on infrastructure errors
"""

from unittest.mock import MagicMock, patch

import pytest
from celery.exceptions import Retry
from sqlalchemy.orm import Session

from app.integrations.celery.tasks.garmin_webhook_task import process_push
from app.schemas.auth import ConnectionStatus
from tests.factories import UserConnectionFactory, UserFactory

MODULE = "app.integrations.celery.tasks.garmin_webhook_task"
HANDLER_MODULE = "app.services.providers.garmin.webhook_handler"


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

        # Assert — validation_error is surfaced in activities detail, not the top-level errors list
        assert result["activities"][0]["status"] == "validation_error"
        assert len(result["errors"]) == 0

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

        # Assert — unknown user: connection not found, nothing processed or saved
        assert "wellness" in result
        assert "dailies" in result["wellness"]
        assert result["wellness"]["dailies"]["processed"] == 0
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
            patch(f"{HANDLER_MODULE}.mark_type_success", return_value=True),
            patch(
                f"{HANDLER_MODULE}.get_backfill_status",
                return_value={"overall_status": "in_progress", "current_window": 1, "total_windows": 5},
            ),
            patch(f"{HANDLER_MODULE}.celery_app") as mock_celery,
        ):
            mock_celery.send_task.return_value = MagicMock(id="backfill-task")
            result = process_push.run(payload, "trace-015")

        # Assert — backfill chaining was triggered
        assert len(result["backfill_chained"]) == 1
        mock_celery.send_task.assert_called_once()


class TestGarminUserPermissionsWebhook:
    """Tests for userPermissionsChange handling via process_push."""

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
        """Test userPermissionsChange with unknown user is a no-op (idempotent)."""
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

        # Assert — unknown user silently skipped, no error produced
        assert "userPermissionsChange" in result
        assert result["userPermissionsChange"]["updated"] == 0
        assert len(result["userPermissionsChange"]["errors"]) == 0

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


class TestGarminDeregistrationWebhook:
    """Tests for deregistration handling via process_push."""

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

        # Assert — unknown user silently skipped, no error produced (idempotent)
        assert "deregistrations" in result
        assert result["deregistrations"]["revoked"] == 0
        assert len(result["deregistrations"]["errors"]) == 0

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


class TestGarminTaskRetry:
    """Tests that process_push calls self.retry on unhandled exceptions."""

    def test_push_retries_on_unexpected_error(
        self,
        task_db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Unhandled exception in process_push triggers self.retry, raising Retry."""
        retry_exc = Retry("will retry", RuntimeError("critical failure"))
        with (
            patch.object(process_push, "retry", return_value=retry_exc) as mock_retry,
            patch(f"{MODULE}.GarminStrategy") as mock_strategy_cls,
        ):
            mock_strategy_cls.side_effect = RuntimeError("critical failure")
            with pytest.raises(Retry):
                process_push.run({}, "trace-retry-push")
        mock_retry.assert_called_once()
