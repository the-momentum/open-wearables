"""Strava webhook endpoints for receiving push event notifications."""

from logging import getLogger
from typing import Annotated

from fastapi import APIRouter, Query, Request

from app.database import DbSession
from app.services.providers.strava.handlers.webhook_helpers import (
    handle_webhook_event,
    handle_webhook_verification,
)

router = APIRouter()
logger = getLogger(__name__)


@router.get("/webhook")
async def strava_webhook_verification(
    hub_mode: Annotated[str, Query(alias="hub.mode")] = "",
    hub_challenge: Annotated[str, Query(alias="hub.challenge")] = "",
    hub_verify_token: Annotated[str, Query(alias="hub.verify_token")] = "",
) -> dict:
    """Strava webhook subscription verification (GET).

    When creating a webhook subscription, Strava sends a GET request
    with hub.mode, hub.challenge, and hub.verify_token parameters.
    We must echo back hub.challenge if the verify_token matches.
    """
    return await handle_webhook_verification(hub_mode, hub_challenge, hub_verify_token)


@router.post("/webhook")
async def strava_webhook_event(
    request: Request,
    db: DbSession,
) -> dict:
    """Strava webhook event handler (POST).

    Receives events when activities are created, updated, or deleted.

    Expected payload:
    {
        "object_type": "activity",
        "object_id": 12345678,
        "aspect_type": "create",
        "owner_id": 87654321,
        "subscription_id": 999,
        "event_time": 1234567890
    }

    Must always return 200 to prevent Strava from retrying.
    """
    return await handle_webhook_event(request, db)


@router.get("/health")
async def strava_webhook_health() -> dict:
    """Health check endpoint for Strava webhook configuration."""
    return {"status": "ok", "service": "strava-webhooks"}
