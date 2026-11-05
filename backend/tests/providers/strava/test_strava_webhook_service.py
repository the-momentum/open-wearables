"""The Strava subscription always points at the callback URL that carries the callback token."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from pydantic import SecretStr

from app.config import settings
from app.services.providers.strava.webhook_service import StravaWebhookService
from app.utils.webhook_callback import callback_token

TOKEN = callback_token("strava").get_secret_value()


@pytest.fixture(autouse=True)
def _strava_settings() -> Generator[None, None, None]:
    with (
        patch.object(settings, "api_base_url", "https://api.example.com"),
        patch.object(settings, "strava_client_id", "293960"),
        patch.object(settings, "strava_client_secret", SecretStr("client-secret")),
    ):
        yield


def _response(payload: Any) -> httpx.Response:
    return httpx.Response(200, json=payload, request=httpx.Request("GET", "https://www.strava.com/api/v3"))


@pytest.fixture
def strava() -> Generator[MagicMock, None, None]:
    """The AsyncClient the service opens; its get/post/delete answer like Strava."""
    client = MagicMock()
    client.get = AsyncMock(return_value=_response([]))
    client.post = AsyncMock(return_value=_response({"id": 382915}))
    client.delete = AsyncMock(return_value=_response(None))
    with patch("httpx.AsyncClient") as client_class:
        client_class.return_value.__aenter__.return_value = client
        yield client


async def test_registers_the_token_url_whatever_the_caller_passes(strava: MagicMock) -> None:
    result = await StravaWebhookService().register_subscriptions("https://attacker.example.com/hook")

    assert result[0]["status"] == "created"
    sent = strava.post.await_args.kwargs["data"]
    assert sent["callback_url"] == f"https://api.example.com/api/v1/providers/strava/webhooks/{TOKEN}"


async def test_the_create_response_does_not_return_the_token(strava: MagicMock) -> None:
    strava.post.return_value = _response(
        {"id": 382915, "callback_url": f"https://api.example.com/api/v1/providers/strava/webhooks/{TOKEN}"}
    )

    result = await StravaWebhookService().register_subscriptions("")

    assert result == [
        {
            "status": "created",
            "response": {
                "id": 382915,
                "callback_url": "https://api.example.com/api/v1/providers/strava/webhooks/redacted",
            },
        }
    ]


async def test_a_rotated_token_replaces_the_subscription(strava: MagicMock) -> None:
    strava.get.return_value = _response(
        [{"id": 382914, "callback_url": "https://api.example.com/api/v1/providers/strava/webhooks/old-token"}]
    )

    result = await StravaWebhookService().register_subscriptions("")

    assert result[0]["status"] == "created"
    assert strava.delete.await_args.args[0].endswith("/push_subscriptions/382914")
    assert strava.post.await_args.kwargs["data"]["callback_url"].endswith(f"/webhooks/{TOKEN}")


async def test_the_current_url_is_left_alone(strava: MagicMock) -> None:
    strava.get.return_value = _response(
        [{"id": 382914, "callback_url": f"https://api.example.com/api/v1/providers/strava/webhooks/{TOKEN}"}]
    )

    result = await StravaWebhookService().register_subscriptions("")

    assert result == [{"subscription_id": 382914, "status": "skipped"}]
    strava.delete.assert_not_awaited()
    strava.post.assert_not_awaited()
