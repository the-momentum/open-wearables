import re
from typing import TYPE_CHECKING, Any

import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.logging import LoggingIntegration, ignore_logger
from sentry_sdk.scrubber import DEFAULT_DENYLIST, DEFAULT_PII_DENYLIST, EventScrubber

from app import __version__
from app.config import settings
from app.utils.exceptions import ProviderError, is_upstream_outage
from app.utils.logging_setup import APP_LOGGER
from app.utils.structured_logging import get_logger

if TYPE_CHECKING:
    from sentry_sdk._types import Event, Hint

logger = get_logger(__name__)

FILTERED = "[Filtered]"

# Keys whose values are masked anywhere in request data, extra, contexts, breadcrumb
# data, span data and user (on top of the SDK's credential/IP defaults).
PII_DENYLIST = [
    "email",
    "username",
    "provider_username",
    "first_name",
    "last_name",
    "full_name",
    "birth_date",
    "date_of_birth",
    "phone",
    "phone_number",
    "address",
    "client_secret",
    "code_verifier",
    "id_token",
]

# Pydantic renders the offending raw value into the error string, e.g.
# "[type=int_parsing, input_value='72 bpm', input_type=str]". Greedy up to the last
# ", input_type=" on the line so a repr containing that text cannot leak a tail.
_PYDANTIC_INPUT_VALUE = re.compile(r"input_value=.*, input_type=")
# Emails are the one kind of PII we can reliably spot in free text (exception messages,
# f-string log errors). Health values in prose are not detectable - keep them out of messages.
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# SQLAlchemy and Postgres errors spell out the failing row: bound parameters, key values,
# "Failing row contains (...)". Those are health values, so everything after the label goes.
_SQL_PARAMETERS = re.compile(r"\[parameters: .*$", re.MULTILINE)
_PG_DETAIL = re.compile(r"DETAIL:.*$", re.MULTILINE)
_QUERY_VALUE = re.compile(r"=[^&]*")

_scrubber = EventScrubber(
    denylist=DEFAULT_DENYLIST + PII_DENYLIST,
    pii_denylist=DEFAULT_PII_DENYLIST,
    recursive=True,
)
# With SENTRY_SEND_SENSITIVE_DATA, credentials (tokens, secrets, cookies) are still masked.
# "headers" covers raw ASGI scopes in frame locals (a Starlette Request is a mapping over its
# scope), whose byte-string headers carry Authorization / API keys. Request headers themselves
# are scrubbed per header by the SDK, so they stay visible.
_credentials_scrubber = EventScrubber(denylist=[*DEFAULT_DENYLIST, "headers"], recursive=True)


def _scrub_text(value: Any) -> Any:
    if isinstance(value, str):
        value = _PYDANTIC_INPUT_VALUE.sub(f"input_value={FILTERED}, input_type=", value)
        value = _SQL_PARAMETERS.sub(f"[parameters: {FILTERED}]", value)
        value = _PG_DETAIL.sub(f"DETAIL: {FILTERED}", value)
        return _EMAIL.sub(FILTERED, value)
    if isinstance(value, dict):
        return {k: _scrub_text(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_scrub_text(v) for v in value]
    return value


def _mask_keys(value: Any, denylist: list[str]) -> Any:
    """Replace values under denylisted keys with FILTERED.

    before_send runs after the SDK serialized the event, so this writes plain strings;
    EventScrubber would write AnnotatedValues, which the envelope cannot encode.
    """
    if isinstance(value, dict):
        return {
            key: FILTERED if isinstance(key, str) and key.lower() in denylist else _mask_keys(item, denylist)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_mask_keys(item, denylist) for item in value]
    return value


def _route_upstream_error(event: "Event", hint: "Hint") -> "Event | None":
    """Drop a provider or storage outage, group what a provider rejected.

    An outage is not our bug, but the SDK's request and task hooks capture it like any 5xx,
    so it is dropped here, unless a line logged with ``alert=True`` carries it (its ``log``
    context marks it): the caller asked for it explicitly. A request the provider rejected
    ships, grouped per provider and status, so a broken integration is one issue with a
    count instead of an event per user.
    """
    exc_info = hint.get("exc_info")
    exc = exc_info[1] if exc_info else None
    if is_upstream_outage(exc) and "log" not in event.get("contexts", {}):
        return None
    if isinstance(exc, ProviderError):
        event["fingerprint"] = ["{{ default }}", exc.provider, str(exc.upstream_status)]
    return event


def _before_send_sensitive(event: "Event", hint: "Hint") -> "Event | None":
    """Credentials stay masked in the app log context too; EventScrubber skips contexts."""
    if _route_upstream_error(event, hint) is None:
        return None
    if "contexts" in event:
        event["contexts"] = _mask_keys(event["contexts"], _credentials_scrubber.denylist)
    return event


def before_send(event: "Event", hint: "Hint") -> "Event | None":
    """Filter free text that the key-based scrubber can't see."""
    if _route_upstream_error(event, hint) is None:
        return None
    # `contexts` is where app log events carry their message and attributes - EventScrubber skips it.
    for key in ("message", "logentry", "contexts", "extra"):
        if key in event:
            event[key] = _scrub_text(event[key])
    if "contexts" in event:
        event["contexts"] = _mask_keys(event["contexts"], _scrubber.denylist)

    for exc in (event.get("exception") or {}).get("values") or []:
        exc["value"] = _scrub_text(exc.get("value"))

    # Keep parameter names for debugging; values can be emails or search terms (?email=, ?search=).
    request = event.get("request") or {}
    if isinstance(query_string := request.get("query_string"), str):
        request["query_string"] = _scrub_text(_QUERY_VALUE.sub(f"={FILTERED}", query_string))

    return event


def init_sentry() -> None:
    if not settings.SENTRY_ENABLED:
        return

    release = f"{__version__}+{settings.GIT_SHA[:12]}" if settings.GIT_SHA else __version__
    sensitive = settings.SENTRY_SEND_SENSITIVE_DATA
    integrations: list[Any] = [CeleryIntegration(monitor_beat_tasks=True, propagate_traces=True)]
    # App code reports to Sentry itself (app.utils.structured_logging): an error with an
    # exception or a line logged with alert=True. Without this, every app ERROR record would
    # be built into an event first.
    ignore_logger(APP_LOGGER)
    ignore_logger(f"{APP_LOGGER}.*")
    if sensitive:
        logger.warning(
            "SENTRY_SEND_SENSITIVE_DATA is on - Sentry receives request bodies, locals and log breadcrumbs, "
            "which carry health data and PII",
            action="sentry_sensitive_data_enabled",
        )
    else:
        # Log records are free-form text the scrubber cannot inspect, so don't turn
        # INFO/WARNING logs into breadcrumbs; ERROR logs of libraries still become events.
        integrations.append(LoggingIntegration(level=None))

    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.SENTRY_ENV,
        server_name=settings.SENTRY_SERVER_NAME,
        release=release,
        traces_sample_rate=settings.SENTRY_SAMPLES_RATE,
        # We process health data: by default never ship request bodies (webhook/SDK payloads),
        # stack-frame locals (parsed records) or default PII (IPs, cookies, task args).
        send_default_pii=False,
        include_local_variables=sensitive,
        max_request_body_size="medium" if sensitive else "never",
        event_scrubber=_credentials_scrubber if sensitive else _scrubber,
        before_send=_before_send_sensitive if sensitive else before_send,
        # Sampled transactions carry the request (query string) too but skip before_send.
        before_send_transaction=None if sensitive else before_send,
        integrations=integrations,
    )
