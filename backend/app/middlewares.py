import contextlib
import logging
import time
from collections.abc import Awaitable, Callable

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


def add_access_log_middleware(app: FastAPI) -> None:
    level = settings.access_log_level
    if level == AccessLogLevel.OFF:
        return

    def emit(request: Request, status: int, duration_ms: float) -> None:
        if level == AccessLogLevel.ERRORS and status < 400:
            return
        path = f"{request.url.path}?{request.url.query}" if request.url.query else request.url.path
        # a logging failure must never break request handling
        with contextlib.suppress(Exception):
            log_structured(
                logger,
                "error" if status >= 400 else "info",
                "http_request",
                method=request.method,
                path=path,
                status=status,
                duration_ms=duration_ms,
            )

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
        emit(request, response.status_code, round((time.perf_counter() - start) * 1000, 1))
        return response
