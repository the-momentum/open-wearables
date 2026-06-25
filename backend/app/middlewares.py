import logging
import time

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.config import settings

logger = logging.getLogger("app.access")


class RequestTimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start = time.perf_counter()
        safe_path = request.url.path.replace("\r", "\\r").replace("\n", "\\n")
        client = f"{request.client.host}:{request.client.port}" if request.client else "-"
        try:
            response = await call_next(request)
        except Exception:
            duration = time.perf_counter() - start
            logger.exception("%s %s %s ERROR (%.3fs)", client, request.method, safe_path, duration)
            raise
        duration = time.perf_counter() - start
        logger.info(
            "%s %s %s %s (%.3fs)",
            client,
            request.method,
            safe_path,
            response.status_code,
            duration,
        )
        return response


def add_cors_middleware(app: FastAPI) -> None:
    cors_origins = [str(origin).rstrip("/") for origin in settings.cors_origins]
    if settings.cors_allow_all:
        cors_origins = ["*"]

    app.add_middleware(
        CORSMiddleware,  # ty:ignore[invalid-argument-type]
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
