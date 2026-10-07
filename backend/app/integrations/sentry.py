import logging
import re
from typing import TYPE_CHECKING, Any

import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.scrubber import DEFAULT_DENYLIST, DEFAULT_PII_DENYLIST, EventScrubber

from app import __version__
from app.config import settings
from app.utils.structured_logging import log_structured

if TYPE_CHECKING:
    from sentry_sdk._types import Event, Hint

logger = logging.getLogger(__name__)

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
        return _EMAIL.sub(FILTERED, value)
    if isinstance(value, dict):
        return {k: _scrub_text(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_scrub_text(v) for v in value]
    return value


def _scrub_query_string(query_string: str) -> str:
    # Keep parameter names for debugging; values can be emails or search terms (?email=, ?search=).
    pairs = [part.split("=", 1)[0] for part in query_string.split("&") if part]
    return "&".join(f"{name}={FILTERED}" for name in pairs)


def before_send(event: "Event", hint: "Hint") -> "Event":
    """Strip health data / PII that the SDK's built-in scrubber does not cover."""
    # log_and_capture_error attaches `extra` as contexts, which EventScrubber skips.
    # Callers often pass `"error": str(exc)` there too, so filter pydantic input values.
    for key in ("contexts", "extra"):
        if key in event:
            event[key] = _scrub_text(event[key])
    _scrubber.scrub_dict(event.get("contexts"))

    request = event.get("request")
    query_string = request.get("query_string") if isinstance(request, dict) else None
    if isinstance(request, dict) and isinstance(query_string, str):
        request["query_string"] = _scrub_query_string(query_string)

    for exc in (event.get("exception") or {}).get("values") or []:
        exc["value"] = _scrub_text(exc.get("value"))

    if "message" in event:
        event["message"] = _scrub_text(event["message"])
    logentry = event.get("logentry")
    if isinstance(logentry, dict):
        for key in ("message", "formatted"):
            if key in logentry:
                logentry[key] = _scrub_text(logentry[key])
        params = logentry.get("params")
        if isinstance(params, list):
            logentry["params"] = [_scrub_text(p) for p in params]

    return event


def before_send_sensitive(event: "Event", hint: "Hint") -> "Event":
    """SENTRY_SEND_SENSITIVE_DATA mode: keep app-code locals, drop library-frame locals.

    Framework frames (Starlette/ASGI) hold the raw request scope, whose byte-string headers
    include Authorization / API keys - the key-based scrubber can't see those.
    """
    for exc in (event.get("exception") or {}).get("values") or []:
        for frame in (exc.get("stacktrace") or {}).get("frames") or []:
            if not frame.get("in_app"):
                frame.pop("vars", None)
    return event


def init_sentry() -> None:
    if not settings.SENTRY_ENABLED:
        return

    release = f"{__version__}+{settings.GIT_SHA[:12]}" if settings.GIT_SHA else __version__
    sensitive = settings.SENTRY_SEND_SENSITIVE_DATA
    integrations: list[Any] = [CeleryIntegration(monitor_beat_tasks=True, propagate_traces=True)]
    if sensitive:
        log_structured(
            logger,
            "warning",
            "SENTRY_SEND_SENSITIVE_DATA is on - Sentry receives request bodies, locals and log breadcrumbs, "
            "which carry health data and PII",
            action="sentry_sensitive_data_enabled",
        )
    else:
        # Log records are free-form text the scrubber cannot inspect, so don't turn
        # INFO/WARNING logs into breadcrumbs; ERROR logs still become events.
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
        before_send=before_send_sensitive if sensitive else before_send,
        integrations=integrations,
    )
