"""Oura webhook subscription management.

Handles app-level subscription registration with the Oura API:
create, list, and renew subscriptions. These are admin-only operations
called once during setup, not part of the inbound webhook pipeline.

Inbound webhook processing is handled by OuraWebhookHandler.
"""

import itertools
from logging import getLogger
from typing import Any

import httpx

from app.config import settings
from app.utils.structured_logging import log_structured

logger = getLogger(__name__)

OURA_WEBHOOK_API_URL = "https://api.ouraring.com/v2/webhook/subscription"

OURA_WEBHOOK_DATA_TYPES = [
    "workout",
    "sleep",
    "daily_sleep",
    "daily_readiness",
    "daily_activity",
    "daily_spo2",
    "daily_cardiovascular_age",
    "vo2_max",
    #
    # ----- not supported yet -----
    #
    # "sleep_time",
    # "rest_mode_period",
    # "ring_configuration",
    # "daily_stress",
    # "daily_cycle_phases",
    # "activation_status",
    # "daily_resilience",
    # "tag",
    # "enhanced_tag",
    # "session",
    #
    # ----- possibly not accessible via api - up to verification -----
    #
    # "blood_glucose",
    # "period_start",
    # "pregnancy",
    # "fertile_window",
    # "ovulation_confirmed",
]

OURA_WEBHOOK_EVENT_TYPES = ["create", "update"]


class OuraWebhookService:
    """App-level Oura webhook subscription management."""

    def _get_oura_credentials(self) -> tuple[str, str]:
        """Get Oura client credentials. Raises ValueError if not configured."""
        client_id = settings.oura_client_id
        client_secret = settings.oura_client_secret.get_secret_value() if settings.oura_client_secret else None
        if not client_id or not client_secret:
            raise ValueError("Oura client credentials not configured")
        return client_id, client_secret

    def _get_client_headers(self) -> dict[str, str]:
        """Build headers with Oura client credentials."""
        client_id, client_secret = self._get_oura_credentials()
        return {
            "x-client-id": client_id,
            "x-client-secret": client_secret,
        }

    async def register_subscriptions(
        self,
        callback_url: str | None = None,
    ) -> list[dict[str, Any]]:
        """Register missing Oura webhook subscriptions for all supported data types.

        GETs existing subscriptions first and skips ones already registered.
        Safe to call multiple times.
        """
        if not callback_url:
            raise ValueError("callback_url is required to upsert webhook subscriptions")

        headers = self._get_client_headers()
        headers["Content-Type"] = "application/json"

        if not settings.oura_webhook_verification_token:
            raise ValueError("Oura webhook verification token is not configured")
        verification_token = settings.oura_webhook_verification_token.get_secret_value()

        results: list[dict[str, Any]] = []

        async with httpx.AsyncClient() as client:
            # Build index of existing subscriptions keyed by (data_type, event_type) → (id, callback_url)
            existing: dict[tuple[str, str], tuple[str, str]] = {}
            try:
                list_resp = await client.get(OURA_WEBHOOK_API_URL, headers=headers, timeout=30.0)
                list_resp.raise_for_status()
                for sub in list_resp.json() or []:
                    key = (sub.get("data_type", ""), sub.get("event_type", ""))
                    if key[0] and key[1]:
                        existing[key] = (sub["id"], sub.get("callback_url", ""))
            except httpx.HTTPError as e:
                log_structured(
                    logger,
                    "error",
                    "Failed to list existing Oura subscriptions",
                    provider="oura",
                    action="oura_webhook_subscription_list_error",
                    error=str(e),
                )
                raise

            for data_type, event_type in itertools.product(OURA_WEBHOOK_DATA_TYPES, OURA_WEBHOOK_EVENT_TYPES):
                body = {
                    "callback_url": callback_url,
                    "verification_token": verification_token,
                    "event_type": event_type,
                    "data_type": data_type,
                }

                if (data_type, event_type) in existing:
                    sub_id, existing_url = existing[(data_type, event_type)]
                    if existing_url == callback_url:
                        results.append({"data_type": data_type, "event_type": event_type, "status": "skipped"})
                        continue
                    # callback_url changed — update the subscription
                    try:
                        response = await client.put(
                            f"{OURA_WEBHOOK_API_URL}/{sub_id}",
                            headers=headers,
                            json=body,
                            timeout=30.0,
                        )
                        response.raise_for_status()
                        results.append({"data_type": data_type, "event_type": event_type, "status": "updated"})
                    except httpx.HTTPError as e:
                        log_structured(
                            logger,
                            "error",
                            "Failed to update Oura webhook subscription",
                            provider="oura",
                            action="oura_webhook_subscription_update_error",
                            data_type=data_type,
                            event_type=event_type,
                            subscription_id=sub_id,
                            error=str(e),
                            status_code=e.response.status_code if isinstance(e, httpx.HTTPStatusError) else None,
                        )
                        results.append(
                            {"data_type": data_type, "event_type": event_type, "status": "error", "error": str(e)}
                        )
                    continue

                try:
                    response = await client.post(
                        OURA_WEBHOOK_API_URL,
                        headers=headers,
                        json=body,
                        timeout=30.0,
                    )
                    if response.status_code == 409:
                        results.append({"data_type": data_type, "event_type": event_type, "status": "skipped"})
                        continue
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
                    log_structured(
                        logger,
                        "error",
                        "Failed to register Oura webhook subscription",
                        provider="oura",
                        action="oura_webhook_subscription_register_error",
                        data_type=data_type,
                        event_type=event_type,
                        error=str(e),
                        status_code=e.response.status_code if isinstance(e, httpx.HTTPStatusError) else None,
                    )
                    results.append(
                        {
                            "data_type": data_type,
                            "event_type": event_type,
                            "status": "error",
                            "error": str(e),
                        }
                    )

        return results

    async def list_subscriptions(self) -> list[dict[str, Any]] | dict[str, Any]:
        """List active Oura webhook subscriptions."""
        headers = self._get_client_headers()

        async with httpx.AsyncClient() as client:
            response = await client.get(
                OURA_WEBHOOK_API_URL,
                headers=headers,
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    async def renew_subscriptions(self) -> list[dict[str, Any]]:
        """Renew all active Oura webhook subscriptions."""
        headers = self._get_client_headers()

        async with httpx.AsyncClient() as client:
            list_response = await client.get(
                OURA_WEBHOOK_API_URL,
                headers=headers,
                timeout=30.0,
            )
            list_response.raise_for_status()
            subscriptions = list_response.json()

            results: list[dict[str, Any]] = []
            items = subscriptions if isinstance(subscriptions, list) else []

            for sub in items:
                sub_id = sub.get("id")
                if not sub_id:
                    continue

                try:
                    renew_response = await client.put(
                        f"{OURA_WEBHOOK_API_URL}/renew/{sub_id}",
                        headers=headers,
                        timeout=30.0,
                    )
                    renew_response.raise_for_status()
                    results.append(
                        {
                            "id": sub_id,
                            "status": "renewed",
                            "response": renew_response.json(),
                        }
                    )
                except httpx.HTTPError as e:
                    log_structured(
                        logger,
                        "error",
                        "Failed to renew Oura webhook subscription",
                        provider="oura",
                        action="oura_webhook_subscription_renew_error",
                        subscription_id=sub_id,
                        error=str(e),
                        status_code=e.response.status_code if isinstance(e, httpx.HTTPStatusError) else None,
                    )
                    results.append({"id": sub_id, "status": "error", "error": str(e)})

        return results


oura_webhook_service = OuraWebhookService()
