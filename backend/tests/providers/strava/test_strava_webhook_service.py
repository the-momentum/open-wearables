"""The Strava subscription always points at the callback URL that carries the callback token."""

from collections.abc import Generator
from typing import NamedTuple
from unittest.mock import patch

import httpx
import pytest
import respx
from pydantic import SecretStr

from app.config import settings
from app.services.providers.strava.webhook_service import StravaWebhookService
from app.utils.webhook_callback import callback_token

TOKEN = callback_token("strava").get_secret_value()
SUBSCRIPTIONS_URL = "https://www.strava.com/api/v3/push_subscriptions"


@pytest.fixture(autouse=True)
def _strava_settings() -> Generator[None, None, None]:
    with (
        patch.object(settings, "api_base_url", "https://api.example.com"),
        patch.object(settings, "strava_client_id", "293960"),
        patch.object(settings, "strava_client_secret", SecretStr("client-secret")),
    ):
        yield


class StravaRoutes(NamedTuple):
    list: respx.Route
    create: respx.Route
    delete: respx.Route


@pytest.fixture
def strava(respx_mock: respx.MockRouter) -> StravaRoutes:
    """Strava's push subscription API: no subscription yet, creating one succeeds."""
    return StravaRoutes(
        list=respx_mock.get(SUBSCRIPTIONS_URL).respond(200, json=[]),
        create=respx_mock.post(SUBSCRIPTIONS_URL).respond(200, json={"id": 382915}),
        delete=respx_mock.delete(f"{SUBSCRIPTIONS_URL}/382914").respond(200),
    )


def _sent_form(route: respx.Route) -> httpx.QueryParams:
    return httpx.QueryParams(route.calls.last.request.content.decode())


async def test_registers_the_token_url_whatever_the_caller_passes(strava: StravaRoutes) -> None:
    result = await StravaWebhookService().register_subscriptions("https://attacker.example.com/hook")

    assert result[0]["status"] == "created"
    assert (
        _sent_form(strava.create)["callback_url"] == f"https://api.example.com/api/v1/providers/strava/webhooks/{TOKEN}"
    )


async def test_the_create_response_does_not_return_the_token(strava: StravaRoutes) -> None:
    strava.create.respond(
        200, json={"id": 382915, "callback_url": f"https://api.example.com/api/v1/providers/strava/webhooks/{TOKEN}"}
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


async def test_a_rotated_token_replaces_the_subscription(strava: StravaRoutes) -> None:
    strava.list.respond(
        200, json=[{"id": 382914, "callback_url": "https://api.example.com/api/v1/providers/strava/webhooks/old-token"}]
    )

    result = await StravaWebhookService().register_subscriptions("")

    assert result[0]["status"] == "created"
    assert strava.delete.call_count == 1
    assert _sent_form(strava.create)["callback_url"].endswith(f"/webhooks/{TOKEN}")


async def test_the_current_url_is_left_alone(strava: StravaRoutes) -> None:
    strava.list.respond(
        200, json=[{"id": 382914, "callback_url": f"https://api.example.com/api/v1/providers/strava/webhooks/{TOKEN}"}]
    )

    result = await StravaWebhookService().register_subscriptions("")

    assert result == [{"subscription_id": 382914, "status": "skipped"}]
    assert not strava.delete.called
    assert not strava.create.called
