"""Polar webhook subscription management.

Handles app-level webhook registration with the Polar AccessLink API.
Polar supports exactly one webhook per application, registered via Basic auth
(client_id:client_secret).

When created, Polar immediately POSTs a PING to the configured URL. The URL
must respond with HTTP 200 or the webhook will not be created. The returned
``signature_secret_key`` is auto-saved to the ``provider_settings`` table
(webhook_secret column) and is not shown again after creation.

When updating the URL via PATCH, Polar sends a new ping to the updated address
and the endpoint must respond with HTTP 200 OK for the change to be accepted.

Webhook auto-deactivates after 7 days of failed delivery. Use activate() to
re-enable it (Polar will ping the URL again before activating).
"""

from logging import getLogger
from typing import Any

import httpx
from fastapi import status

from app.config import settings
from app.schemas.providers.polar import PolarWebhookEventType
from app.utils.structured_logging import log_structured

logger = getLogger(__name__)

_POLAR_API_URL = "https://www.polaraccesslink.com"

_ALL_EVENTS = [e for e in PolarWebhookEventType if e is not PolarWebhookEventType.PING]


class PolarWebhookService:
    """App-level Polar webhook subscription management."""

    def _get_basic_auth(self) -> httpx.BasicAuth:
        client_id = settings.polar_client_id
        client_secret = settings.polar_client_secret.get_secret_value() if settings.polar_client_secret else None
        if not client_id or not client_secret:
            raise ValueError("Polar client credentials (POLAR_CLIENT_ID / POLAR_CLIENT_SECRET) not configured")
        return httpx.BasicAuth(client_id, client_secret)

    async def get_webhook(self) -> dict[str, Any] | None:
        """Return the existing webhook config, or None if not registered."""
        auth = self._get_basic_auth()
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{_POLAR_API_URL}/v3/webhooks", auth=auth, timeout=30.0)
            resp.raise_for_status()
            data = resp.json()
            webhooks = data.get("data", [])
            return webhooks[0] if webhooks else None

    async def register_subscriptions(self, callback_url: str) -> dict[str, Any]:
        """Create or verify the Polar webhook subscription.

        Calls ``get_webhook`` to check for an existing registration:
        - Same URL: returns skipped, no changes made.
        - Different URL: calls ``_patch_webhook`` to update the existing webhook in place.
        - No existing webhook: calls ``_create_webhook``; Polar returns
          ``signature_secret_key`` on creation which is not retrievable afterwards.

        Returns a result dict describing the outcome.
        """
        if not callback_url:
            raise ValueError("callback_url is required")

        auth = self._get_basic_auth()

        existing = await self.get_webhook()
        if existing:
            existing_url = existing.get("url", "")
            webhook_id = existing.get("id")

            if existing_url == callback_url:
                log_structured(
                    logger,
                    "info",
                    "Polar webhook already registered",
                    provider="polar",
                    action="polar_webhook_skipped",
                    webhook_id=webhook_id,
                )
                return {"status": "skipped", "webhook_id": webhook_id}

            if not webhook_id:
                return {"status": "error", "error": "existing webhook has no id"}
            # URL changed — patch in place
            return await self._patch_webhook(auth, webhook_id, callback_url)

        return await self._create_webhook(auth, callback_url)

    async def _patch_webhook(self, auth: httpx.BasicAuth, webhook_id: str, callback_url: str) -> dict[str, Any]:
        async with httpx.AsyncClient() as client:
            resp = await client.patch(
                f"{_POLAR_API_URL}/v3/webhooks/{webhook_id}",
                auth=auth,
                json={"events": _ALL_EVENTS, "url": callback_url},
                timeout=30.0,
            )
            resp.raise_for_status()
            result = resp.json().get("data") or {}
            log_structured(
                logger,
                "info",
                "Patched Polar webhook URL",
                provider="polar",
                action="polar_webhook_patched",
                webhook_id=webhook_id,
            )
            return {"status": "patched", "webhook_id": webhook_id, "response": result}

    async def _create_webhook(self, auth: httpx.BasicAuth, callback_url: str) -> dict[str, Any]:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{_POLAR_API_URL}/v3/webhooks",
                auth=auth,
                json={"events": _ALL_EVENTS, "url": callback_url},
                timeout=30.0,
            )
            if resp.status_code == status.HTTP_409_CONFLICT:
                log_structured(
                    logger,
                    "warning",
                    "Polar webhook already exists (409) — signature_secret_key not returned;"
                    " delete and recreate manually to obtain it",
                    provider="polar",
                    callback_url=callback_url,
                    response=resp.text,
                )
                return {"status": "skipped", "reason": "already_exists"}
            resp.raise_for_status()
            result = resp.json().get("data", resp.json())
            log_structured(
                logger,
                "info",
                "Polar webhook created",
                provider="polar",
                action="polar_webhook_created",
                webhook_id=result.get("id"),
            )
            return {"status": "created", "response": result}

    # should be wired after implementing base webhook methods & endpoinst (issue #1011)

    async def activate(self) -> dict[str, Any]:
        """Activate a deactivated Polar webhook."""
        auth = self._get_basic_auth()
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{_POLAR_API_URL}/v3/webhooks/activate", auth=auth, timeout=30.0)
            resp.raise_for_status()
            log_structured(logger, "info", "Polar webhook activated", provider="polar")
            return {"status": "activated"}

    async def deactivate(self) -> dict[str, Any]:
        """Deactivate the active Polar webhook."""
        auth = self._get_basic_auth()
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{_POLAR_API_URL}/v3/webhooks/deactivate", auth=auth, timeout=30.0)
            resp.raise_for_status()
            log_structured(logger, "info", "Polar webhook deactivated", provider="polar")
            return {"status": "deactivated"}

    async def list_subscriptions(self) -> list[dict[str, Any]]:
        webhook = await self.get_webhook()
        return [webhook] if webhook else []


polar_webhook_service = PolarWebhookService()
