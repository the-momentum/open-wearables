"""Strava webhooks are accepted only on the callback URL that carries the callback token."""

import json
import time
from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.config import settings
from app.constants.celery_tasks import CeleryTask
from app.utils.webhook_callback import callback_token

TOKEN = callback_token("strava").get_secret_value()
BASE = "/api/v1/providers/strava/webhooks"
HANDLER = "app.services.providers.strava.webhook_handler"

# Captured from Strava on 2026-11-04 (test app 293960); event_time is set per request.
CREATE_EVENT = {
    "aspect_type": "create",
    "object_id": 20853903452,
    "object_type": "activity",
    "owner_id": 315693644,
    "subscription_id": 382914,
    "updates": {},
}


@pytest.fixture
def celery() -> Generator[MagicMock, None, None]:
    with patch(f"{HANDLER}.celery_app") as mock, patch(f"{HANDLER}.store_raw_payload"):
        mock.send_task.return_value.id = "task-1"
        yield mock


def _post_event(client: TestClient, path: str) -> httpx.Response:
    now = int(time.time())
    return client.post(
        path,
        content=json.dumps({**CREATE_EVENT, "event_time": now}),
        headers={"Content-Type": "application/json", "X-Strava-Signature": f"t={now},v1={'0' * 64}"},
    )


def _handshake(client: TestClient, path: str) -> httpx.Response:
    params = {
        "hub.mode": "subscribe",
        "hub.challenge": "15f7d1a91c1f40f8a748fd134752feb3",
        "hub.verify_token": settings.strava_webhook_verify_token.get_secret_value(),  # ty:ignore[unresolved-attribute]
    }
    return client.get(path, params=params)


class TestEvents:
    def test_event_on_the_token_url_is_accepted(self, client: TestClient, celery: MagicMock) -> None:
        response = _post_event(client, f"{BASE}/{TOKEN}")

        assert response.status_code == 200
        assert response.json() == {"status": "accepted"}
        assert celery.send_task.call_args.args[0] == CeleryTask.PROCESS_WEBHOOK_PUSH

    @pytest.mark.parametrize(
        "path",
        [BASE, f"{BASE}/{TOKEN[:-1]}x", f"{BASE}/{TOKEN}x", f"{BASE}/żółw"],
        ids=["no-token", "wrong-token", "longer-token", "non-ascii-token"],
    )
    def test_event_without_the_right_token_is_rejected(self, client: TestClient, celery: MagicMock, path: str) -> None:
        response = _post_event(client, path)

        assert response.status_code == 401
        celery.send_task.assert_not_called()

    @pytest.mark.parametrize("path", ["/api/v1/strava/webhooks", "/api/v1/strava/webhook"])
    def test_legacy_routes_are_gone(self, client: TestClient, celery: MagicMock, path: str) -> None:
        assert _post_event(client, path).status_code == 404
        celery.send_task.assert_not_called()


class TestHandshake:
    def test_handshake_on_the_token_url_echoes_the_challenge(self, client: TestClient) -> None:
        response = _handshake(client, f"{BASE}/{TOKEN}")

        assert response.status_code == 200
        assert response.json() == {"hub.challenge": "15f7d1a91c1f40f8a748fd134752feb3"}

    @pytest.mark.parametrize("path", [BASE, f"{BASE}/wrong"], ids=["no-token", "wrong-token"])
    def test_handshake_without_the_right_token_is_rejected(self, client: TestClient, path: str) -> None:
        assert _handshake(client, path).status_code == 401


class TestProbe:
    def test_probe_is_authenticated_before_it_is_found_unsupported(self, client: TestClient) -> None:
        assert client.head(BASE).status_code == 401
        assert client.head(f"{BASE}/{TOKEN}").status_code == 501


class TestRouting:
    @pytest.mark.parametrize("method", ["post", "get", "head"])
    def test_providers_without_a_callback_token_do_not_serve_token_urls(self, client: TestClient, method: str) -> None:
        response = client.request(method.upper(), f"/api/v1/providers/oura/webhooks/{TOKEN}")

        assert response.status_code == 404

    def test_a_handle_override_cannot_skip_the_token_check(self, client: TestClient) -> None:
        """Polar answers a PING in its own handle() before the base pipeline runs."""
        assert client.post("/api/v1/providers/polar/webhooks", json={"event": "PING"}).status_code == 200
        assert client.post(f"/api/v1/providers/polar/webhooks/{TOKEN}", json={"event": "PING"}).status_code == 404

    def test_registration_defaults_to_this_deployments_callback_url(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        registered = AsyncMock(return_value=[{"status": "created"}])
        with (
            patch.object(settings, "api_base_url", "https://api.example.com"),
            patch("app.services.providers.oura.webhook_service.OuraWebhookService.register_subscriptions", registered),
        ):
            response = client.post("/api/v1/providers/oura/webhooks/subscriptions", headers=auth_headers)

        assert response.status_code == 200
        registered.assert_awaited_once_with("https://api.example.com/api/v1/providers/oura/webhooks")

    def test_subscriptions_path_still_reaches_the_management_api(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        listed = AsyncMock(return_value=[])
        with patch("app.services.providers.strava.webhook_service.StravaWebhookService.list_subscriptions", listed):
            response = client.get(f"{BASE}/subscriptions", headers=auth_headers)

        assert response.status_code == 200
        assert response.json() == {"subscriptions": []}
        listed.assert_awaited_once()

    def test_subscription_list_hides_the_token(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        strava_response = httpx.Response(
            200,
            request=httpx.Request("GET", "https://www.strava.com/api/v3/push_subscriptions"),
            json=[
                {
                    "id": 382914,
                    "application_id": 293960,
                    "callback_url": f"https://api.example.com{BASE}/{TOKEN}",
                    "created_at": "2026-11-04T10:00:00Z",
                    "updated_at": "2026-11-04T10:00:00Z",
                }
            ],
        )
        with (
            patch.object(settings, "strava_client_id", "293960"),
            patch.object(settings, "strava_client_secret", SecretStr("client-secret")),
            patch("httpx.AsyncClient") as client_class,
        ):
            client_class.return_value.__aenter__.return_value.get = AsyncMock(return_value=strava_response)
            response = client.get(f"{BASE}/subscriptions", headers=auth_headers)

        assert response.status_code == 200
        assert TOKEN not in response.text
        assert response.json()["subscriptions"][0]["callback_url"] == f"https://api.example.com{BASE}/redacted"
