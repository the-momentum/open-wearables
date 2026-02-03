from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles

from app.api import head_router
from app.config import settings
from app.database import engine
from app.integrations.celery import create_celery
from app.integrations.observability import init_observability, init_providers
from app.integrations.sentry import init_sentry
from app.middlewares import add_cors_middleware
from app.utils.exceptions import DatetimeParseError, handle_exception

# Initialize OpenTelemetry providers BEFORE creating the FastAPI app
# This ensures that middleware added during app creation can use the correct providers
init_providers()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize observability instrumentations on API startup."""
    init_observability(app, engine)
    init_sentry()
    yield


api = FastAPI(title=settings.api_name, lifespan=lifespan)
celery_app = create_celery()

# Add OpenTelemetry HTTP instrumentation
# Providers must be passed explicitly since add_middleware stores the class for later instantiation
if settings.otel_enabled:
    from opentelemetry import metrics, trace
    from opentelemetry.instrumentation.asgi import OpenTelemetryMiddleware

    api.add_middleware(
        OpenTelemetryMiddleware,
        tracer_provider=trace.get_tracer_provider(),
        meter_provider=metrics.get_meter_provider(),
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
async def request_validation_exception_handler(_: Request, exc: RequestValidationError) -> None:
    raise handle_exception(exc, "")


@api.exception_handler(DatetimeParseError)
async def datetime_parse_exception_handler(_: Request, exc: DatetimeParseError) -> None:
    raise handle_exception(exc, "")


api.include_router(head_router)
