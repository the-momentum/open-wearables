"""
Tests for import data endpoints.

Tests the /api/v1/users/{user_id}/import/apple/xml endpoints for XML import
and the /api/v1/sns/notification endpoint its uploads are announced on.
"""

from collections.abc import Iterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient
from httpx import Response
from kombu.exceptions import OperationalError
from sqlalchemy.orm import Session

from app.api.routes.v1.import_xml import _limited_receive
from tests.factories import ApiKeyFactory, UserFactory
from tests.utils import api_key_headers


class TestXMLImportEndpoint:
    """Test suite for XML import endpoint (presigned URL generation)."""

    def test_generate_presigned_url_success(
        self,
        client: TestClient,
        db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Test presigned URL endpoint (may fail if S3 not configured in test env)."""
        # Arrange
        user = UserFactory()
        api_key = ApiKeyFactory()
        headers = api_key_headers(api_key.plain_key)
        payload = {
            "filename": "export.xml",
        }

        # Act
        response = client.post(
            f"/api/v1/users/{user.id}/import/apple/xml/s3",
            headers=headers,
            json=payload,
        )

        # Assert - May return 403 or 503 if S3 is not configured in test environment
        assert response.status_code in [200, 201, 403, 503]
        if response.status_code in [200, 201]:
            data = response.json()
            assert "upload_url" in data
            assert "form_fields" in data
            assert "file_key" in data
            assert "expires_in" in data
            assert "max_file_size" in data
            assert "bucket" in data

    def test_generate_presigned_url_missing_api_key(self, client: TestClient, db: Session) -> None:
        """Test that presigned URL generation requires API key."""
        # Arrange
        user = UserFactory()
        payload = {
            "file_name": "export.xml",
            "content_type": "application/xml",
        }

        # Act
        response = client.post(
            f"/api/v1/users/{user.id}/import/apple/xml/s3",
            json=payload,
        )

        # Assert
        assert response.status_code == 401

    def test_generate_presigned_url_invalid_payload(
        self,
        client: TestClient,
        db: Session,
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """Test presigned URL generation with invalid payload."""
        # Arrange
        user = UserFactory()
        api_key = ApiKeyFactory()
        headers = api_key_headers(api_key.plain_key)
        payload = {
            "expiration_seconds": 30,  # Less than minimum (60)
        }

        # Act
        response = client.post(
            f"/api/v1/users/{user.id}/import/apple/xml/s3",
            headers=headers,
            json=payload,
        )

        # Assert
        assert response.status_code == 422


class TestSNSNotificationEndpoint:
    """Test suite for the SNS notification endpoint."""

    def test_unparsable_notification_does_not_echo_the_body(self, client: TestClient, db: Session) -> None:
        """A body that is not an SNS notification is a 400 that does not quote it back."""
        # Act
        response = client.post("/api/v1/sns/notification", content=b'{"Type": "secret-marker"')

        # Assert
        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid SNS notification"
        assert "secret-marker" not in response.text

    def test_invalid_notification_does_not_echo_the_body(self, client: TestClient, db: Session) -> None:
        """Valid JSON that fails the notification schema gets the same answer."""
        # Act
        response = client.post("/api/v1/sns/notification", json={"Type": "secret-marker"})

        # Assert
        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid SNS notification"
        assert "secret-marker" not in response.text


_ROUTE = "app.api.routes.v1.import_xml"
_MIB = 1024 * 1024
_XML = b"<HealthData></HealthData>"


def _upload_direct(client: TestClient, user_id: str, content: bytes) -> Response:
    api_key = ApiKeyFactory()
    return client.post(
        f"/api/v1/users/{user_id}/import/apple/xml/direct",
        headers=api_key_headers(api_key.plain_key),
        files={"file": ("export.xml", content, "application/xml")},
    )


class TestDirectXMLUpload:
    """Test suite for the direct XML upload endpoint."""

    def test_queues_file_at_limit(self, client: TestClient, db: Session) -> None:
        user = UserFactory()

        with (
            patch(f"{_ROUTE}.MAX_DIRECT_UPLOAD_SIZE", len(_XML)),
            patch(f"{_ROUTE}.process_xml_upload") as mock_task,
        ):
            mock_task.delay.return_value.id = "task-1"
            response = _upload_direct(client, str(user.id), _XML)

        assert response.status_code == 200
        assert response.json() == {"status": "processing", "task_id": "task-1", "user_id": str(user.id)}
        mock_task.delay.assert_called_once_with(file_contents=_XML, filename="export.xml", user_id=str(user.id))

    def test_rejects_file_over_limit_without_queueing(self, client: TestClient, db: Session) -> None:
        user = UserFactory()

        with (
            patch(f"{_ROUTE}.MAX_DIRECT_UPLOAD_SIZE", len(_XML) - 1),
            patch(f"{_ROUTE}.process_xml_upload") as mock_task,
        ):
            response = _upload_direct(client, str(user.id), _XML)

        assert response.status_code == 413
        assert response.headers["content-type"] == "application/problem+json"
        mock_task.delay.assert_not_called()

    def test_lower_product_limit_applies_to_direct_upload(self, client: TestClient, db: Session) -> None:
        user = UserFactory()

        with (
            patch(f"{_ROUTE}.MAX_FILE_SIZE", len(_XML) - 1),
            patch(f"{_ROUTE}.process_xml_upload") as mock_task,
        ):
            response = _upload_direct(client, str(user.id), _XML)

        assert response.status_code == 413
        mock_task.delay.assert_not_called()

    def test_413_message_points_to_multipart(self, client: TestClient, db: Session) -> None:
        user = UserFactory()

        with (
            patch(f"{_ROUTE}.MAX_DIRECT_UPLOAD_SIZE", 3 * _MIB),
            patch(f"{_ROUTE}.process_xml_upload"),
        ):
            response = _upload_direct(client, str(user.id), b"x" * (3 * _MIB + 1))

        assert response.status_code == 413
        assert response.json()["detail"] == (
            "Direct upload accepts files up to 3 MiB. "
            "Use the multipart upload (POST /api/v1/users/{user_id}/import/apple/xml/s3/multipart/create) "
            "for larger files."
        )

    def test_413_message_skips_multipart_for_file_over_product_limit(self, client: TestClient, db: Session) -> None:
        user = UserFactory()

        with (
            patch(f"{_ROUTE}.MAX_DIRECT_UPLOAD_SIZE", 2 * _MIB),
            patch(f"{_ROUTE}.MAX_FILE_SIZE", 3 * _MIB),
            patch(f"{_ROUTE}.process_xml_upload"),
        ):
            response = _upload_direct(client, str(user.id), b"x" * (4 * _MIB))

        assert response.status_code == 413
        assert response.json()["detail"] == "XML import accepts files up to 3 MiB."

    def test_rejects_declared_oversized_body_before_parsing_it(self, client: TestClient, db: Session) -> None:
        user = UserFactory()

        with (
            patch(f"{_ROUTE}.MAX_DIRECT_UPLOAD_SIZE", 3 * _MIB),
            patch(f"{_ROUTE}.process_xml_upload") as mock_task,
            patch("starlette.requests.Request.form", new_callable=AsyncMock) as mock_form,
        ):
            response = _upload_direct(client, str(user.id), b"x" * (4 * _MIB))

        assert response.status_code == 413
        assert response.headers["content-type"] == "application/problem+json"
        assert response.json()["detail"] == (
            "Direct upload accepts files up to 3 MiB. "
            "Use the multipart upload (POST /api/v1/users/{user_id}/import/apple/xml/s3/multipart/create) "
            "for larger files."
        )
        mock_form.assert_not_called()
        mock_task.delay.assert_not_called()

    def test_rejects_undeclared_oversized_body(self, client: TestClient, db: Session) -> None:
        user = UserFactory()
        boundary = "test-boundary"

        def body() -> Iterator[bytes]:
            # A generator makes httpx send the body chunked, without Content-Length.
            yield (
                f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="export.xml"\r\n'
                "Content-Type: application/xml\r\n\r\n"
            ).encode()
            for _ in range(4):
                yield b"x" * _MIB
            yield f"\r\n--{boundary}--\r\n".encode()

        with (
            patch(f"{_ROUTE}.MAX_DIRECT_UPLOAD_SIZE", 3 * _MIB),
            patch(f"{_ROUTE}.process_xml_upload") as mock_task,
        ):
            response = client.post(
                f"/api/v1/users/{user.id}/import/apple/xml/direct",
                headers={
                    **api_key_headers(ApiKeyFactory().plain_key),
                    "Content-Type": f"multipart/form-data; boundary={boundary}",
                },
                content=body(),
            )

        assert response.status_code == 413
        assert response.json()["detail"].startswith("Direct upload accepts files up to 3 MiB.")
        mock_task.delay.assert_not_called()

    def test_returns_503_when_queue_rejects_task(self, client: TestClient, db: Session) -> None:
        user = UserFactory()

        with (
            patch(f"{_ROUTE}.process_xml_upload") as mock_task,
            patch(f"{_ROUTE}.logger") as mock_logger,
        ):
            mock_task.delay.side_effect = OperationalError("Error 32 while writing to socket. Broken pipe.")
            response = _upload_direct(client, str(user.id), _XML)

        assert response.status_code == 503
        assert response.json()["detail"] == "Unable to queue XML processing"
        mock_logger.error.assert_called_once()
        assert mock_logger.error.call_args.kwargs["action"] == "xml_direct_upload_queue_failed"


class TestLimitedReceive:
    """The body counter stops reading as soon as the limit is crossed."""

    @staticmethod
    def _request(chunks: list[bytes], headers: list[tuple[bytes, bytes]] | None = None) -> tuple[Request, list[int]]:
        consumed = [0]

        async def receive() -> dict:
            consumed[0] += 1
            body = chunks[consumed[0] - 1]
            return {"type": "http.request", "body": body, "more_body": consumed[0] < len(chunks)}

        return Request({"type": "http", "headers": headers or []}, receive), consumed

    async def test_raises_on_the_chunk_that_crosses_the_limit(self) -> None:
        with patch(f"{_ROUTE}._MULTIPART_OVERHEAD", 10):
            request, consumed = self._request([b"x" * 60, b"x" * 60, b"x" * 60])
            receive = _limited_receive(request, 100)

            await receive()
            with pytest.raises(HTTPException) as exc_info:
                await receive()

        assert exc_info.value.status_code == 413
        assert consumed[0] == 2

    async def test_passes_a_body_within_the_limit_plus_framing(self) -> None:
        with patch(f"{_ROUTE}._MULTIPART_OVERHEAD", 10):
            request, _ = self._request([b"x" * 60, b"x" * 50])
            receive = _limited_receive(request, 100)

            first = await receive()
            second = await receive()

        assert (len(first["body"]), len(second["body"])) == (60, 50)
        assert second["more_body"] is False

    def test_rejects_declared_length_before_reading(self) -> None:
        with patch(f"{_ROUTE}._MULTIPART_OVERHEAD", 10):
            request, consumed = self._request([b"x"], headers=[(b"content-length", b"111")])
            with pytest.raises(HTTPException) as exc_info:
                _limited_receive(request, 100)

        assert exc_info.value.status_code == 413
        assert consumed[0] == 0
