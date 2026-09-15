"""Deployed SDK builds still send "google" for Health Connect."""

import json
from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from httpx import Response
from starlette.testclient import TestClient

from tests.factories import ApiKeyFactory


@pytest.fixture(autouse=True)
def mock_celery_tasks() -> Generator[MagicMock, None, None]:
    with patch("app.api.routes.v1.sdk_sync.process_sdk_upload") as mock:
        mock.delay.return_value = None
        yield mock


def _post(client: TestClient, api_v1_prefix: str, provider: str) -> Response:
    api_key = ApiKeyFactory()
    user_id = "123e4567-e89b-12d3-a456-426614174000"
    return client.post(
        f"{api_v1_prefix}/sdk/users/{user_id}/sync/",
        headers={"X-Open-Wearables-API-Key": api_key.plain_key},
        json={
            "provider": provider,
            "sdkVersion": "1.0.0",
            "syncTimestamp": "2021-01-01T00:00:00Z",
            "data": {"records": [], "workouts": [], "sleep": []},
        },
    )


class TestSDKProviderAlias:
    def test_google_payload_is_queued_as_health_connect(
        self, client: TestClient, api_v1_prefix: str, mock_celery_tasks: MagicMock
    ) -> None:
        response = _post(client, api_v1_prefix, "google")

        assert response.status_code == 202
        assert mock_celery_tasks.delay.call_args.kwargs["provider"] == "health_connect"

    def test_alias_is_applied_to_the_stored_payload(
        self, client: TestClient, api_v1_prefix: str, mock_celery_tasks: MagicMock
    ) -> None:
        """The worker re-reads provider from the payload, so the body must carry the canonical slug."""
        _post(client, api_v1_prefix, "google")

        content = json.loads(mock_celery_tasks.delay.call_args.kwargs["content"])
        assert content["provider"] == "health_connect"

    def test_canonical_slug_is_accepted(
        self, client: TestClient, api_v1_prefix: str, mock_celery_tasks: MagicMock
    ) -> None:
        response = _post(client, api_v1_prefix, "health_connect")

        assert response.status_code == 202
        assert mock_celery_tasks.delay.call_args.kwargs["provider"] == "health_connect"

    def test_google_health_is_not_an_sdk_provider(self, client: TestClient, api_v1_prefix: str) -> None:
        """The cloud OAuth provider must not be reachable through the SDK upload endpoint."""
        response = _post(client, api_v1_prefix, "google_health")

        assert response.status_code == 400
