"""Oura Ring webhook endpoints for receiving data notifications."""

from datetime import datetime, timedelta, timezone
from logging import getLogger
from typing import Annotated, Any, cast
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError

from app.config import settings
from app.database import DbSession
from app.models import Developer
from app.repositories import UserConnectionRepository
from app.schemas.oura.imports import OuraWebhookNotification
from app.services.providers.factory import ProviderFactory
from app.services.providers.oura.data_247 import Oura247Data
from app.services.providers.oura.workouts import OuraWorkouts
from app.utils.auth import get_current_developer

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
    try:
        payload = await request.json()
        logger.info(f"Received Oura webhook notification: {payload}")

        # Parse notification
        try:
            notification = OuraWebhookNotification(**payload)
        except ValidationError as e:
            logger.error(f"Invalid Oura webhook payload: {e}")
            raise HTTPException(status_code=400, detail="Invalid webhook payload")

        # Look up internal user by Oura user_id
        repo = UserConnectionRepository()
        connection = repo.get_by_provider_user_id(db, "oura", notification.user_id)
        if not connection:
            logger.warning(f"No connection found for Oura user {notification.user_id}")
            return {"status": "ignored", "reason": "user_not_connected"}

        internal_user_id: UUID = connection.user_id
        logger.info(
            f"Processing Oura {notification.data_type}/{notification.event_type} "
            f"for user {internal_user_id} (Oura: {notification.user_id})"
        )

        # Skip delete events
        if notification.event_type == "delete":
            logger.info(f"Ignoring delete event for {notification.data_type}")
            return {"status": "ignored", "reason": "delete_event"}

        # Get Oura provider
        factory = ProviderFactory()
        oura_strategy = factory.get_provider("oura")

        # Determine date range from notification (default: last 2 days)
        if notification.data_timestamp:
            try:
                data_date = datetime.fromisoformat(notification.data_timestamp.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                data_date = datetime.now(timezone.utc)
        else:
            data_date = datetime.now(timezone.utc)

        start_time = data_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = start_time + timedelta(days=1)

        count = 0

        # Fetch and save based on data_type
        if notification.data_type in ("sleep", "daily_sleep") and oura_strategy.data_247:
            oura_247 = cast(Oura247Data, oura_strategy.data_247)
            count = oura_247.load_and_save_sleep(db, internal_user_id, start_time, end_time)

        elif notification.data_type == "daily_readiness" and oura_strategy.data_247:
            oura_247 = cast(Oura247Data, oura_strategy.data_247)
            count = oura_247.load_and_save_recovery(db, internal_user_id, start_time, end_time)

        elif notification.data_type == "daily_activity" and oura_strategy.data_247:
            oura_247 = cast(Oura247Data, oura_strategy.data_247)
            raw = oura_247.get_activity_samples(db, internal_user_id, start_time, end_time)
            normalized = oura_247.normalize_activity_samples(raw, internal_user_id)
            count = oura_247.save_activity_data(db, internal_user_id, normalized)

        elif notification.data_type == "daily_spo2" and oura_strategy.data_247:
            oura_247 = cast(Oura247Data, oura_strategy.data_247)
            raw = oura_247.get_spo2_data(db, internal_user_id, start_time, end_time)
            count = oura_247.save_spo2_data(db, internal_user_id, raw)

        elif notification.data_type == "workout" and oura_strategy.workouts:
            oura_workouts = cast(OuraWorkouts, oura_strategy.workouts)
            oura_workouts.load_data(db, internal_user_id, start_date=start_time, end_date=end_time)
            count = 1  # load_data returns bool

        else:
            logger.info(f"Unhandled Oura data_type: {notification.data_type}")
            return {"status": "ignored", "reason": f"unhandled_data_type: {notification.data_type}"}

        logger.info(f"Processed {count} records for Oura {notification.data_type}")
        return {
            "status": "processed",
            "data_type": notification.data_type,
            "event_type": notification.event_type,
            "records_saved": count,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing Oura webhook: {str(e)}")
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

    Args:
        callback_url: The URL Oura should send notifications to.
    """
    client_id = settings.oura_client_id
    client_secret = settings.oura_client_secret.get_secret_value() if settings.oura_client_secret else None

    if not client_id or not client_secret:
        raise HTTPException(status_code=500, detail="Oura client credentials not configured")

    verification_token = settings.oura_webhook_verification_token or ""

    data_types = [
        "daily_activity",
        "daily_readiness",
        "daily_sleep",
        "daily_spo2",
        "workout",
    ]

    results: list[dict[str, Any]] = []

    async with httpx.AsyncClient() as client:
        for data_type in data_types:
            for event_type in ["create", "update"]:
                try:
                    response = await client.post(
                        "https://api.ouraring.com/v2/webhook/subscription",
                        headers={
                            "x-client-id": client_id,
                            "x-client-secret": client_secret,
                            "Content-Type": "application/json",
                        },
                        json={
                            "callback_url": callback_url or "",
                            "verification_token": verification_token,
                            "event_type": event_type,
                            "data_type": data_type,
                        },
                        timeout=30.0,
                    )
                    response.raise_for_status()
                    results.append(
                        {
                            "data_type": data_type,
                            "event_type": event_type,
                            "status": "created",
                            "response": response.json(),
                        }
                    )
                except httpx.HTTPError as e:
                    results.append(
                        {
                            "data_type": data_type,
                            "event_type": event_type,
                            "status": "error",
                            "error": str(e),
                        }
                    )

    return {"subscriptions": results}


@router.get("/subscriptions")
async def list_webhook_subscriptions(
    db: DbSession,
    current_developer: Annotated[Developer, Depends(get_current_developer)],
) -> dict:
    """List active Oura webhook subscriptions."""
    client_id = settings.oura_client_id
    client_secret = settings.oura_client_secret.get_secret_value() if settings.oura_client_secret else None

    if not client_id or not client_secret:
        raise HTTPException(status_code=500, detail="Oura client credentials not configured")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                "https://api.ouraring.com/v2/webhook/subscription",
                headers={
                    "x-client-id": client_id,
                    "x-client-secret": client_secret,
                },
                timeout=30.0,
            )
            response.raise_for_status()
            return {"subscriptions": response.json()}
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"Failed to list subscriptions: {str(e)}")


@router.post("/subscriptions/renew")
async def renew_webhook_subscriptions(
    db: DbSession,
    current_developer: Annotated[Developer, Depends(get_current_developer)],
) -> dict:
    """Renew all active Oura webhook subscriptions."""
    client_id = settings.oura_client_id
    client_secret = settings.oura_client_secret.get_secret_value() if settings.oura_client_secret else None

    if not client_id or not client_secret:
        raise HTTPException(status_code=500, detail="Oura client credentials not configured")

    async with httpx.AsyncClient() as client:
        # First list active subscriptions
        try:
            list_response = await client.get(
                "https://api.ouraring.com/v2/webhook/subscription",
                headers={
                    "x-client-id": client_id,
                    "x-client-secret": client_secret,
                },
                timeout=30.0,
            )
            list_response.raise_for_status()
            subscriptions = list_response.json()
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"Failed to list subscriptions: {str(e)}")

        # Renew each subscription
        results: list[dict[str, Any]] = []
        items = subscriptions if isinstance(subscriptions, list) else []

        for sub in items:
            sub_id = sub.get("id")
            if not sub_id:
                continue

            try:
                renew_response = await client.put(
                    f"https://api.ouraring.com/v2/webhook/subscription/renew/{sub_id}",
                    headers={
                        "x-client-id": client_id,
                        "x-client-secret": client_secret,
                    },
                    timeout=30.0,
                )
                renew_response.raise_for_status()
                results.append({"id": sub_id, "status": "renewed", "response": renew_response.json()})
            except httpx.HTTPError as e:
                results.append({"id": sub_id, "status": "error", "error": str(e)})

    return {"renewed": results}
