"""Strava webhook endpoints for receiving push event notifications."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.database import DbSession
from app.services.providers.factory import ProviderFactory

router = APIRouter()

_strategy = ProviderFactory().get_provider("strava")
if _strategy.webhooks is None:
    raise RuntimeError("Strava webhook handler not initialised")
_handler = _strategy.webhooks


async def _read_body(request: Request) -> bytes:
    return await request.body()


@router.get("")
def strava_webhook_verification(request: Request) -> dict:
    """Strava webhook subscription verification (GET).

    Delegates to StravaWebhookHandler.handle_challenge().
    """
    return _handler.handle_challenge(request)


@router.post("")
def strava_webhook_event(
    request: Request,
    db: DbSession,
    body: Annotated[bytes, Depends(_read_body)],
) -> dict:
    """Strava webhook event handler (POST).

    Delegates to StravaWebhookHandler (signature verification, parsing,
    Celery task dispatch).
    """
    return _handler.handle(request, body, db)


@router.get("/health")
def strava_webhook_health() -> dict:
    """Health check endpoint for Strava webhook configuration."""
    return {"status": "ok", "service": "strava-webhooks"}
