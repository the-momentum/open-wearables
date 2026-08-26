"""Tests for SDK sync payload offload - the queue carries a reference, not the body."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient

from app.config import settings
from tests.factories import ApiKeyFactory

_USER_ID = "123e4567-e89b-12d3-a456-426614174000"
_REF = "s3://bucket/raw-payloads/apple/sdk/2026-08-26/user/x.json"
_BODY = {
    "provider": "apple",
    "sdkVersion": "1.0.0",
    "syncTimestamp": "2021-01-01T00:00:00Z",
    "data": {"records": [], "workouts": [], "sleep": []},
}


@pytest.fixture
def mock_task() -> Generator[MagicMock, None, None]:
    with patch("app.api.routes.v1.sdk_sync.process_sdk_upload") as mock:
        mock.delay.return_value = None
        yield mock


def _sync(client: TestClient, api_v1_prefix: str) -> object:
    api_key = ApiKeyFactory()
    return client.post(
        f"{api_v1_prefix}/sdk/users/{_USER_ID}/sync/",
        headers={"X-Open-Wearables-API-Key": api_key.id},
        json=_BODY,
    )


class TestOffloadDisabled:
    def test_body_is_enqueued_inline(self, client: TestClient, api_v1_prefix: str, mock_task: MagicMock) -> None:
        with (
            patch.object(settings, "sdk_payload_s3_offload", False),
            patch("app.api.routes.v1.sdk_sync.store_raw_payload") as mock_archive,
            patch("app.api.routes.v1.sdk_sync.put_payload_to_s3") as mock_put,
        ):
            response = _sync(client, api_v1_prefix)

        assert response.status_code == 202
        mock_put.assert_not_called()
        mock_archive.assert_called_once()

        kwargs = mock_task.delay.call_args[1]
        assert kwargs["payload_ref"] is None
        assert '"provider": "apple"' in kwargs["content"]


class TestOffloadEnabled:
    def test_only_a_reference_is_enqueued(self, client: TestClient, api_v1_prefix: str, mock_task: MagicMock) -> None:
        with (
            patch.object(settings, "sdk_payload_s3_offload", True),
            patch("app.api.routes.v1.sdk_sync.store_raw_payload") as mock_archive,
            patch("app.api.routes.v1.sdk_sync.put_payload_to_s3", return_value=_REF),
        ):
            response = _sync(client, api_v1_prefix)

        assert response.status_code == 202
        # Transport owns the object, so the archival write is not called on top of it.
        mock_archive.assert_not_called()

        kwargs = mock_task.delay.call_args[1]
        assert kwargs["content"] is None
        assert kwargs["payload_ref"] == _REF

    def test_upload_failure_rejects_the_batch(
        self, client: TestClient, api_v1_prefix: str, mock_task: MagicMock
    ) -> None:
        """Falling back to an inline body is what fills the broker, so fail loudly instead."""
        with (
            patch.object(settings, "sdk_payload_s3_offload", True),
            patch("app.api.routes.v1.sdk_sync.put_payload_to_s3", return_value=None),
        ):
            response = _sync(client, api_v1_prefix)

        assert response.status_code == 503
        mock_task.delay.assert_not_called()
