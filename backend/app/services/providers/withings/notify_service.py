"""Per-user Withings notify subscription management.

Withings subscriptions are created with the user's bearer token, so they are
managed per-user rather than through the app-level webhook service.
"""

import logging
from typing import Any
from uuid import UUID

from app.database import DbSession
from app.repositories.user_connection_repository import UserConnectionRepository
from app.schemas.auth import LiveSyncMode
from app.services.providers.templates.base_oauth import BaseOAuthTemplate
from app.services.providers.templates.base_webhook_service import BaseWebhookService
from app.services.providers.withings._client import withings_request
from app.services.providers.withings.applis import SUBSCRIBED_APPLIS, withings_callback_url
from app.utils.sentry_helpers import log_and_capture_error

logger = logging.getLogger(__name__)


class WithingsNotifyService(BaseWebhookService):
    """Per-user subscribe / revoke for Withings notifications."""

    def __init__(self, connection_repo: UserConnectionRepository, oauth: BaseOAuthTemplate) -> None:
        self.connection_repo = connection_repo
        self.oauth = oauth

    def sync_user(self, db: DbSession, user_id: UUID, mode: LiveSyncMode) -> list[dict[str, Any]]:
        callback_url = withings_callback_url()
        if mode == LiveSyncMode.WEBHOOK:
            return self.subscribe_user(db, user_id, callback_url)
        return self.revoke_user(db, user_id, callback_url)

    def subscribe_user(
        self,
        db: DbSession,
        user_id: UUID,
        callback_url: str,
    ) -> list[dict[str, Any]]:
        return self._apply("subscribe", "subscribed", db, user_id, callback_url)

    def revoke_user(
        self,
        db: DbSession,
        user_id: UUID,
        callback_url: str,
    ) -> list[dict[str, Any]]:
        return self._apply("revoke", "revoked", db, user_id, callback_url)

    def _apply(
        self,
        action: str,
        ok_status: str,
        db: DbSession,
        user_id: UUID,
        callback_url: str,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for appli in SUBSCRIBED_APPLIS:
            params: dict[str, Any] = {"callbackurl": callback_url, "appli": appli}
            if action == "subscribe":
                params["comment"] = "open-wearables"
            try:
                withings_request(
                    db=db,
                    user_id=user_id,
                    connection_repo=self.connection_repo,
                    oauth=self.oauth,
                    service_path="/notify",
                    action=action,
                    params=params,
                )
                results.append({"appli": appli, "status": ok_status})
            except Exception as e:
                log_and_capture_error(
                    e,
                    logger,
                    f"Withings {action} failed",
                    extra={"provider": "withings", "appli": appli, "user_id": str(user_id)},
                )
                results.append({"appli": appli, "status": "error", "error": str(e)})
        return results
