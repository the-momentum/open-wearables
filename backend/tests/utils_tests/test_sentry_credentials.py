"""Credentials must be masked in Sentry events, also with SENTRY_SEND_SENSITIVE_DATA."""

from copy import deepcopy
from typing import TYPE_CHECKING, Any, cast

import pytest
from sentry_sdk._types import AnnotatedValue
from sentry_sdk.scrubber import EventScrubber

from app.integrations.sentry import FILTERED, _credentials_scrubber, _scrubber

if TYPE_CHECKING:
    from sentry_sdk._types import Event

FAKE_API_KEY = "sk-not-a-real-api-key"
FAKE_SECRET = "not-a-real-secret"

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
