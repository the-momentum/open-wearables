"""Oura Ring webhook endpoints for receiving data notifications."""

from logging import getLogger
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError

from app.database import DbSession
from app.models import Developer
from app.schemas.oura.imports import OuraWebhookNotification
from app.services.providers.oura.webhook_service import oura_webhook_service
from app.utils.auth import get_current_developer
from app.utils.structured_logging import log_structured

router = APIRouter()
logger = getLogger(__name__)


@router.post("")
async def oura_webhook_notification(
    request: Request,
    db: DbSession,
) -> dict:
    """Receive Oura webhook notifications.

    Oura sends lightweight notifications when data is available.
    The notification contains: event_type, data_type, user_id (Oura user ID).
    Actual data must be fetched via REST API.
    """
    payload = await request.json()

    try:
        notification = OuraWebhookNotification(**payload)
    except ValidationError as e:
        log_structured(
            logger,
            "error",
            "Invalid Oura webhook payload",
            action="oura_webhook_invalid_payload",
            error=str(e),
        )
        raise HTTPException(status_code=400, detail="Invalid webhook payload")

    try:
        return oura_webhook_service.process_notification(db, notification)
    except Exception as e:
        log_structured(
            logger,
            "error",
            "Failed to process Oura webhook",
            action="oura_webhook_error",
            error=str(e),
            error_type=type(e).__name__,
            data_type=notification.data_type,
            oura_user_id=notification.user_id,
        )
        raise HTTPException(status_code=500, detail="Failed to process webhook")


@router.get("/health")
async def oura_webhook_health() -> dict:
    """Health check endpoint for Oura webhook configuration."""
    return {"status": "ok", "service": "oura-webhooks"}


@router.post("/subscriptions")
async def create_webhook_subscriptions(
    db: DbSession,
    current_developer: Annotated[Developer, Depends(get_current_developer)],
    callback_url: str | None = None,
) -> dict:
    """Create Oura webhook subscriptions for all data types.

    Requires Oura client_id and client_secret to be configured.
    Subscriptions are app-level (cover all authorized users).
    """
    try:
        results = await oura_webhook_service.create_subscriptions(callback_url)
        return {"subscriptions": results}
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/subscriptions")
async def list_webhook_subscriptions(
    db: DbSession,
    current_developer: Annotated[Developer, Depends(get_current_developer)],
) -> dict:
    """List active Oura webhook subscriptions."""
    try:
        subscriptions = await oura_webhook_service.list_subscriptions()
        return {"subscriptions": subscriptions}
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Failed to list subscriptions: {str(e)}")


@router.post("/subscriptions/renew")
async def renew_webhook_subscriptions(
    db: DbSession,
    current_developer: Annotated[Developer, Depends(get_current_developer)],
) -> dict:
    """Renew all active Oura webhook subscriptions."""
    try:
        results = await oura_webhook_service.renew_subscriptions()
        return {"renewed": results}
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Failed to renew subscriptions: {str(e)}")
