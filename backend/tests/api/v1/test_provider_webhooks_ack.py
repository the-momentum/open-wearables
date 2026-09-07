"""Acknowledgement status of the unified provider webhook endpoint.

Google's webhook service requires an empty ``204 No Content`` in response to every
notification batch and retries anything else (developers.google.com/health/webhooks). Other
providers keep the JSON body their handlers return, and the Google endpoint-verification
handshake keeps its 200 + JSON.
"""

from typing import Any
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.v1 import webhooks as webhooks_route
from app.database import _get_db_dependency
from app.services.providers.google.health_api.webhook_handler import GoogleWebhookHandler


class _StubHandler:
    def __init__(self, result: dict[str, Any], ack_no_content: bool) -> None:
        self.result = result
        self.ack_no_content = ack_no_content

    def handle(self, request: Any, body: bytes, db: Any) -> dict[str, Any]:
        return self.result


def _client(handler: _StubHandler) -> TestClient:
    app = FastAPI()
    app.include_router(webhooks_route.router, prefix="/providers/{provider}/webhooks")
    app.dependency_overrides[_get_db_dependency] = lambda: MagicMock()
    strategy = MagicMock()
    strategy.webhooks = handler
    patcher = patch.object(webhooks_route._factory, "get_provider", return_value=strategy)
    patcher.start()
    client = TestClient(app)
    client.__dict__["_patcher"] = patcher
    return client


def test_google_handler_requests_empty_204_acknowledgement() -> None:
    assert GoogleWebhookHandler.ack_no_content is True


def test_accepted_notification_is_acknowledged_with_204_when_handler_asks_for_it() -> None:
    client = _client(_StubHandler({"status": "accepted"}, ack_no_content=True))
    try:
        response = client.post("/providers/google/webhooks", json=[{"data": {}}])
    finally:
        client.__dict__["_patcher"].stop()
    assert response.status_code == 204
    assert response.content == b""


def test_verification_handshake_keeps_200_with_json_body() -> None:
    client = _client(_StubHandler({"status": "verified"}, ack_no_content=True))
    try:
        response = client.post("/providers/google/webhooks", json={"type": "verification"})
    finally:
        client.__dict__["_patcher"].stop()
    assert response.status_code == 200
    assert response.json() == {"status": "verified"}


def test_providers_without_the_flag_keep_their_json_body() -> None:
    client = _client(_StubHandler({"status": "accepted"}, ack_no_content=False))
    try:
        response = client.post("/providers/polar/webhooks", json={"event": "PING"})
    finally:
        client.__dict__["_patcher"].stop()
    assert response.status_code == 200
    assert response.json() == {"status": "accepted"}
