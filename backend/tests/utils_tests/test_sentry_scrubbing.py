"""Sentry must never receive health data or PII.

Runs the real init_sentry() with a capturing transport and asserts on the events
the SDK would actually ship.
"""

import json
import logging
from collections.abc import Generator
from typing import Any
from unittest.mock import patch

import pytest
import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from pydantic import BaseModel, ValidationError
from sentry_sdk.envelope import Envelope
from sentry_sdk.transport import Transport

from app.config import settings
from app.integrations import sentry as sentry_integration
from app.utils.sentry_helpers import log_and_capture_error

logger = logging.getLogger("app.test_sentry_scrubbing")

FAKE_HEART_RATE = 187.349  # a dot keeps it from matching numeric ids in the event
FAKE_EMAIL = "jane.doe@example.com"
FAKE_USERNAME = "jane-strava-login"
FAKE_PAYLOAD = "resting_hr=48"


class _CapturingTransport(Transport):
    def __init__(self, options: dict[str, Any] | None = None) -> None:
        super().__init__(options)
        self.events: list[dict[str, Any]] = []

    def capture_envelope(self, envelope: Envelope) -> None:
        event = envelope.get_event()
        if event is not None:
            self.events.append(event)


class _Sample(BaseModel):
    heart_rate: int


@pytest.fixture
def captured() -> Generator[list[dict[str, Any]], None, None]:
    transport = _CapturingTransport()
    real_init = sentry_sdk.init

    def init_with_transport(*args: Any, **kwargs: Any) -> Any:
        return real_init(*args, transport=transport, **kwargs)

    with (
        patch.object(settings, "SENTRY_ENABLED", True),
        patch.object(settings, "SENTRY_DSN", "https://public@sentry.example.com/1"),
        patch.object(sentry_integration.sentry_sdk, "init", init_with_transport),
    ):
        sentry_integration.init_sentry()
    try:
        yield transport.events
    finally:
        sentry_sdk.flush()
        sentry_sdk.get_global_scope().set_client(None)


def _dump(event: dict[str, Any]) -> str:
    return json.dumps(event, default=str)


def test_unhandled_request_error_ships_no_body_or_locals(captured: list[dict[str, Any]]) -> None:
    app = FastAPI()

    @app.post("/webhook")
    async def webhook(request: Request) -> None:
        payload = await request.json()  # noqa: F841 - must not appear as a frame local
        raise RuntimeError("boom")

    client = TestClient(app, raise_server_exceptions=False)
    client.post("/webhook", json={"heart_rate": FAKE_HEART_RATE, "email": FAKE_EMAIL})
    sentry_sdk.flush()

    assert len(captured) == 1
    event = captured[0]
    # The SDK keeps an empty placeholder (annotated "removed" in _meta), never the body.
    assert not event["request"].get("data")
    frames = event["exception"]["values"][-1]["stacktrace"]["frames"]
    assert all("vars" not in frame for frame in frames)
    assert FAKE_EMAIL not in _dump(event)
    assert str(FAKE_HEART_RATE) not in _dump(event)


def test_pydantic_input_value_is_filtered(captured: list[dict[str, Any]]) -> None:
    try:
        _Sample.model_validate({"heart_rate": f"{FAKE_EMAIL} {FAKE_HEART_RATE}"})
    except ValidationError as exc:
        sentry_sdk.capture_exception(exc)
    sentry_sdk.flush()

    value = captured[0]["exception"]["values"][0]["value"]
    assert "input_value=[Filtered], input_type=str" in value
    assert "heart_rate" in value  # field location is kept for debugging
    assert FAKE_EMAIL not in _dump(captured[0])


def test_log_and_capture_error_context_is_scrubbed(captured: list[dict[str, Any]]) -> None:
    log_and_capture_error(
        RuntimeError("sync failed"),
        logger,
        "sync failed",
        extra={
            "user_id": "u-1",
            "email": FAKE_EMAIL,
            "nested": {"provider_username": FAKE_USERNAME},
            "error": f"[type=int_parsing, input_value='{FAKE_PAYLOAD}', input_type=str]",
        },
    )
    sentry_sdk.flush()

    # The ERROR log is its own event; the exception event carries the context.
    event = next(e for e in captured if "exception" in e)
    assert event["contexts"]["user_id"] == {"value": "u-1"}
    for e in captured:
        assert FAKE_EMAIL not in _dump(e)
        assert FAKE_USERNAME not in _dump(e)
        assert FAKE_PAYLOAD not in _dump(e)


def test_info_logs_do_not_become_breadcrumbs(captured: list[dict[str, Any]]) -> None:
    logger.info("Invitation sent to %s", FAKE_EMAIL)
    logger.warning("Skipping user %s", FAKE_EMAIL)
    sentry_sdk.capture_message("something happened")
    sentry_sdk.flush()

    assert FAKE_EMAIL not in _dump(captured[0])


def test_query_string_values_are_filtered(captured: list[dict[str, Any]]) -> None:
    app = FastAPI()

    @app.get("/users")
    async def users() -> None:
        raise RuntimeError("boom")

    client = TestClient(app, raise_server_exceptions=False)
    client.get("/users", params={"email": FAKE_EMAIL, "search": FAKE_USERNAME})
    sentry_sdk.flush()

    event = captured[0]
    assert event["request"]["query_string"] == "email=[Filtered]&search=[Filtered]"
    assert FAKE_USERNAME not in _dump(event)
    assert "example.com" not in _dump(event)  # covers the URL-encoded email too


def test_emails_in_error_logs_and_exception_messages_are_filtered(captured: list[dict[str, Any]]) -> None:
    logger.error(f"Failed to send invitation to {FAKE_EMAIL}")
    logger.error("Failed to send invitation to %s", FAKE_EMAIL)
    sentry_sdk.capture_exception(ValueError(f"User {FAKE_EMAIL} already exists"))
    sentry_sdk.flush()

    assert len(captured) == 3
    for event in captured:
        assert FAKE_EMAIL not in _dump(event)
