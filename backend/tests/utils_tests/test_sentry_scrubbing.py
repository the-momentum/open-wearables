"""Sentry must never receive health data or PII.

Runs the real init_sentry() with a capturing transport and asserts on the events
the SDK would actually ship.
"""

import json
import logging
from collections.abc import Generator, Iterator
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest
import sentry_sdk
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
from pydantic import BaseModel, ValidationError
from sentry_sdk.envelope import Envelope
from sentry_sdk.transport import Transport
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.integrations import sentry as sentry_integration
from app.services import raw_payload_storage
from app.utils.config_utils import LogLevel
from app.utils.logging_setup import configure_app_logger
from app.utils.structured_logging import get_logger

# A library logger: its ERROR records keep becoming Sentry events, like before.
logger = logging.getLogger("library.test_sentry_scrubbing")
app_logger = get_logger("app.test_sentry_scrubbing")

FAKE_HEART_RATE = 187.349  # a dot keeps it from matching numeric ids in the event
FAKE_EMAIL = "jane.doe@example.com"
FAKE_USERNAME = "jane-strava-login"
FAKE_PAYLOAD = "resting_hr=48"
FAKE_TOKEN = "tok-not-a-real-credential"


class _CapturingTransport(Transport):
    def __init__(self, options: dict[str, Any] | None = None) -> None:
        super().__init__(options)
        self.events: list[dict[str, Any]] = []
        self.transactions: list[dict[str, Any]] = []

    def capture_envelope(self, envelope: Envelope) -> None:
        # Encode it like the real transport: an event that cannot be encoded never ships.
        envelope.serialize()
        if (event := envelope.get_event()) is not None:
            self.events.append(event)
        if (transaction := envelope.get_transaction_event()) is not None:
            self.transactions.append(transaction)


class _Sample(BaseModel):
    heart_rate: int


@pytest.fixture
def transport() -> _CapturingTransport:
    return _CapturingTransport()


