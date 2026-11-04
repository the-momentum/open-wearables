"""Credentials must be masked in Sentry events, also with SENTRY_SEND_SENSITIVE_DATA."""

import json
import traceback
from collections.abc import Generator
from copy import deepcopy
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import MagicMock, patch

import httpx
import pytest
import sentry_sdk
from sentry_sdk._types import AnnotatedValue
from sentry_sdk.consts import SPANDATA
from sentry_sdk.envelope import Envelope
from sentry_sdk.scrubber import EventScrubber
from sentry_sdk.transport import Transport

from app.config import settings
from app.integrations import sentry as sentry_integration
from app.integrations.sentry import FILTERED, _credentials_scrubber, _scrubber
from app.services.providers.oura.strategy import OuraStrategy
from app.services.providers.templates.base_oauth import BaseOAuthTemplate
from app.utils.exceptions import ProviderError

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
@pytest.mark.parametrize("key", ["client_secret", "code_verifier", "id_token", "access_token", "refresh_token"])
def test_oauth_credentials_are_masked(scrubber: EventScrubber, key: str) -> None:
    event = {
        "request": {"data": {key: FAKE_SECRET}},
        "extra": {"payload": {key: FAKE_SECRET}},
    }

    scrubbed = _scrub(scrubber, event)

    assert _is_masked(scrubbed["request"]["data"][key])
    assert _is_masked(scrubbed["extra"]["payload"][key])


@SCRUBBERS
def test_outgoing_request_query_is_masked(scrubber: EventScrubber) -> None:
    data = {"url": "https://api.ouraring.com/oauth/revoke", SPANDATA.HTTP_QUERY: f"access_token={FAKE_TOKEN}"}
    event = {
        "breadcrumbs": {"values": [{"type": "http", "data": dict(data)}]},
        "spans": [{"op": "http.client", "data": dict(data)}],
    }

    scrubbed = _scrub(scrubber, event)

    for scrubbed_data in (scrubbed["breadcrumbs"]["values"][0]["data"], scrubbed["spans"][0]["data"]):
        assert _is_masked(scrubbed_data[SPANDATA.HTTP_QUERY])
        assert scrubbed_data["url"] == "https://api.ouraring.com/oauth/revoke"


class _CapturingTransport(Transport):
    def __init__(self, options: dict[str, Any] | None = None) -> None:
        super().__init__(options)
        self.envelopes: list[Envelope] = []

    def capture_envelope(self, envelope: Envelope) -> None:
        self.envelopes.append(envelope)

    def payloads(self) -> list[dict[str, Any]]:
        events = [e.get_event() or e.get_transaction_event() for e in self.envelopes]
        return [dict(event) for event in events if event is not None]


@pytest.fixture(params=[False, True], ids=["default", "sensitive"])
def sentry_transport(request: pytest.FixtureRequest) -> Generator[_CapturingTransport, None, None]:
    """The real init_sentry() with a transport that keeps what the SDK would ship."""
    transport = _CapturingTransport()
    real_init = sentry_sdk.init

    def init_with_transport(*args: Any, **kwargs: Any) -> Any:
        return real_init(*args, transport=transport, **kwargs)

    with (
        patch.object(settings, "SENTRY_ENABLED", True),
        patch.object(settings, "SENTRY_DSN", "https://public@sentry.example.com/1"),
        patch.object(settings, "SENTRY_SEND_SENSITIVE_DATA", request.param),
        patch.object(settings, "SENTRY_SAMPLES_RATE", 1.0),
        patch.object(sentry_integration.sentry_sdk, "init", init_with_transport),
    ):
        sentry_integration.init_sentry()
    try:
        yield transport
    finally:
        sentry_sdk.get_global_scope().set_client(None)


def test_shipped_events_carry_no_outgoing_query_credentials(sentry_transport: _CapturingTransport) -> None:
    client = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200)))

    with sentry_sdk.isolation_scope(), sentry_sdk.start_transaction(name="revoke"):
        client.post("https://api.ouraring.com/oauth/revoke", params={"access_token": FAKE_TOKEN})
        sentry_sdk.capture_message("later failure in the same scope")
    sentry_sdk.flush()

    payloads = sentry_transport.payloads()
    assert {p.get("type", "event") for p in payloads} == {"event", "transaction"}
    breadcrumbs = [b for p in payloads for b in p.get("breadcrumbs", {}).get("values", [])]
    spans = [s for p in payloads for s in p.get("spans", [])]
    assert any(b.get("data", {}).get("url") == "https://api.ouraring.com/oauth/revoke" for b in breadcrumbs)
    assert any(s.get("data", {}).get("url") == "https://api.ouraring.com/oauth/revoke" for s in spans)
    assert FAKE_TOKEN not in json.dumps(payloads, default=str)


def _revoke(access_token: str, refresh_token: str) -> None:
    raise RuntimeError("revoke failed")


