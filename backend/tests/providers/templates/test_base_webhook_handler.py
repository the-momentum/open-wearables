"""``handle()`` checks the callback token itself, not only the unified router.

Routes that call ``handle()`` directly (the deprecated per-provider ones) rely on
this: dropping the call from ``handle()`` would leave them unauthenticated.
"""

from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi import Request

from app.services.providers.templates.base_webhook_handler import BaseWebhookHandler
from app.utils.exceptions import WebhookVerificationError
from app.utils.webhook_callback import CALLBACK_TOKEN_PARAM, callback_token

TOKEN = callback_token("test").get_secret_value()


class _TokenHandler(BaseWebhookHandler):
    requires_callback_token = True

    def __init__(self) -> None:
        super().__init__("test")
        self.signature_checked = False

    def verify_signature(self, request: Request, body: bytes) -> bool:
        self.signature_checked = True
        return True

    def parse_payload(self, body: bytes) -> Any:
        return {}

    def dispatch(self, db: Any, payload: Any) -> dict[str, Any]:
        return {"status": "dispatched"}

    def supported_event_types(self) -> list[str]:
        return []


def _request(path_params: dict[str, str]) -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/test/webhook",
            "headers": [],
            "query_string": b"",
            "path_params": path_params,
        }
    )


@pytest.mark.parametrize("path_params", [{}, {CALLBACK_TOKEN_PARAM: "wrong"}])
def test_handle_rejects_a_request_without_the_token_before_anything_else(path_params: dict[str, str]) -> None:
    handler = _TokenHandler()

    with pytest.raises(WebhookVerificationError):
        handler.handle(_request(path_params), b"{}", MagicMock())

    assert not handler.signature_checked


def test_handle_accepts_a_request_with_the_token() -> None:
    handler = _TokenHandler()

    result = handler.handle(_request({CALLBACK_TOKEN_PARAM: TOKEN}), b"{}", MagicMock())

    assert result == {"status": "dispatched"}
    assert handler.signature_checked