@pytest.fixture
def captured(
    request: pytest.FixtureRequest, transport: _CapturingTransport
) -> Generator[list[dict[str, Any]], None, None]:
    """Error events Sentry would ship. Parametrize indirectly with True to enable SENTRY_SEND_SENSITIVE_DATA."""
    send_sensitive = getattr(request, "param", False)
    real_init = sentry_sdk.init

    def init_with_transport(*args: Any, **kwargs: Any) -> Any:
        return real_init(*args, transport=transport, **kwargs)

    with (
        patch.object(settings, "SENTRY_ENABLED", True),
        patch.object(settings, "SENTRY_DSN", "https://public@sentry.example.com/1"),
        patch.object(settings, "SENTRY_SEND_SENSITIVE_DATA", send_sensitive),
        patch.object(settings, "SENTRY_SAMPLES_RATE", 1.0),
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


def test_database_error_keeps_its_statement_but_not_the_row(captured: list[dict[str, Any]]) -> None:
    error = IntegrityError(
        "INSERT INTO data_point_series (value) VALUES (%(value)s)",
        {"value": FAKE_HEART_RATE},
        Exception(
            'duplicate key value violates unique constraint "uq_data_point_series_source_type_time"\n'
            f"DETAIL:  Key (data_source_id, value)=(abc, {FAKE_HEART_RATE}) already exists."
        ),
    )
    sentry_sdk.capture_exception(error)
    sentry_sdk.flush()

    value = captured[0]["exception"]["values"][0]["value"]
    assert "uq_data_point_series_source_type_time" in value
    assert "INSERT INTO data_point_series" in value
    assert "[parameters: [Filtered]]" in value
    assert "DETAIL: [Filtered]" in value
    assert str(FAKE_HEART_RATE) not in _dump(captured[0])


def _raised(exc: Exception) -> Exception:
    try:
        raise exc
    except Exception as caught:
        return caught


@pytest.fixture
def app_log_level() -> Iterator[Any]:
    """Apply a LOG_LEVEL to the app logger for the test."""

    def apply(level: LogLevel | None) -> None:
        with patch.object(settings, "log_level", level):
            configure_app_logger()

    yield apply
    configure_app_logger()


def test_log_context_is_scrubbed(captured: list[dict[str, Any]]) -> None:
    app_logger.error(
        "sync failed",
        exc_info=_raised(RuntimeError("sync failed")),
        user_id="u-1",
        run_id=UUID(int=1),
        api_key=FAKE_TOKEN,
        email=FAKE_EMAIL,
        nested={"provider_username": FAKE_USERNAME},
        error=f"[type=int_parsing, input_value='{FAKE_PAYLOAD}', input_type=str]",
    )
    sentry_sdk.flush()

    # One exception event, carrying the call's attributes as a context; it must still encode.
    [event] = captured
    assert event["exception"]["values"][0]["value"] == "sync failed"
    context = event["contexts"]["log"]
    assert context["message"] == "sync failed"
    assert context["logger"] == "app.test_sentry_scrubbing"
    assert context["user_id"] == "u-1"
    assert "00000000-0000-0000-0000-000000000001" in str(context["run_id"])
    assert context["api_key"] == context["email"] == "[Filtered]"
    assert FAKE_TOKEN not in _dump(event)
    assert FAKE_EMAIL not in _dump(event)
    assert FAKE_USERNAME not in _dump(event)
    assert FAKE_PAYLOAD not in _dump(event)


@pytest.mark.parametrize("captured", [False, True], indirect=True)
def test_app_errors_without_an_exception_do_not_alert(captured: list[dict[str, Any]]) -> None:
    app_logger.error("Sync failed", user_id="u-1")
    app_logger.warning("Fetch failed", exc_info=_raised(ValueError("boom")))
    app_logger.error("Token refresh rejected", exc_info=_raised(HTTPException(status_code=401)))
    sentry_sdk.flush()

    assert captured == []


def test_app_errors_do_not_go_through_the_logging_integration(captured: list[dict[str, Any]]) -> None:
    """Otherwise every app ERROR record (each 4xx/5xx access log line) is built into an event first."""
    with patch("sentry_sdk.integrations.logging.sentry_sdk.capture_event") as capture_event:
        app_logger.error("http_request", status=401)
        logger.error("library error")

    assert capture_event.call_count == 1


def test_log_level_filters_reports_of_exceptions_but_not_alerts(
    captured: list[dict[str, Any]], app_log_level: Any
) -> None:
    app_log_level(LogLevel.CRITICAL)
    app_logger.error("Sync failed", exc_info=_raised(ValueError("filtered")))
    app_logger.error("Storage disabled", alert=True)
    app_logger.warning("Fetch failed", alert=True)
    sentry_sdk.flush()

    assert [event["message"] for event in captured] == ["Storage disabled", "Fetch failed"]


def test_alert_reports_lines_without_an_exception_or_below_error(captured: list[dict[str, Any]]) -> None:
    app_logger.error("Storage disabled", alert=True, user_id="u-1")
    app_logger.warning("Fetch failed", exc_info=_raised(ValueError("boom")), alert=True, user_id="u-2")
    sentry_sdk.flush()

    message_event, exception_event = captured
    assert message_event["level"] == "error"
    assert message_event["message"] == "Storage disabled"
    assert message_event["contexts"]["log"]["user_id"] == "u-1"
    # A captured exception is an error in Sentry, whatever the level of the line.
    assert exception_event["level"] == "error"
    assert exception_event["exception"]["values"][0]["value"] == "boom"
    assert exception_event["contexts"]["log"]["user_id"] == "u-2"


def test_alert_below_error_without_an_exception_keeps_its_level(captured: list[dict[str, Any]]) -> None:
    app_logger.warning("Fetch failed", alert=True)
    sentry_sdk.flush()

    [event] = captured
    assert event["level"] == "warning"


def test_attributes_do_not_replace_the_fields_of_the_log_context(captured: list[dict[str, Any]]) -> None:
    app_logger.error("Storage disabled", alert=True, logger="custom")
    sentry_sdk.flush()

    [event] = captured
    context = event["contexts"]["log"]
    assert context["logger"] == "app.test_sentry_scrubbing"
    assert context["attr_logger"] == "custom"


def test_misconfigured_raw_payload_storage_alerts(captured: list[dict[str, Any]]) -> None:
    try:
        raw_payload_storage.configure("s3", 1024 * 1024, s3_bucket=None)
    finally:
        raw_payload_storage.configure("disabled", 10 * 1024 * 1024)
    sentry_sdk.flush()

    [event] = captured
    assert event["message"] == "S3 storage requested but no S3 bucket configured"


def test_info_logs_do_not_become_breadcrumbs(captured: list[dict[str, Any]]) -> None:
    logger.info("Invitation sent to %s", FAKE_EMAIL)
    logger.warning("Skipping user %s", FAKE_EMAIL)
    app_logger.info("Invitation sent", email=FAKE_EMAIL)
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


@pytest.mark.parametrize("captured", [True], indirect=True)
def test_sensitive_mode_masks_credentials_in_the_log_context(captured: list[dict[str, Any]]) -> None:
    app_logger.error("sync failed", exc_info=_raised(RuntimeError("boom")), api_key=FAKE_TOKEN, email=FAKE_EMAIL)
    sentry_sdk.flush()

    [event] = captured
    assert event["contexts"]["log"]["api_key"] == "[Filtered]"
    assert event["contexts"]["log"]["email"] == FAKE_EMAIL


@pytest.mark.parametrize("captured", [True], indirect=True)
def test_sensitive_mode_ships_full_data_but_still_masks_credentials(captured: list[dict[str, Any]]) -> None:
    app = FastAPI()

    @app.post("/webhook")
    async def webhook(request: Request) -> None:
        payload = await request.json()  # noqa: F841 - expected as a frame local in this mode
        raise RuntimeError("boom")

    client = TestClient(app, raise_server_exceptions=False)
    client.post(
        "/webhook",
        json={"heart_rate": FAKE_HEART_RATE, "email": FAKE_EMAIL},
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
    )
    sentry_sdk.flush()

    event = captured[0]
    assert event["request"]["data"] == {"heart_rate": FAKE_HEART_RATE, "email": FAKE_EMAIL}
    assert any("payload" in frame.get("vars", {}) for frame in event["exception"]["values"][-1]["stacktrace"]["frames"])
    assert FAKE_TOKEN not in _dump(event)


def test_stored_raw_payload_is_referenced_not_included(captured: list[dict[str, Any]]) -> None:
    with patch.object(raw_payload_storage, "_create_s3_client", return_value=MagicMock()):
        raw_payload_storage.configure("s3", 1024 * 1024, s3_bucket="raw-bucket")
    try:
        raw_payload_storage.store_raw_payload(
            source="webhook", provider="polar", payload={"resting_hr": FAKE_PAYLOAD}, trace_id="t-1"
        )
    finally:
        raw_payload_storage.configure("disabled", 10 * 1024 * 1024)
    sentry_sdk.capture_message("processing failed")
    sentry_sdk.flush()

    crumbs = [c for c in captured[0]["breadcrumbs"]["values"] if c.get("category") == "raw_payload"]
    assert crumbs[-1]["data"]["ref"].startswith("s3://raw-bucket/raw-payloads/polar/webhook/")
    assert crumbs[-1]["data"]["trace_id"] == "t-1"
    assert FAKE_PAYLOAD not in _dump(captured[0])


def test_query_string_is_filtered_in_transactions_and_param_names(
    captured: list[dict[str, Any]], transport: _CapturingTransport
) -> None:
    app = FastAPI()

    @app.get("/users")
    async def users() -> None:
        return None

    client = TestClient(app)
    client.get(f"/users?email={FAKE_EMAIL}&{FAKE_EMAIL}=1")
    sentry_sdk.flush()

    transaction = transport.transactions[-1]
    assert transaction["request"]["query_string"] == "email=[Filtered]&[Filtered]=[Filtered]"
    assert FAKE_EMAIL not in _dump(transaction)


def test_failed_s3_upload_adds_no_breadcrumb(captured: list[dict[str, Any]]) -> None:
    with patch.object(raw_payload_storage, "_create_s3_client", return_value=MagicMock()):
        raw_payload_storage.configure("s3", 1024 * 1024, s3_bucket="raw-bucket")
    try:
        with patch.object(raw_payload_storage, "put_payload_to_s3", return_value=None):
            raw_payload_storage.store_raw_payload(source="webhook", provider="oura", payload={"x": 1})
    finally:
        raw_payload_storage.configure("disabled", 10 * 1024 * 1024)
    sentry_sdk.capture_message("processing failed")
    sentry_sdk.flush()

    crumbs = captured[0].get("breadcrumbs", {}).get("values", [])
    assert not [c for c in crumbs if c.get("category") == "raw_payload" and c["data"]["provider"] == "oura"]
