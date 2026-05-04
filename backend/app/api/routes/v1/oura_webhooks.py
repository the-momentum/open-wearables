"""Oura Ring webhook endpoints for receiving data notifications."""

from logging import getLogger
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request

from app.database import DbSession
from app.models import Developer
from app.services.providers.factory import ProviderFactory
from app.services.providers.oura.webhook_service import oura_webhook_service
from app.utils.auth import get_current_developer

router = APIRouter()
logger = getLogger(__name__)

_strategy = ProviderFactory().get_provider("oura")
if _strategy.webhooks is None:
    raise RuntimeError("Oura webhook handler not initialised")
_handler = _strategy.webhooks


async def _read_body(request: Request) -> bytes:
    return await request.body()


@router.post("")
def oura_webhook_notification(
    request: Request,
    db: DbSession,
    body: Annotated[bytes, Depends(_read_body)],
) -> dict:
    """Receive Oura webhook notifications.

    Delegates to OuraWebhookHandler (signature verification, payload parsing,
    Celery task dispatch).
    """
    return _handler.handle(request, body, db)


@router.get("")
def oura_webhook_verification(request: Request) -> dict:
    """Handle Oura webhook verification challenge.

    Delegates to OuraWebhookHandler.handle_challenge().
    """
    return _handler.handle_challenge(request)


@router.get("/health")
def oura_webhook_health() -> dict:
    """Health check endpoint for Oura webhook configuration."""
    return {"status": "ok", "service": "oura-webhooks"}


@router.post("/subscriptions")
async def create_webhook_subscriptions(
    current_developer: Annotated[Developer, Depends(get_current_developer)],
    callback_url: str | None = None,
) -> dict:
    """Register Oura webhook subscriptions for all data types.

    Requires Oura client_id and client_secret to be configured.
    Subscriptions are app-level (cover all authorized users).
    """
    try:
        results = await oura_webhook_service.register_subscriptions(callback_url)
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
