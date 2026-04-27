"""Oura webhook subscription management endpoints.

Inbound webhook events (POST/GET) are now handled by the unified webhook
router at ``/providers/oura/webhooks`` via OuraWebhookHandler.

These endpoints handle app-level subscription management (admin-only).
"""

from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException

from app.models import Developer
from app.services.providers.oura.webhook_service import oura_webhook_service
from app.utils.auth import get_current_developer

router = APIRouter()


@router.get("/health")
def oura_webhook_health() -> dict:
    """Health check endpoint for Oura webhook configuration."""
    return {"status": "ok", "service": "oura-webhooks"}


@router.post("/subscriptions")
async def upsert_webhook_subscriptions(
    current_developer: Annotated[Developer, Depends(get_current_developer)],
    callback_url: str | None = None,
) -> dict:
    """Upsert Oura webhook subscriptions for all supported data types.

    Checks existing subscriptions first — updates ones that exist, creates
    missing ones. Safe to call multiple times. Subscriptions are app-level
    (cover all authorized users).
    """
    try:
        results = await oura_webhook_service.upsert_subscriptions(callback_url)
        return {"subscriptions": results}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/subscriptions")
async def list_webhook_subscriptions(
    current_developer: Annotated[Developer, Depends(get_current_developer)],
) -> dict:
    """List active Oura webhook subscriptions."""
    try:
        subscriptions = await oura_webhook_service.list_subscriptions()
        return {"subscriptions": subscriptions}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Failed to list subscriptions: {str(e)}")


@router.post("/subscriptions/renew")
async def renew_webhook_subscriptions(
    current_developer: Annotated[Developer, Depends(get_current_developer)],
) -> dict:
    """Renew all active Oura webhook subscriptions."""
    try:
        results = await oura_webhook_service.renew_subscriptions()
        return {"renewed": results}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Failed to renew subscriptions: {str(e)}")
