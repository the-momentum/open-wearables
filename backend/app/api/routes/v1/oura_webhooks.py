"""Oura Ring webhook endpoints for receiving data notifications."""

import hashlib
import hmac
import json
from logging import getLogger
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError

from app.config import settings
from app.database import DbSession
from app.models import Developer
from app.schemas.providers.oura import OuraWebhookNotification
from app.services.providers.oura.webhook_service import oura_webhook_service
from app.services.raw_payload_storage import store_raw_payload
from app.utils.auth import get_current_developer
from app.utils.structured_logging import log_structured

router = APIRouter()
logger = getLogger(__name__)


def _verify_oura_signature(body: bytes, signature: str | None, timestamp: str | None) -> bool:
    """Verify Oura webhook HMAC-SHA256 signature.

    Per Oura docs the HMAC is computed as ``HMAC-SHA256(client_secret, timestamp + body)``
    and sent upper-case hex in the ``x-oura-signature`` header.
    """
    if not signature or not timestamp:
        return False
    secret = settings.oura_client_secret.get_secret_value() if settings.oura_client_secret else None
    if not secret:
        return False
    mac = hmac.new(secret.encode(), timestamp.encode() + body, hashlib.sha256)
    return hmac.compare_digest(mac.hexdigest().upper(), signature.upper())


async def _require_verified_body(request: Request) -> bytes:
    """Async dependency: read raw body and verify Oura HMAC-SHA256 signature.

    Keeping body-reading in a dependency (async) while the route handler
    itself stays sync avoids holding the event loop hostage during
    synchronous DB work.
    """
    body = await request.body()
    signature = request.headers.get("x-oura-signature")
    timestamp = request.headers.get("x-oura-timestamp")
    if not _verify_oura_signature(body, signature, timestamp):
        log_structured(
            logger,
            "warning",
            "Invalid Oura webhook signature",
            action="oura_webhook_signature_invalid",
        )
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    return body


@router.post("")
def oura_webhook_notification(
    body: Annotated[bytes, Depends(_require_verified_body)],
    db: DbSession,
) -> dict:
    """Receive Oura webhook notifications.

    Oura sends lightweight notifications when data is available.
    The notification contains: event_type, data_type, user_id (Oura user ID).
    Actual data must be fetched via REST API.
    """
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    store_raw_payload(
        source="webhook",
        provider="oura",
        payload=payload,
    )

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


@router.get("")
def oura_webhook_verification(
    verification_token: str | None = None,
    challenge: str | None = None,
) -> dict:
    """Handle Oura webhook verification challenge.

    When creating a subscription Oura sends a GET with verification_token and
    challenge query params.  We must verify the token matches our configured
    token and echo the challenge back.
    """
    expected = (
        settings.oura_webhook_verification_token.get_secret_value()
        if settings.oura_webhook_verification_token
        else None
    )
    if not expected or not verification_token or not hmac.compare_digest(verification_token, expected):
        raise HTTPException(status_code=401, detail="Invalid verification token")
    return {"challenge": challenge or ""}


@router.get("/health")
def oura_webhook_health() -> dict:
    """Health check endpoint for Oura webhook configuration."""
    return {"status": "ok", "service": "oura-webhooks"}


@router.post("/subscriptions")
async def create_webhook_subscriptions(
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
