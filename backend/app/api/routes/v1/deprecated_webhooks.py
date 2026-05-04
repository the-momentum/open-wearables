"""Deprecated webhook routes retained for backward compatibility.

These paths were registered in production before the unified
``/providers/{provider}/webhooks`` architecture was introduced.

New integrations must use:
  POST /api/v1/providers/{provider}/webhooks

Migration status:
  Garmin  — was in production; old URLs kept until Garmin Developer Portal
            is updated to the new canonical path.
  Oura    — was not in production; old paths kept for completeness only.
  Strava  — was not in production; old paths kept for completeness only.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.database import DbSession
from app.services.providers.factory import ProviderFactory
from app.services.providers.templates.base_webhook_handler import BaseWebhookHandler

from .oura_webhooks import router as oura_webhooks_router
from .strava_webhooks import router as strava_webhooks_router

router = APIRouter()

_factory = ProviderFactory()


def _get_garmin_handler() -> BaseWebhookHandler:
    strategy = _factory.get_provider("garmin")
    if strategy.webhooks is None:
        raise RuntimeError("Garmin webhook handler not initialised")
    return strategy.webhooks


async def _read_body(request: Request) -> bytes:
    return await request.body()


# ---------------------------------------------------------------------------
# Garmin — canonical path changed from /garmin/webhooks/{ping,push}
#          to /providers/garmin/webhooks in commit e458cdeb.
# ---------------------------------------------------------------------------


@router.post("/garmin/webhooks/ping")
def garmin_webhook_ping_compat(
    request: Request,
    db: DbSession,
    body: Annotated[bytes, Depends(_read_body)],
) -> dict:
    """Deprecated: POST /api/v1/garmin/webhooks/ping.

    Use POST /api/v1/providers/garmin/webhooks instead.
    """
    handler = _get_garmin_handler()
    return handler.handle(request, body, db)


@router.post("/garmin/webhooks/push")
def garmin_webhook_push_compat(
    request: Request,
    db: DbSession,
    body: Annotated[bytes, Depends(_read_body)],
) -> dict:
    """Deprecated: POST /api/v1/garmin/webhooks/push.

    Use POST /api/v1/providers/garmin/webhooks instead.
    """
    handler = _get_garmin_handler()
    return handler.handle(request, body, db)


# Oura and Strava — re-registered at old paths for completeness.
# These were never in production at these paths.
router.include_router(oura_webhooks_router, prefix="/oura/webhooks")
router.include_router(strava_webhooks_router, prefix="/strava/webhook")
