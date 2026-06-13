"""Per-user Withings notify subscription management.

Withings subscriptions are created with the user's bearer token, so they are
managed per-user from the connect lifecycle rather than the app-level
``register_webhooks`` hook.
"""

import logging
from typing import Any
from uuid import UUID

from app.database import DbSession
from app.repositories.user_connection_repository import UserConnectionRepository
from app.services.providers.templates.base_oauth import BaseOAuthTemplate
from app.services.providers.withings._client import withings_request
from app.utils.structured_logging import log_structured

logger = logging.getLogger(__name__)

# Notification categories: 1 = Body & Weight, 4 = Blood Pressure & Heart Rate,
# 16 = Activity (incl. workouts), 44 = Sleep.
WITHINGS_APPLI_SET: list[int] = [1, 4, 16, 44]


class WithingsNotifyService:
    """Per-user subscribe / revoke for Withings notifications."""

    def subscribe_user(
        self,
        db: DbSession,
        user_id: UUID,
        connection_repo: UserConnectionRepository,
        oauth: BaseOAuthTemplate,
        callback_url: str,
    ) -> list[dict[str, Any]]:
        return self._apply("subscribe", db, user_id, connection_repo, oauth, callback_url)

    def revoke_user(
        self,
        db: DbSession,
        user_id: UUID,
        connection_repo: UserConnectionRepository,
        oauth: BaseOAuthTemplate,
        callback_url: str,
    ) -> list[dict[str, Any]]:
        return self._apply("revoke", db, user_id, connection_repo, oauth, callback_url)

    def _apply(
        self,
        action: str,
        db: DbSession,
        user_id: UUID,
        connection_repo: UserConnectionRepository,
        oauth: BaseOAuthTemplate,
        callback_url: str,
    ) -> list[dict[str, Any]]:
        ok_status = "subscribed" if action == "subscribe" else "revoked"
        results: list[dict[str, Any]] = []
        for appli in WITHINGS_APPLI_SET:
            params: dict[str, Any] = {"callbackurl": callback_url, "appli": appli}
            if action == "subscribe":
                params["comment"] = "open-wearables"
            try:
                withings_request(
                    db=db,
                    user_id=user_id,
                    connection_repo=connection_repo,
                    oauth=oauth,
                    service_path="/notify",
                    action=action,
                    params=params,
                )
                results.append({"appli": appli, "status": ok_status})
            except Exception as e:
                log_structured(
                    logger,
                    "error",
                    f"Withings {action} failed",
                    provider="withings",
                    appli=appli,
                    user_id=str(user_id),
                    error=str(e),
                )
                results.append({"appli": appli, "status": "error", "error": str(e)})
        return results
