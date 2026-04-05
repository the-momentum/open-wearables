import logging
import sys
from logging import INFO, StreamHandler, basicConfig
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles

from app.api import head_router
from app.config import settings
from app.integrations.celery import create_celery
from app.integrations.sentry import init_sentry
from app.middlewares import add_cors_middleware
from app.services import raw_payload_storage
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

api = FastAPI(
    title=settings.api_name,
    openapi_tags=[
        # External: 3rd party integration endpoints
        {"name": "External: Users", "description": "Create and manage end-users"},
        {"name": "External: Connections", "description": "User-provider connections"},
        {"name": "External: Summaries", "description": "Daily aggregated health data"},
        {"name": "External: Timeseries", "description": "Granular time-series health data"},
        {"name": "External: Events", "description": "Workouts and sleep sessions"},
        {"name": "External: Providers", "description": "OAuth authorization and provider listing"},
        {"name": "External: Data Sync", "description": "Trigger data sync from providers"},
        {"name": "External: Workouts", "description": "Provider-specific workout data"},
        {"name": "External: Apple Health Import", "description": "Apple Health XML import via S3 or direct upload"},
        {"name": "External: Connectors", "description": "Third-party data connectors (Auto Health Export)"},
        {"name": "External: Mobile SDK", "description": "SDK sync, user tokens, and invitation codes"},
        {"name": "External: Token", "description": "Token refresh and revocation"},
        {"name": "External: Data Sources", "description": "User data source priorities"},
        # Internal: dashboard management endpoints
        {"name": "Internal: Auth", "description": "Dashboard authentication"},
        {"name": "Internal: Developers", "description": "Developer and team management"},
        {"name": "Internal: Invitations", "description": "Team invitations"},
        {"name": "Internal: API Keys", "description": "API key management"},
        {"name": "Internal: Applications", "description": "Application credentials"},
        {"name": "Internal: Dashboard", "description": "Dashboard statistics"},
        {"name": "Internal: Priorities", "description": "Global provider and device type priorities"},
        {"name": "Internal: Providers", "description": "Provider enable/disable settings"},
        {"name": "Internal: Data Lifecycle", "description": "Data archival settings"},
        # System: provider webhooks and debug tools
        {"name": "System: Garmin Webhooks", "description": "Garmin push/ping webhook receiver"},
        {"name": "System: Oura Webhooks", "description": "Oura data notification webhook receiver"},
        {"name": "System: Strava Webhooks", "description": "Strava event notification webhook receiver"},
        {"name": "System: Provider Webhooks", "description": "Unified provider webhook receiver"},
        {"name": "System: Debug", "description": "Suunto debug and raw data endpoints"},
    ],
)
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
async def request_validation_exception_handler(_: Request, exc: RequestValidationError) -> None:
    raise handle_exception(exc, "")


@api.exception_handler(DatetimeParseError)
async def datetime_parse_exception_handler(_: Request, exc: DatetimeParseError) -> None:
    raise handle_exception(exc, "")


api.include_router(head_router)
