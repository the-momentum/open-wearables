"""Strava webhook subscription management.

Handles app-level subscription registration with the Strava API:
create, view, and delete subscriptions. These are admin-only operations
called once during setup, not part of the inbound webhook pipeline.

Strava allows exactly one subscription per app. If a subscription already
exists with a different callback URL it is deleted and re-created.

Inbound webhook processing is handled by StravaWebhookHandler.
"""

from logging import getLogger
from typing import Any

import httpx

from app.config import settings
from app.utils.structured_logging import log_structured

logger = getLogger(__name__)

STRAVA_PUSH_SUBSCRIPTIONS_URL = "https://www.strava.com/api/v3/push_subscriptions"


class StravaWebhookService:
    """App-level Strava webhook subscription management."""

    def _get_strava_credentials(self) -> tuple[str, str]:
        """Get Strava client credentials. Raises ValueError if not configured."""
        client_id = settings.strava_client_id
        client_secret = settings.strava_client_secret.get_secret_value() if settings.strava_client_secret else None
        if not client_id or not client_secret:
            raise ValueError("Strava client credentials not configured")
        return client_id, client_secret

    async def register_subscriptions(self, callback_url: str) -> list[dict[str, Any]]:
        """Register or update the Strava webhook subscription.

        GETs the existing subscription first. If one exists with the same
        callback URL it is skipped. If the callback URL differs the old
        subscription is deleted and a new one is created. Safe to call
        multiple times.
        """
        if not callback_url:
            raise ValueError("callback_url is required to register webhook subscription")

        client_id, client_secret = self._get_strava_credentials()
        verify_token = settings.strava_webhook_verify_token.get_secret_value()  # type: ignore[union-attr]

        async with httpx.AsyncClient() as client:
            # Check for existing subscription
            existing: dict[str, Any] | None = None
            try:
                list_resp = await client.get(
                    STRAVA_PUSH_SUBSCRIPTIONS_URL,
                    params={"client_id": client_id, "client_secret": client_secret},
                    timeout=30.0,
                )
                list_resp.raise_for_status()
                subscriptions = list_resp.json()
                if isinstance(subscriptions, list) and subscriptions:
                    existing = subscriptions[0]
            except httpx.HTTPError as e:
                log_structured(
                    logger,
                    "error",
                    "Failed to list existing Strava subscriptions",
                    provider="strava",
                    action="strava_webhook_subscription_list_error",
                    error=str(e),
                )
                raise

            if existing:
                sub_id = existing.get("id")
                existing_url = existing.get("callback_url", "")

                if existing_url == callback_url:
                    log_structured(
                        logger,
                        "info",
                        "Strava webhook subscription already up to date",
                        provider="strava",
                        action="strava_webhook_subscription_skipped",
                        subscription_id=sub_id,
                    )
                    return [{"subscription_id": sub_id, "status": "skipped"}]

                # Callback URL changed — delete and re-create
                try:
                    del_resp = await client.delete(
                        f"{STRAVA_PUSH_SUBSCRIPTIONS_URL}/{sub_id}",
                        params={"client_id": client_id, "client_secret": client_secret},
                        timeout=30.0,
                    )
                    del_resp.raise_for_status()
                    log_structured(
                        logger,
                        "info",
                        "Deleted stale Strava webhook subscription",
                        provider="strava",
                        action="strava_webhook_subscription_deleted",
                        subscription_id=sub_id,
                    )
                except httpx.HTTPError as e:
                    log_structured(
                        logger,
                        "error",
                        "Failed to delete existing Strava subscription",
                        provider="strava",
                        action="strava_webhook_subscription_delete_error",
                        subscription_id=sub_id,
                        error=str(e),
                        status_code=e.response.status_code if isinstance(e, httpx.HTTPStatusError) else None,
                    )
                    return [{"subscription_id": sub_id, "status": "error", "error": str(e)}]

            # Create new subscription (Strava requires form-encoded body)
            try:
                create_resp = await client.post(
                    STRAVA_PUSH_SUBSCRIPTIONS_URL,
                    data={
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "callback_url": callback_url,
                        "verify_token": verify_token,
                    },
                    timeout=30.0,
                )
                if create_resp.status_code == 409:
                    return [{"status": "skipped", "reason": "already_exists"}]
                create_resp.raise_for_status()
                result = create_resp.json()
                log_structured(
                    logger,
                    "info",
                    "Strava webhook subscription created",
                    provider="strava",
                    action="strava_webhook_subscription_created",
                    subscription_id=result.get("id"),
                )
                return [{"status": "created", "response": result}]
            except httpx.HTTPError as e:
                log_structured(
                    logger,
                    "error",
                    "Failed to create Strava webhook subscription",
                    provider="strava",
                    action="strava_webhook_subscription_create_error",
                    error=str(e),
                    status_code=e.response.status_code if isinstance(e, httpx.HTTPStatusError) else None,
                )
                return [{"status": "error", "error": str(e)}]

    async def list_subscriptions(self) -> list[dict[str, Any]]:
        """List active Strava webhook subscriptions."""
        client_id, client_secret = self._get_strava_credentials()

        async with httpx.AsyncClient() as client:
            response = await client.get(
                STRAVA_PUSH_SUBSCRIPTIONS_URL,
                params={"client_id": client_id, "client_secret": client_secret},
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()


strava_webhook_service = StravaWebhookService()
