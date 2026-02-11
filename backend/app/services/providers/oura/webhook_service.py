"""Service for processing Oura Ring webhook notifications and managing subscriptions."""

from datetime import datetime, timedelta, timezone
from logging import getLogger
from typing import Any, cast
from uuid import UUID

import httpx

from app.config import settings
from app.repositories import UserConnectionRepository
from app.schemas.oura.imports import OuraWebhookNotification
from app.services.providers.factory import ProviderFactory
from app.services.providers.oura.data_247 import Oura247Data
from app.services.providers.oura.workouts import OuraWorkouts
from app.utils.structured_logging import log_structured

logger = getLogger(__name__)

OURA_WEBHOOK_API_URL = "https://api.ouraring.com/v2/webhook/subscription"

OURA_WEBHOOK_DATA_TYPES = [
    "daily_activity",
    "daily_readiness",
    "daily_sleep",
    "daily_spo2",
    "workout",
]


class OuraWebhookService:
    """Handles Oura webhook notification processing and subscription management."""

    def __init__(self) -> None:
        self.connection_repo = UserConnectionRepository()

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

    @staticmethod
    def _parse_data_timestamp(
        notification: OuraWebhookNotification,
    ) -> tuple[datetime, datetime]:
        """Parse notification timestamp into a start/end date range."""
        if notification.data_timestamp:
            try:
                data_date = datetime.fromisoformat(notification.data_timestamp.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                data_date = datetime.now(timezone.utc)
        else:
            data_date = datetime.now(timezone.utc)

        start_time = data_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = start_time + timedelta(days=1)
        return start_time, end_time

    def process_notification(
        self,
        db: Any,
        notification: OuraWebhookNotification,
    ) -> dict:
        """Process a single Oura webhook notification.

        Looks up the internal user, fetches the relevant data from Oura API,
        and saves it to the database.

        Returns:
            Dict with processing result (status, data_type, records_saved, etc.)
        """
        # Look up internal user by Oura user_id
        connection = self.connection_repo.get_by_provider_user_id(db, "oura", notification.user_id)
        if not connection:
            log_structured(
                logger,
                "warning",
                "No connection found for Oura user",
                action="oura_webhook_user_not_found",
                oura_user_id=notification.user_id,
                data_type=notification.data_type,
            )
            return {"status": "ignored", "reason": "user_not_connected"}

        internal_user_id: UUID = connection.user_id

        log_structured(
            logger,
            "info",
            "Processing Oura webhook notification",
            action="oura_webhook_processing",
            user_id=str(internal_user_id),
            oura_user_id=notification.user_id,
            data_type=notification.data_type,
            event_type=notification.event_type,
        )

        # Skip delete events
        if notification.event_type == "delete":
            log_structured(
                logger,
                "info",
                "Ignoring delete event",
                action="oura_webhook_delete_skipped",
                data_type=notification.data_type,
                user_id=str(internal_user_id),
            )
            return {"status": "ignored", "reason": "delete_event"}

        start_time, end_time = self._parse_data_timestamp(notification)

        # Get Oura provider
        factory = ProviderFactory()
        oura_strategy = factory.get_provider("oura")

        count = self._dispatch_data_type(db, notification, oura_strategy, internal_user_id, start_time, end_time)

        if count is None:
            log_structured(
                logger,
                "info",
                "Unhandled Oura data type",
                action="oura_webhook_unhandled",
                data_type=notification.data_type,
                user_id=str(internal_user_id),
            )
            return {
                "status": "ignored",
                "reason": f"unhandled_data_type: {notification.data_type}",
            }

        log_structured(
            logger,
            "info",
            "Oura webhook notification processed",
            action="oura_webhook_complete",
            user_id=str(internal_user_id),
            data_type=notification.data_type,
            event_type=notification.event_type,
            records_saved=count,
        )

        return {
            "status": "processed",
            "data_type": notification.data_type,
            "event_type": notification.event_type,
            "records_saved": count,
        }

    @staticmethod
    def _dispatch_data_type(
        db: Any,
        notification: OuraWebhookNotification,
        oura_strategy: Any,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> int | None:
        """Dispatch webhook to the appropriate data handler.

        Returns the number of records saved, or None if data_type is unhandled.
        """
        if notification.data_type in ("sleep", "daily_sleep") and oura_strategy.data_247:
            oura_247 = cast(Oura247Data, oura_strategy.data_247)
            return oura_247.load_and_save_sleep(db, user_id, start_time, end_time)

        if notification.data_type == "daily_readiness" and oura_strategy.data_247:
            oura_247 = cast(Oura247Data, oura_strategy.data_247)
            return oura_247.load_and_save_recovery(db, user_id, start_time, end_time)

        if notification.data_type == "daily_activity" and oura_strategy.data_247:
            oura_247 = cast(Oura247Data, oura_strategy.data_247)
            raw = oura_247.get_activity_samples(db, user_id, start_time, end_time)
            normalized = oura_247.normalize_activity_samples(raw, user_id)
            return oura_247.save_activity_data(db, user_id, normalized)

        if notification.data_type == "daily_spo2" and oura_strategy.data_247:
            oura_247 = cast(Oura247Data, oura_strategy.data_247)
            raw = oura_247.get_spo2_data(db, user_id, start_time, end_time)
            return oura_247.save_spo2_data(db, user_id, raw)

        if notification.data_type == "workout" and oura_strategy.workouts:
            oura_workouts = cast(OuraWorkouts, oura_strategy.workouts)
            oura_workouts.load_data(db, user_id, start_date=start_time, end_date=end_time)
            return 1

        return None

    async def create_subscriptions(
        self,
        callback_url: str | None = None,
    ) -> list[dict[str, Any]]:
        """Create Oura webhook subscriptions for all data types.

        Creates subscriptions for both 'create' and 'update' events
        across all supported data types.
        """
        headers = self._get_client_headers()
        headers["Content-Type"] = "application/json"

        verification_token = (
            settings.oura_webhook_verification_token.get_secret_value()
            if settings.oura_webhook_verification_token
            else ""
        )

        results: list[dict[str, Any]] = []

        async with httpx.AsyncClient() as client:
            for data_type in OURA_WEBHOOK_DATA_TYPES:
                for event_type in ["create", "update"]:
                    try:
                        response = await client.post(
                            OURA_WEBHOOK_API_URL,
                            headers=headers,
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

        return results

    async def list_subscriptions(self) -> Any:
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
            # List active subscriptions
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
                    results.append({"id": sub_id, "status": "error", "error": str(e)})

        return results


oura_webhook_service = OuraWebhookService()
