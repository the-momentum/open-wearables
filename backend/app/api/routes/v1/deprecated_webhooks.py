"""Deprecated webhook routes retained for backward compatibility.

These paths were registered in production before the unified
``/providers/{provider}/webhooks`` architecture was introduced.

New integrations must use:
  POST /api/v1/providers/{provider}/webhooks

Migration status:
  Garmin  — was in production; old URLs kept, but they reject every request
            with 401 (see ``_reject_garmin_legacy_route``).
  Oura    — was not in production; old paths kept for completeness only.
  Strava  — was not in production; old paths removed, since its callback URL
            must carry a secret token (POST /api/v1/providers/strava/webhooks/{token}).
"""

from typing import NoReturn

from fastapi import APIRouter, Request

from app.services.providers.garmin.webhook_handler import report_rejected_webhook_url, webhook_url_hint
from app.utils.exceptions import WebhookVerificationError
from app.utils.structured_logging import get_logger

from .oura_webhooks import router as oura_webhooks_router

logger = get_logger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Garmin — canonical path changed from /garmin/webhooks/{ping,push}
#          to /providers/garmin/webhooks in commit e458cdeb, and then to
#          /providers/garmin/webhooks/{callback token}.
# ---------------------------------------------------------------------------


def _reject_garmin_legacy_route(request: Request) -> NoReturn:
    """These paths cannot carry the callback token, so every request to them is rejected."""
    if not report_rejected_webhook_url(request):
        logger.warning(
            "Request to a deprecated Garmin webhook URL rejected",
            provider="garmin",
            action="garmin_webhook_deprecated_route_rejected",
            path=request.url.path,
            client_host=request.client.host if request.client else None,
        )
    raise WebhookVerificationError(f"Deprecated Garmin webhook URL, use {webhook_url_hint()}")


@router.post("/garmin/webhooks/ping")
def garmin_webhook_ping_compat(request: Request) -> dict:
    """Deprecated: POST /api/v1/garmin/webhooks/ping. Always rejected with 401.

    Use POST /api/v1/providers/garmin/webhooks/{callback token} instead; print the full
    URL with `uv run python scripts/garmin_webhook_url.py` on the server.
    """
    _reject_garmin_legacy_route(request)


@router.post("/garmin/webhooks/push")
def garmin_webhook_push_compat(request: Request) -> dict:
    """Deprecated: POST /api/v1/garmin/webhooks/push. Always rejected with 401.

    Use POST /api/v1/providers/garmin/webhooks/{callback token} instead; print the full
    URL with `uv run python scripts/garmin_webhook_url.py` on the server.
    """
    _reject_garmin_legacy_route(request)


# Oura — re-registered at the old path for completeness.
# It was never in production at this path.
router.include_router(oura_webhooks_router, prefix="/oura/webhooks")
