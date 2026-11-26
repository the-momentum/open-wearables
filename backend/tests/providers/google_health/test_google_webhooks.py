"""Registering the project's Health API subscriber."""

import json

import pytest
import respx
from pydantic import SecretStr

from app.config import settings
from app.services.providers.google_health import webhook_service
from app.services.providers.google_health.webhook_service import GOOGLE_WEBHOOK_DATA_TYPES, GoogleWebhookService

CALLBACK = "https://ow.example.com/api/v1/providers/google_health/webhooks"
SUBSCRIBERS_URL = "https://health.googleapis.com/v4/projects/ow-project/subscribers"


@pytest.fixture
def google_api(monkeypatch: pytest.MonkeyPatch, respx_mock: respx.MockRouter) -> respx.MockRouter:
    """Answer the subscriber API like a project whose subscriber already exists."""
    monkeypatch.setattr(settings, "google_project_id", "ow-project")
    monkeypatch.setattr(settings, "google_webhook_secret", SecretStr("secret"))
    monkeypatch.setattr(GoogleWebhookService, "_project_token", lambda self: "token")
    respx_mock.post(SUBSCRIBERS_URL).respond(409, json={})
    respx_mock.patch(f"{SUBSCRIBERS_URL}/{webhook_service.SUBSCRIBER_ID}").respond(200, json={})
    return respx_mock


async def test_an_existing_subscriber_gets_the_current_data_types(google_api: respx.MockRouter) -> None:
    result = await GoogleWebhookService().register_subscriptions(CALLBACK)

    post, patch_request = (call.request for call in google_api.calls)
    assert (post.method, patch_request.method) == ("POST", "PATCH")
    assert post.url.params["subscriberId"] == webhook_service.SUBSCRIBER_ID
    assert patch_request.url.params["updateMask"] == "subscriberConfigs"
    assert patch_request.headers["Authorization"] == "Bearer token"
    sent = json.loads(patch_request.content)
    assert sent["subscriberConfigs"][0]["dataTypes"] == GOOGLE_WEBHOOK_DATA_TYPES
    assert "daily-sleep-temperature-derivations" in GOOGLE_WEBHOOK_DATA_TYPES
    assert result == [{"status": "updated", "subscriber_id": webhook_service.SUBSCRIBER_ID}]
