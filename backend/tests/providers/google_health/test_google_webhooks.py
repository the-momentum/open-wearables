"""Registering the project's Health API subscriber."""

import json

import httpx
import pytest
from pydantic import SecretStr

from app.config import settings
from app.services.providers.google_health import webhook_service
from app.services.providers.google_health.webhook_service import GOOGLE_WEBHOOK_DATA_TYPES, GoogleWebhookService

CALLBACK = "https://ow.example.com/api/v1/providers/google_health/webhooks"
# The suite patches httpx.AsyncClient globally; keep the real one to serve a mock transport.
_REAL_ASYNC_CLIENT = httpx.AsyncClient


@pytest.fixture
def google_api(monkeypatch: pytest.MonkeyPatch) -> list[httpx.Request]:
    """Answer the subscriber API like a project whose subscriber already exists."""
    monkeypatch.setattr(settings, "google_project_id", "ow-project")
    monkeypatch.setattr(settings, "google_webhook_secret", SecretStr("secret"))
    monkeypatch.setattr(GoogleWebhookService, "_project_token", lambda self: "token")
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(409 if request.method == "POST" else 200, json={})

    monkeypatch.setattr(
        webhook_service.httpx,
        "AsyncClient",
        lambda **kwargs: _REAL_ASYNC_CLIENT(transport=httpx.MockTransport(respond)),
    )
    return requests


async def test_an_existing_subscriber_gets_the_current_data_types(google_api: list) -> None:
    result = await GoogleWebhookService().register_subscriptions(CALLBACK)

    post, patch_request = google_api
    assert (post.method, patch_request.method) == ("POST", "PATCH")
    assert patch_request.url.params["updateMask"] == "subscriberConfigs"
    sent = json.loads(patch_request.content)
    assert sent["subscriberConfigs"][0]["dataTypes"] == GOOGLE_WEBHOOK_DATA_TYPES
    assert "daily-sleep-temperature-derivations" in GOOGLE_WEBHOOK_DATA_TYPES
    assert result == [{"status": "updated", "subscriber_id": webhook_service.SUBSCRIBER_ID}]
