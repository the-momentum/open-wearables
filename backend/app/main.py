import logging
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from logging import INFO, StreamHandler, basicConfig
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import head_router
from app.config import settings
from app.integrations.celery import create_celery
from app.integrations.sentry import init_sentry
from app.middlewares import add_cors_middleware
from app.services import raw_payload_storage
from app.services.outgoing_webhooks import svix as svix_service
from app.utils.exceptions import DatetimeParseError, handle_exception

# Configure logging to use stdout instead of stderr
# Some platforms convert stderr logs to level.error automatically, so we must use stdout
# This ensures platforms correctly identify log levels from JSON structured logs
basicConfig(
    level=INFO,
    format="[%(asctime)s - %(name)s] (%(levelname)s) %(message)s",
    handlers=[StreamHandler(sys.stdout)],
)

# Remove uvicorn's default handlers to prevent duplicate logs (uvicorn.error)
# and ensure access logs (uvicorn.access) also get timestamps via the root logger
for _name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
    _logger = logging.getLogger(_name)
    _logger.handlers.clear()
    _logger.propagate = True


@asynccontextmanager
async def _lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    svix_service.register_event_types()
    yield


api = FastAPI(title=settings.api_name, lifespan=_lifespan)
celery_app = create_celery()
init_sentry()
raw_payload_storage.configure(
    settings.raw_payload_storage,
    settings.raw_payload_max_size_bytes,
    s3_bucket=settings.raw_payload_s3_bucket or settings.aws_bucket_name,
    s3_prefix=settings.raw_payload_s3_prefix,
    s3_endpoint_url=settings.raw_payload_s3_endpoint_url,
)

add_cors_middleware(api)

# Mount static files for provider icons
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    api.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@api.get("/")
async def root() -> dict[str, str]:
    return {"message": "Server is running!"}


@api.exception_handler(RequestValidationError)
async def request_validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    # (FastAPI ≥ 0.130 rejects empty required str form fields before the handler runs)
    if request.url.path.endswith("/auth/login"):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Incorrect email or password"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    raise handle_exception(exc, "")


@api.exception_handler(DatetimeParseError)
async def datetime_parse_exception_handler(_: Request, exc: DatetimeParseError) -> None:
    raise handle_exception(exc, "")


api.include_router(head_router)
