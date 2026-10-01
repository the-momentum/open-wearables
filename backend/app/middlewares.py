import asyncio
import contextlib
import logging
import time
import traceback
from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import parse_qsl, urlencode

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.datastructures import Headers
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config import settings
from app.services.endpoint_usage import caller_type, endpoint_usage, route_key
from app.utils.config_utils import AccessLogLevel
from app.utils.structured_logging import log_structured

logger = logging.getLogger("app.access")

# Query keys whose value authenticates a request and must never reach the logs.
# Providers that sign inbound webhooks use a header instead; these three carry the
# shared secret in the URL, so the provider replays it on every delivery:
#   token              - Withings notify callback (unsigned notifications)
#   verification_token - Oura subscription verification
#   hub.verify_token   - Strava subscription validation
_REDACTED_QUERY_KEYS = frozenset({"token", "verification_token", "hub.verify_token"})
_REDACTED = "REDACTED"  # plain word: urlencode would percent-encode brackets


def _log_path(request: Request) -> str:
    """The request path with any secret-bearing query values masked."""
    query = request.url.query
    if not query:
        return request.url.path
    try:
        pairs = parse_qsl(query, keep_blank_values=True)
    except ValueError:
        # Unparseable query: drop it wholesale rather than risk logging a secret.
        return f"{request.url.path}?{_REDACTED}"
    masked = [(key, _REDACTED if key.lower() in _REDACTED_QUERY_KEYS else value) for key, value in pairs]
    return f"{request.url.path}?{urlencode(masked)}"


def add_cors_middleware(app: FastAPI) -> None:
    cors_origins = [str(origin).rstrip("/") for origin in settings.cors_origins]
    if settings.cors_allow_all:
        cors_origins = ["*"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


class _RateWindow:
    """Fixed-window counter: allow at most ``limit`` events per 60s window."""

    def __init__(self, limit: int) -> None:
        self.limit = limit
        self.window_start = 0.0
        self.count = 0

    def allow(self, now: float) -> bool:
        if now - self.window_start >= 60:
            self.window_start = now
            self.count = 0
        if self.count >= self.limit:
            return False
        self.count += 1
        return True


def add_access_log_middleware(app: FastAPI) -> None:
    level = settings.access_log_level
    if level == AccessLogLevel.OFF:
        return

    capture_body = settings.log_error_response_body
    body_window = _RateWindow(settings.log_error_response_body_max_per_minute)

    def emit(
        request: Request,
        status: int,
        duration_ms: float,
        response_body: str | None = None,
        error: BaseException | None = None,
    ) -> None:
        if level == AccessLogLevel.ERRORS and status < 400:
            return
        attributes: dict[str, Any] = {
            "method": request.method,
            "path": _log_path(request),
            "status": status,
            "duration_ms": duration_ms,
        }

        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                attributes["request_bytes"] = int(content_length)
            except ValueError:
                attributes["request_bytes"] = content_length
        if response_body is not None:
            attributes["response_body"] = response_body
        if status >= 400:
            # Extra 4xx/5xx context: content headers + the underlying cause of a body-parse
            # HTTPException (stashed on request.state by the exception handler).
            content_type = request.headers.get("content-type")
            if content_type:
                attributes["content_type"] = content_type
            content_encoding = request.headers.get("content-encoding")
            if content_encoding:
                attributes["content_encoding"] = content_encoding
            cause_type = getattr(request.state, "error_cause_type", None)
            if cause_type:
                attributes["error_cause_type"] = cause_type
                attributes["error_cause_msg"] = getattr(request.state, "error_cause_msg", None)
        if error is not None:
            # Attach the cause so a 500 is diagnosable from our own logs (stdout),
            # which — unlike Sentry — is not subject to rate-limiting/quota drops.
            # Formatting runs before the suppress() block below, so guard it here: a
            # broken __str__/__repr__ must not raise and mask the original exception.
            try:
                error_message = str(error)
                formatted_traceback = "".join(traceback.format_exception(error))
            except Exception:
                error_message = "<unavailable>"
                formatted_traceback = "<unavailable>"
            attributes["error_type"] = type(error).__name__
            attributes["error_message"] = error_message
            attributes["traceback"] = formatted_traceback
        # a logging failure must never break request handling
        with contextlib.suppress(Exception):
            log_structured(logger, "error" if status >= 400 else "info", "http_request", **attributes)

    @app.middleware("http")
    async def access_log(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as exc:
            # Unhandled exception → 500; log the line WITH the traceback so the cause
            # lands in our own logs, then re-raise so the ASGI Sentry integration still
            # captures it (single source — we don't capture here, to avoid duplicates).
            emit(request, 500, round((time.perf_counter() - start) * 1000, 1), error=exc)
            raise

        # 4xx detail stashed on request.state by the HTTPException handler; rate-capped.
        response_body: str | None = None
        if capture_body:
            detail = getattr(request.state, "error_response_body", None)
            if isinstance(detail, str) and body_window.allow(time.monotonic()):
                response_body = detail

        emit(request, response.status_code, round((time.perf_counter() - start) * 1000, 1), response_body)
        return response


class _EndpointUsageMiddleware:
    """Counts requests per route template for the telemetry ping.

    Plain ASGI rather than BaseHTTPMiddleware: the count is taken when the response
    starts, so a long-lived stream is counted once up front and never buffered.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        recorded = False

        async def send_and_record(message: Message) -> None:
            nonlocal recorded
            if message["type"] == "http.response.start" and not recorded:
                recorded = True
                _record_endpoint_usage(scope, message["status"])
            await send(message)

        try:
            await self.app(scope, receive, send_and_record)
        except Exception:
            # Unhandled exception: the 500 is sent by the server error middleware above us.
            if not recorded:
                _record_endpoint_usage(scope, 500)
            raise


def _record_endpoint_usage(scope: Scope, status: int) -> None:
    # telemetry must never break request handling
    with contextlib.suppress(Exception):
        key = route_key(scope, status)
        if key is None:
            return
        headers = Headers(scope=scope)
        auth = caller_type(headers.get("authorization"), headers.get("x-open-wearables-api-key"))
        endpoint_usage.record(key, auth, status)
        if endpoint_usage.claim_flush():
            # Redis I/O stays off the event loop.
            asyncio.get_running_loop().run_in_executor(None, endpoint_usage.flush)


def add_endpoint_usage_middleware(app: FastAPI) -> None:
    # Not installed at all when opted out, so a disabled instance counts nothing.
    if settings.telemetry_enabled:
        app.add_middleware(_EndpointUsageMiddleware)
