import contextlib
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.utils.config_utils import AccessLogLevel
from app.utils.structured_logging import log_structured

logger = logging.getLogger("app.access")


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

    def emit(request: Request, status: int, duration_ms: float, response_body: str | None = None) -> None:
        if level == AccessLogLevel.ERRORS and status < 400:
            return
        path = f"{request.url.path}?{request.url.query}" if request.url.query else request.url.path
        attributes: dict[str, Any] = {
            "method": request.method,
            "path": path,
            "status": status,
            "duration_ms": duration_ms,
        }
        if response_body is not None:
            attributes["response_body"] = response_body
        # a logging failure must never break request handling
        with contextlib.suppress(Exception):
            log_structured(logger, "error" if status >= 400 else "info", "http_request", **attributes)

    @app.middleware("http")
    async def access_log(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            # Unhandled exception → 500; log the line, then re-raise so the ASGI
            # Sentry integration still captures it.
            emit(request, 500, round((time.perf_counter() - start) * 1000, 1))
            raise

        # 4xx detail stashed on request.state by the HTTPException handler; rate-capped.
        response_body: str | None = None
        if capture_body:
            detail = getattr(request.state, "error_response_body", None)
            if isinstance(detail, str) and body_window.allow(time.monotonic()):
                response_body = detail

        emit(request, response.status_code, round((time.perf_counter() - start) * 1000, 1), response_body)
        return response
