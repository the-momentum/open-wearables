"""Garmin wellness webhook handler.

Processes a batch of wellness notifications for a single data type.
Supports both PUSH (inline records) and PING (callbackURL) per notification.
"""

import logging
from typing import Any
from uuid import UUID

from app.database import DbSession
from app.repositories import UserConnectionRepository
from app.schemas.sync_status import SyncSource, SyncStatus
from app.services.providers.garmin.backfill_state import get_trace_id
from app.services.providers.garmin.data_247 import Garmin247Data
from app.services.sync_status_service import completed, new_run_id
from app.utils.structured_logging import log_structured

logger = logging.getLogger(__name__)


def process_wellness_items(
    db: DbSession,
    connection_repo: UserConnectionRepository,
    garmin_247: Garmin247Data,
    summary_type: str,
    notifications: list[dict[str, Any]],
    errors: list[str],
    synced_user_ids: set[UUID],
    request_trace_id: str,
) -> dict[str, Any]:
    """Process wellness notifications for a single data type.

    Detects PING (items have ``callbackURL``) vs PUSH (inline data) per item.
    Groups resolved records by user_id before calling ``process_items_batch``
    to minimise DB round-trips.

    Returns:
        {"processed": int, "saved": int, "succeeded_users": list[str]}
    """
    user_items: dict[UUID, list[dict[str, Any]]] = {}

    for notification in notifications:
        garmin_user_id: str | None = notification.get("userId")
        if not garmin_user_id:
            log_structured(
                logger,
                "warning",
                "No user ID in notification",
                provider="garmin",
                trace_id=request_trace_id,
                summary_type=summary_type,
            )
            errors.append(f"{summary_type}: missing userId")
            continue

        connection = connection_repo.get_by_provider_user_id(db, "garmin", garmin_user_id)
        if not connection:
            log_structured(
                logger,
                "warning",
                "No connection found for Garmin user",
                provider="garmin",
                trace_id=request_trace_id,
                summary_type=summary_type,
                garmin_user_id=garmin_user_id,
            )
            errors.append(f"User {garmin_user_id} not connected")
            continue

        user_id = connection.user_id

        if "callbackURL" in notification:
            # PING not supported; Garmin must be configured for PUSH-only delivery.
            continue
        # PUSH: inline data
        user_items.setdefault(user_id, []).append(notification)

    total_processed = sum(len(items) for items in user_items.values())
    total_saved = 0
    succeeded_users: list[str] = []

    for uid, items in user_items.items():
        trace_id = get_trace_id(uid) or request_trace_id
        try:
            count = garmin_247.process_items_batch(db, uid, summary_type, items)
            total_saved += count
            synced_user_ids.add(uid)
            succeeded_users.append(str(uid))
            log_structured(
                logger,
                "info",
                "Saved wellness data",
                provider="garmin",
                trace_id=trace_id,
                summary_type=summary_type,
                saved=count,
                user_id=str(uid),
            )
            completed(
                uid,
                "garmin",
                SyncSource.WEBHOOK,
                run_id=new_run_id(prefix=f"garmin_webhook_{summary_type}"),
                status=SyncStatus.SUCCESS,
                message=f"Garmin live data received: {summary_type}",
                items_processed=count,
                metadata={
                    "trace_id": trace_id,
                    "summary_type": summary_type,
                    "items": len(items),
                },
            )
        except Exception as e:
            log_structured(
                logger,
                "error",
                f"Error processing {summary_type}",
                provider="garmin",
                trace_id=trace_id,
                user_id=str(uid),
                error=str(e),
            )
            errors.append(f"{summary_type} error: {e}")

    return {"processed": total_processed, "saved": total_saved, "succeeded_users": succeeded_users}
