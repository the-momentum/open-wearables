"""
Tests for process_apple_upload Celery task.

Tests Apple Health data import processing with user validation.
"""

from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.config import settings
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


_MODULE = "app.integrations.celery.tasks.process_sdk_upload_task"
_PAYLOAD_REF = "s3://bucket/raw/apple/sdk/2026-08-26/user/x.json"


class TestOffloadedPayload:
    """The body is fetched in the worker, so the broker only ever carries a reference."""

    @patch(f"{_MODULE}.get_payload_from_s3")
    @patch(f"{_MODULE}.SessionLocal")
    @patch(f"{_MODULE}.UserRepository")
    def test_content_is_loaded_from_the_reference(
        self,
        mock_user_repo_class: MagicMock,
        mock_session_local: MagicMock,
        mock_get_payload: MagicMock,
    ) -> None:
        mock_get_payload.return_value = '{"data":{"records":[]}}'
        mock_session_local.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_session_local.return_value.__exit__ = MagicMock(return_value=None)
        mock_user_repo = MagicMock()
        mock_user_repo.get.return_value = None
        mock_user_repo_class.return_value = mock_user_repo

        result = process_sdk_upload(
            content=None,
            content_type="application/json",
            user_id=str(uuid4()),
            provider="apple",
            payload_ref=_PAYLOAD_REF,
        )

        mock_get_payload.assert_called_once_with(_PAYLOAD_REF)
        assert result["reason"] == "user_not_found"

    @patch(f"{_MODULE}.get_payload_from_s3")
    def test_read_failure_propagates(self, mock_get_payload: MagicMock) -> None:
        """Swallowing this would drop the batch silently; raising reports it to Sentry."""
        mock_get_payload.side_effect = RuntimeError("S3 unavailable")

        with pytest.raises(RuntimeError, match="S3 unavailable"):
            process_sdk_upload(
                content=None,
                content_type="application/json",
                user_id=str(uuid4()),
                provider="apple",
                payload_ref=_PAYLOAD_REF,
            )

    def test_neither_content_nor_reference_is_reported(self) -> None:
        result = process_sdk_upload(
            content=None,
            content_type="application/json",
            user_id=str(uuid4()),
            provider="apple",
        )

        assert result["reason"] == "missing_payload"


def _run_offloaded_batch(db: Session, user: Any, *, archival: str, status_code: int = 200) -> MagicMock:
    """Process an offloaded batch; returns the delete_payload_from_s3 mock."""
    response = MagicMock()
    response.model_dump.return_value = {"status_code": status_code, "message": "done"}

    with (
        patch(f"{_MODULE}.delete_payload_from_s3") as mock_delete,
        patch(f"{_MODULE}.get_payload_from_s3", return_value='{"data":{"records":[]}}'),
        patch(f"{_MODULE}.sdk_import_service") as mock_import,
        patch(f"{_MODULE}.SessionLocal") as mock_session_local,
        patch(f"{_MODULE}.UserRepository") as mock_user_repo_class,
        patch.object(settings, "raw_payload_storage", archival),
    ):
        mock_session_local.return_value.__enter__ = MagicMock(return_value=db)
        mock_session_local.return_value.__exit__ = MagicMock(return_value=None)
        mock_user_repo = MagicMock()
        mock_user_repo.get.return_value = user
        mock_user_repo_class.return_value = mock_user_repo
        mock_import.import_data_from_request.return_value = response

        process_sdk_upload(
            content=None,
            content_type="application/json",
            user_id=str(user.id),
            provider="apple",
            payload_ref=_PAYLOAD_REF,
        )

    return mock_delete


class TestTransportedPayloadCleanup:
    """With archival off the S3 object only carries the payload, so it is dropped once saved."""

    def test_deleted_when_archival_is_disabled(self, db: Session, mock_celery_app: MagicMock) -> None:
        mock_delete = _run_offloaded_batch(db, UserFactory(), archival="disabled")

        mock_delete.assert_called_once_with(_PAYLOAD_REF)

    def test_kept_when_archival_uses_s3(self, db: Session, mock_celery_app: MagicMock) -> None:
        """That same object is the archive, so deleting it would throw the archive away."""
        mock_delete = _run_offloaded_batch(db, UserFactory(), archival="s3")

        mock_delete.assert_not_called()

    def test_kept_when_archival_uses_log(self, db: Session, mock_celery_app: MagicMock) -> None:
        """The offload path skips the stdout write, so S3 holds the only copy."""
        mock_delete = _run_offloaded_batch(db, UserFactory(), archival="log")

        mock_delete.assert_not_called()

    def test_kept_when_the_import_fails(self, db: Session, mock_celery_app: MagicMock) -> None:
        """A failed batch keeps its payload so it can be diagnosed and replayed."""
        mock_delete = _run_offloaded_batch(db, UserFactory(), archival="disabled", status_code=500)

        mock_delete.assert_not_called()