def test_shipped_events_carry_no_token_locals(sentry_transport: _CapturingTransport) -> None:
    # Sensitive mode ships frame locals; token parameters must still be masked there.
    try:
        _revoke(FAKE_TOKEN, FAKE_SECRET)
    except RuntimeError as e:
        sentry_sdk.capture_exception(e)
    sentry_sdk.flush()

    payloads = sentry_transport.payloads()
    assert payloads
    dumped = json.dumps(payloads, default=str)
    assert FAKE_TOKEN not in dumped
    assert FAKE_SECRET not in dumped


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

    with pytest.raises(ProviderError) as exc_info:
        _oura_oauth().deregister_user(FAKE_TOKEN)

    exc = exc_info.value
    assert exc.upstream_status == 400
    assert str(exc) == "Oura API error (status 400)"
    assert exc.__cause__ is None
    assert exc.__suppress_context__ is True
    # What Sentry and log handlers render: the hidden httpx error must not show up.
    assert FAKE_TOKEN not in "".join(traceback.format_exception(exc))


def _oura_revoke_connect_error(*args: Any, **kwargs: Any) -> httpx.Response:
    # Like httpx's own transport frames: a `request` local whose repr shows the full URL.
    request = httpx.Request("POST", args[0], params=kwargs["params"])
    raise httpx.ConnectError("[Errno 111] Connection refused", request=request)


@patch("httpx.post", side_effect=_oura_revoke_connect_error)
def test_oura_revoke_transport_error_does_not_carry_token(mock_post: MagicMock) -> None:
    with pytest.raises(ProviderError) as exc_info:
        _oura_oauth().deregister_user(FAKE_TOKEN)

    exc = exc_info.value
    assert exc.upstream_status is None
    assert str(exc) == "Oura API request failed"
    assert exc.__cause__ is None
    assert exc.__suppress_context__ is True
    assert FAKE_TOKEN not in "".join(traceback.format_exception(exc))


@patch("httpx.post", side_effect=_oura_revoke_connect_error)
def test_shipped_oura_transport_error_carries_no_token(
    mock_post: MagicMock, sentry_transport: _CapturingTransport
) -> None:
    # Sensitive mode ships frame locals; the httpx frames holding the request must not be reported.
    try:
        _oura_oauth().deregister_user(FAKE_TOKEN)
    except ProviderError as e:
        sentry_sdk.capture_exception(e)
    sentry_sdk.flush()

    payloads = sentry_transport.payloads()
    assert payloads
    assert FAKE_TOKEN not in json.dumps(payloads, default=str)


@patch("httpx.post")
def test_oura_revoke_success_does_not_raise(mock_post: MagicMock) -> None:
    mock_post.side_effect = lambda *a, **kw: _oura_revoke_response(200, *a, **kw)

    _oura_oauth().deregister_user(FAKE_TOKEN)

    assert mock_post.call_args.kwargs["params"] == {"access_token": FAKE_TOKEN}


@pytest.mark.parametrize("key", ["code", "verification_token", "hub.verify_token", "token", "access_token"])
def test_shipped_events_carry_no_incoming_query_credentials(sentry_transport: _CapturingTransport, key: str) -> None:
    query_string = f"{key}={FAKE_TOKEN}&start_date=2025-03-01"
    with sentry_sdk.isolation_scope() as scope:
        # What the ASGI integration attaches to an incoming request's events
        scope.add_event_processor(lambda event, _: {**event, "request": {"query_string": query_string}})
        sentry_sdk.capture_message("callback failed")
        with sentry_sdk.start_transaction(name="callback"):
            pass
    sentry_sdk.flush()

    payloads = sentry_transport.payloads()
    assert {p.get("type", "event") for p in payloads} == {"event", "transaction"}
    assert FAKE_TOKEN not in json.dumps(payloads, default=str)


@pytest.mark.parametrize(
    ("query_string", "shipped"),
    [
        ("code=abc&secret-tail&state=x", FILTERED),  # "abc%26secret-tail", decoded by the SDK
        ("start_date=2025-03-01&flag", "start_date=2025-03-01&flag"),
    ],
    ids=["credential", "none"],
)
def test_sensitive_mode_masks_a_query_with_a_credential_whole(query_string: str, shipped: str) -> None:
    event = sentry_integration._before_send_sensitive(cast("Event", {"request": {"query_string": query_string}}), {})

    assert event is not None
    assert event["request"]["query_string"] == shipped


def _redeem(code: str) -> None:
    raise RuntimeError("redeem failed")


def test_shipped_events_carry_no_code_locals(sentry_transport: _CapturingTransport) -> None:
    # An invitation or OAuth code is a credential in a local named "code"
    try:
        _redeem(FAKE_TOKEN)
    except RuntimeError as e:
        sentry_sdk.capture_exception(e)
    sentry_sdk.flush()

    payloads = sentry_transport.payloads()
    assert payloads
    assert FAKE_TOKEN not in json.dumps(payloads, default=str)


def _handle_callback(scope: dict[str, Any]) -> None:
    raise RuntimeError("callback failed")


def test_shipped_events_carry_no_query_credentials_in_scope_locals(sentry_transport: _CapturingTransport) -> None:
    # Sensitive mode ships frame locals; a raw ASGI scope keeps the query as bytes.
    try:
        _handle_callback({"type": "http", "query_string": f"code={FAKE_TOKEN}".encode()})
    except RuntimeError as e:
        sentry_sdk.capture_exception(e)
    sentry_sdk.flush()

    payloads = sentry_transport.payloads()
    assert payloads
    assert FAKE_TOKEN not in json.dumps(payloads, default=str)
