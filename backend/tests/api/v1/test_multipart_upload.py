"""Tests for the Apple XML S3/MinIO multipart upload endpoints."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from tests.factories import ApiKeyFactory, UserFactory
from tests.utils.auth import api_key_headers

BASE = "/api/v1/users/{user_id}/import/apple/xml/s3/multipart"


class TestCreateMultipart:
    def test_create_success(self, client: TestClient, db: Session, mock_external_apis: dict[str, MagicMock]) -> None:
        user = UserFactory()
        headers = api_key_headers(ApiKeyFactory().id)

        response = client.post(
            BASE.format(user_id=user.id) + "/create",
            headers=headers,
            json={"filename": "export.xml", "file_size": 200 * 1024 * 1024},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["upload_id"] == "test-upload-id"
        assert data["key"].startswith(f"{user.id}/raw/")
        assert data["bucket"] == "test-bucket"
        assert data["part_size"] > 0

    def test_create_requires_api_key(self, client: TestClient, db: Session) -> None:
        user = UserFactory()
        response = client.post(
            BASE.format(user_id=user.id) + "/create",
            json={"filename": "export.xml", "file_size": 200 * 1024 * 1024},
        )
        assert response.status_code == 401

    def test_create_rejects_file_below_min_part_size(
        self, client: TestClient, db: Session, mock_external_apis: dict[str, MagicMock]
    ) -> None:
        user = UserFactory()
        headers = api_key_headers(ApiKeyFactory().id)
        response = client.post(
            BASE.format(user_id=user.id) + "/create",
            headers=headers,
            json={"filename": "export.xml", "file_size": 1024},  # below 5 MiB minimum
        )
        assert response.status_code in (400, 422)


class TestSignMultipart:
    def test_sign_returns_urls(self, client: TestClient, db: Session, mock_external_apis: dict[str, MagicMock]) -> None:
        user = UserFactory()
        headers = api_key_headers(ApiKeyFactory().id)
        response = client.post(
            BASE.format(user_id=user.id) + "/sign",
            headers=headers,
            json={
                "key": f"{user.id}/raw/export.xml",
                "upload_id": "test-upload-id",
                "part_numbers": [1, 2],
            },
        )

        assert response.status_code == 200
        urls = response.json()["urls"]
        assert [u["part_number"] for u in urls] == [1, 2]
        assert all(u["url"] for u in urls)

    def test_sign_rejects_foreign_key(
        self, client: TestClient, db: Session, mock_external_apis: dict[str, MagicMock]
    ) -> None:
        user = UserFactory()
        headers = api_key_headers(ApiKeyFactory().id)
        response = client.post(
            BASE.format(user_id=user.id) + "/sign",
            headers=headers,
            json={
                "key": "someone-else/raw/export.xml",
                "upload_id": "test-upload-id",
                "part_numbers": [1],
            },
        )
        assert response.status_code == 403


class TestCompleteMultipart:
    def test_complete_client_mode_dispatches_processing(
        self,
        client: TestClient,
        db: Session,
        mock_external_apis: dict[str, MagicMock],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings, "apple_xml_upload_completion_mode", "client")
        user = UserFactory()
        headers = api_key_headers(ApiKeyFactory().id)
        key = f"{user.id}/raw/export.xml"

        with patch("app.api.routes.v1.import_xml.complete_and_process_aws_upload") as mock_task:
            mock_task.delay.return_value = MagicMock(id="task-123")
            response = client.post(
                BASE.format(user_id=user.id) + "/complete",
                headers=headers,
                json={"key": key, "upload_id": "test-upload-id", "parts": [{"part_number": 1, "etag": "e1"}]},
            )

        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "processing"
        assert data["task_id"] == "task-123"
        assert data["bucket"] == "test-bucket"
        mock_task.delay.assert_called_once_with(
            bucket_name="test-bucket",
            object_key=key,
            upload_id="test-upload-id",
            parts=[{"part_number": 1, "etag": "e1"}],
            user_id=str(user.id),
        )
        mock_external_apis["s3"].complete_multipart_upload.assert_not_called()

    def test_complete_client_mode_keeps_upload_incomplete_when_queueing_fails(
        self,
        client: TestClient,
        db: Session,
        mock_external_apis: dict[str, MagicMock],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings, "apple_xml_upload_completion_mode", "client")
        user = UserFactory()
        headers = api_key_headers(ApiKeyFactory().id)
        key = f"{user.id}/raw/export.xml"

        with patch("app.api.routes.v1.import_xml.complete_and_process_aws_upload") as mock_task:
            mock_task.delay.side_effect = RuntimeError("broker unavailable")
            response = client.post(
                BASE.format(user_id=user.id) + "/complete",
                headers=headers,
                json={"key": key, "upload_id": "test-upload-id", "parts": [{"part_number": 1, "etag": "e1"}]},
            )

        assert response.status_code == 503
        assert "remains incomplete" in response.json()["detail"]
        mock_external_apis["s3"].complete_multipart_upload.assert_not_called()

    def test_complete_sns_mode_does_not_dispatch(
        self,
        client: TestClient,
        db: Session,
        mock_external_apis: dict[str, MagicMock],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings, "apple_xml_upload_completion_mode", "sns")
        user = UserFactory()
        headers = api_key_headers(ApiKeyFactory().id)
        key = f"{user.id}/raw/export.xml"

        with patch("app.api.routes.v1.import_xml.complete_and_process_aws_upload") as mock_task:
            response = client.post(
                BASE.format(user_id=user.id) + "/complete",
                headers=headers,
                json={"key": key, "upload_id": "test-upload-id", "parts": [{"part_number": 1, "etag": "e1"}]},
            )

        assert response.status_code == 200
        assert response.json()["status"] == "uploaded"
        mock_task.delay.assert_not_called()

    def test_complete_rejects_foreign_key(
        self, client: TestClient, db: Session, mock_external_apis: dict[str, MagicMock]
    ) -> None:
        user = UserFactory()
        headers = api_key_headers(ApiKeyFactory().id)
        response = client.post(
            BASE.format(user_id=user.id) + "/complete",
            headers=headers,
            json={"key": "other/raw/x.xml", "upload_id": "u", "parts": [{"part_number": 1, "etag": "e1"}]},
        )
        assert response.status_code == 403


class TestAbortMultipart:
    def test_abort_success(self, client: TestClient, db: Session, mock_external_apis: dict[str, MagicMock]) -> None:
        user = UserFactory()
        headers = api_key_headers(ApiKeyFactory().id)
        key = f"{user.id}/raw/export.xml"
        response = client.post(
            BASE.format(user_id=user.id) + "/abort",
            headers=headers,
            json={"key": key, "upload_id": "test-upload-id"},
        )
        assert response.status_code == 200
        assert response.json() == {"status": "aborted", "key": key}
        mock_external_apis["s3"].abort_multipart_upload.assert_called_once()
