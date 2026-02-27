"""
Tests for process_apple_upload Celery task.

Tests Apple Health data import processing with user validation.
"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

from sqlalchemy.orm import Session

from app.integrations.celery.tasks.process_sdk_upload_task import process_sdk_upload
from tests.factories import UserFactory


class TestProcessSDKUploadTask:
    """Test suite for process_sdk_upload task."""

    @patch("app.integrations.celery.tasks.process_sdk_upload_task.SessionLocal")
    @patch("app.integrations.celery.tasks.process_sdk_upload_task.UserRepository")
    def test_process_sdk_upload_with_nonexistent_user(
        self,
        mock_user_repo_class: MagicMock,
        mock_session_local: MagicMock,
    ) -> None:
        """Verify task gracefully handles non-existent user_id."""
        # Arrange
        non_existent_user_id = str(uuid4())
        mock_db = MagicMock()
        mock_session_local.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_local.return_value.__exit__ = MagicMock(return_value=None)

        mock_user_repo = MagicMock()
        mock_user_repo.get.return_value = None  # User not found
        mock_user_repo_class.return_value = mock_user_repo

        # Act
        result = process_sdk_upload(
            content='{"data":{"workouts":[],"records":[]}}',
            content_type="application/json",
            user_id=non_existent_user_id,
            provider="apple",
        )

        # Assert
        assert result["status"] == "skipped"
        assert result["reason"] == "user_not_found"

    def test_process_sdk_upload_with_invalid_uuid(self) -> None:
        """Verify task handles invalid UUID format gracefully."""
        result = process_sdk_upload(
            content='{"data":{"workouts":[],"records":[]}}',
            content_type="application/json",
            user_id="not-a-valid-uuid",
            provider="apple",
        )

        assert result["status"] == "error"
        assert result["reason"] == "invalid_user_id"

    @patch("app.integrations.celery.tasks.process_sdk_upload_task.sdk_import_service")
    @patch("app.integrations.celery.tasks.process_sdk_upload_task.SessionLocal")
    @patch("app.integrations.celery.tasks.process_sdk_upload_task.UserRepository")
    def test_process_sdk_upload_success_apple(
        self,
        mock_user_repo_class: MagicMock,
        mock_session_local: MagicMock,
        mock_hk_import_service: MagicMock,
        db: Session,
        mock_celery_app: MagicMock,
    ) -> None:
        """Test successful processing with apple provider."""
        # Arrange
        user = UserFactory()
        mock_session_local.return_value.__enter__ = MagicMock(return_value=db)
        mock_session_local.return_value.__exit__ = MagicMock(return_value=None)

        mock_user_repo = MagicMock()
        mock_user_repo.get.return_value = user
        mock_user_repo_class.return_value = mock_user_repo

        mock_response = MagicMock()
        mock_response.model_dump.return_value = {"status_code": 200, "message": "Import successful"}
        mock_hk_import_service.import_data_from_request.return_value = mock_response

        content = '{"data":{"workouts":[],"records":[]}}'
        content_type = "application/json"

        # Act
        result = process_sdk_upload(
            content=content,
            content_type=content_type,
            user_id=str(user.id),
            provider="apple",
        )

        # Assert
        assert result["status_code"] == 200
        mock_hk_import_service.import_data_from_request.assert_called_once()

    @patch("app.integrations.celery.tasks.process_sdk_upload_task.ae_import_service")
    @patch("app.integrations.celery.tasks.process_sdk_upload_task.SessionLocal")
    @patch("app.integrations.celery.tasks.process_sdk_upload_task.UserRepository")
    def test_process_sdk_upload_success_auto_health_export(
        self,
        mock_user_repo_class: MagicMock,
        mock_session_local: MagicMock,
        mock_ae_import_service: MagicMock,
        db: Session,
        mock_celery_app: MagicMock,
    ) -> None:
        """Test successful processing with auto-health-export provider."""
        # Arrange
        user = UserFactory()
        mock_session_local.return_value.__enter__ = MagicMock(return_value=db)
        mock_session_local.return_value.__exit__ = MagicMock(return_value=None)

        mock_user_repo = MagicMock()
        mock_user_repo.get.return_value = user
        mock_user_repo_class.return_value = mock_user_repo

        mock_response = MagicMock()
        mock_response.model_dump.return_value = {"status_code": 200, "message": "Import successful"}
        mock_ae_import_service.import_data_from_request.return_value = mock_response

        content = '{"data":{"workouts":[],"metrics":[]}}'
        content_type = "application/json"

        # Act
        result = process_sdk_upload(
            content=content,
            content_type=content_type,
            user_id=str(user.id),
            provider="auto-health-export",
        )

        # Assert
        assert result["status_code"] == 200
        mock_ae_import_service.import_data_from_request.assert_called_once()

    @patch("app.integrations.celery.tasks.process_sdk_upload_task.SessionLocal")
    @patch("app.integrations.celery.tasks.process_sdk_upload_task.UserRepository")
    def test_process_sdk_upload_user_check_uses_correct_uuid(
        self,
        mock_user_repo_class: MagicMock,
        mock_session_local: MagicMock,
    ) -> None:
        """Verify the user repository is called with the correct UUID."""
        # Arrange
        user_id = str(uuid4())
        mock_db = MagicMock()
        mock_session_local.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_local.return_value.__exit__ = MagicMock(return_value=None)

        mock_user_repo = MagicMock()
        mock_user_repo.get.return_value = None
        mock_user_repo_class.return_value = mock_user_repo

        # Act
        process_sdk_upload(
            content='{"data":{}}',
            content_type="application/json",
            user_id=user_id,
            provider="apple",
        )

        # Assert
        from uuid import UUID

        mock_user_repo.get.assert_called_once()
        call_args = mock_user_repo.get.call_args
        assert call_args[0][0] == mock_db
        assert call_args[0][1] == UUID(user_id)
