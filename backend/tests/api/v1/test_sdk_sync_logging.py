"""Tests for the attribution fields on the SDK sync batch log line."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient

from app.config import settings
from tests.factories import ApiKeyFactory

_USER_ID = "123e4567-e89b-12d3-a456-426614174000"
_BODY = {
    "provider": "apple",
    "sdkVersion": "1.0.0",
    "syncTimestamp": "2021-01-01T00:00:00Z",
    "data": {"records": [], "workouts": [], "sleep": []},
}


@pytest.fixture
def mock_log() -> Generator[MagicMock, None, None]:
    with (
        patch("app.api.routes.v1.sdk_sync.process_sdk_upload"),
        patch("app.api.routes.v1.sdk_sync.store_raw_payload"),
        patch.object(settings, "sdk_payload_s3_offload", False),
        patch("app.api.routes.v1.sdk_sync.log_structured") as mock,
    ):
        yield mock


def _batch_received(mock_log: MagicMock) -> dict:
    return next(call.kwargs for call in mock_log.call_args_list if call.kwargs["action"] == "apple_sdk_batch_received")


class TestSDKSyncAttribution:
    def test_attribution_headers_are_logged(self, client: TestClient, api_v1_prefix: str, mock_log: MagicMock) -> None:
        response = client.post(
            f"{api_v1_prefix}/sdk/users/{_USER_ID}/sync/",
            headers={
                "X-Open-Wearables-API-Key": ApiKeyFactory().plain_key,
                "X-Open-Wearables-SDK-Version": "0.15.0",
                "X-Open-Wearables-SDK-Platform": "ios",
                "X-Request-Id": "req-1",
                "User-Agent": "OpenWearablesHealthSDK/0.15.0 (iOS 18.1.0; iPhone15,2)",
            },
            json=_BODY,
        )

        assert response.status_code == 202
        attributes = _batch_received(mock_log)
        assert attributes["sdk_version"] == "0.15.0"
        assert attributes["sdk_platform"] == "ios"
        assert attributes["request_id"] == "req-1"
        assert attributes["user_agent"] == "OpenWearablesHealthSDK/0.15.0 (iOS 18.1.0; iPhone15,2)"

    def test_body_version_is_the_fallback(self, client: TestClient, api_v1_prefix: str, mock_log: MagicMock) -> None:
        client.post(
            f"{api_v1_prefix}/sdk/users/{_USER_ID}/sync/",
            headers={"X-Open-Wearables-API-Key": ApiKeyFactory().plain_key},
            json=_BODY,
        )

        attributes = _batch_received(mock_log)
        assert attributes["sdk_version"] == "1.0.0"
        assert "sdk_platform" not in attributes
