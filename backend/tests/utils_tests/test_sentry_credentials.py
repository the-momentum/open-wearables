"""Credentials must be masked in Sentry events, also with SENTRY_SEND_SENSITIVE_DATA."""

import traceback
from copy import deepcopy
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import MagicMock, patch

import httpx
import pytest
from sentry_sdk._types import AnnotatedValue
from sentry_sdk.scrubber import EventScrubber

from app.integrations.sentry import FILTERED, _credentials_scrubber, _scrubber
from app.services.providers.oura.strategy import OuraStrategy
from app.services.providers.templates.base_oauth import BaseOAuthTemplate

if TYPE_CHECKING:
    from sentry_sdk._types import Event

FAKE_API_KEY = "sk-not-a-real-api-key"
FAKE_SECRET = "not-a-real-secret"
FAKE_TOKEN = "tok-not-a-real-credential"

SCRUBBERS = pytest.mark.parametrize(
    "scrubber",
    [_scrubber, _credentials_scrubber],
    ids=["default", "sensitive"],
)


def _scrub(scrubber: EventScrubber, event: dict[str, Any]) -> dict[str, Any]:
    event = deepcopy(event)
    scrubber.scrub_event(cast("Event", event))
    return event


def _is_masked(value: Any) -> bool:
    # The scrubber substitutes an AnnotatedValue; the transport serializes it to "[Filtered]".
    return isinstance(value, AnnotatedValue) and value.value == FILTERED


@SCRUBBERS
def test_api_key_header_is_masked(scrubber: EventScrubber) -> None:
    event = {
        "request": {
            "headers": {
                "x-open-wearables-api-key": FAKE_API_KEY,
                "user-agent": "pytest",
            }
        }
    }

    headers = _scrub(scrubber, event)["request"]["headers"]

    assert _is_masked(headers["x-open-wearables-api-key"])
    assert headers["user-agent"] == "pytest"


@SCRUBBERS
@pytest.mark.parametrize("key", ["client_secret", "code_verifier", "id_token"])
def test_oauth_credentials_are_masked(scrubber: EventScrubber, key: str) -> None:
    event = {
        "request": {"data": {key: FAKE_SECRET}},
        "extra": {"payload": {key: FAKE_SECRET}},
    }

    scrubbed = _scrub(scrubber, event)

    assert _is_masked(scrubbed["request"]["data"][key])
    assert _is_masked(scrubbed["extra"]["payload"][key])


def _oura_oauth() -> BaseOAuthTemplate:
    oauth = OuraStrategy().oauth
    assert oauth is not None
    return oauth


def _oura_revoke_response(status_code: int, *args: Any, **kwargs: Any) -> httpx.Response:
    # A real Response bound to the real request, so raise_for_status renders the full URL.
    request = httpx.Request("POST", args[0], params=kwargs["params"])
    return httpx.Response(status_code, request=request)


@patch("httpx.post")
def test_oura_revoke_error_does_not_carry_token(mock_post: MagicMock) -> None:
    mock_post.side_effect = lambda *a, **kw: _oura_revoke_response(400, *a, **kw)

    with pytest.raises(RuntimeError) as exc_info:
        _oura_oauth().deregister_user(FAKE_TOKEN)

    exc = exc_info.value
    assert str(exc) == "Oura token revoke failed: HTTP 400"
    assert exc.__cause__ is None
    assert exc.__suppress_context__ is True
    # What Sentry and log handlers render: the hidden httpx error must not show up.
    assert FAKE_TOKEN not in "".join(traceback.format_exception(exc))


@patch("httpx.post")
def test_oura_revoke_success_does_not_raise(mock_post: MagicMock) -> None:
    mock_post.side_effect = lambda *a, **kw: _oura_revoke_response(200, *a, **kw)

    _oura_oauth().deregister_user(FAKE_TOKEN)

    assert mock_post.call_args.kwargs["params"] == {"access_token": FAKE_TOKEN}
