"""Garmin connection lifecycle event handlers.

Handles webhook events that change the state of a user's Garmin connection:
- userPermissionsChange: update the OAuth scope stored on the connection
- deregistrations: mark the connection as revoked
"""

import logging
from typing import Any

from app.database import DbSession
from app.repositories import UserConnectionRepository
from app.utils.structured_logging import log_structured

logger = logging.getLogger(__name__)


def process_user_permissions(
    db: DbSession,
    connection_repo: UserConnectionRepository,
    permissions_list: list[dict[str, Any]],
    trace_id: str,
) -> dict[str, Any]:
    """Handle userPermissionsChange entries — update scope on the connection."""
    results: dict[str, Any] = {"updated": 0, "errors": []}

    if not isinstance(permissions_list, list):
        return {"updated": 0, "errors": ["Invalid userPermissions payload format"]}

    for entry in permissions_list:
        if not isinstance(entry, dict):
            results["errors"].append("Invalid userPermissions entry format")
            continue

        garmin_user_id: str | None = entry.get("userId")
        if not garmin_user_id:
            results["errors"].append("Missing userId in userPermissions entry")
            continue

        connection = connection_repo.get_by_provider_user_id(db, "garmin", garmin_user_id)
        if not connection:
            log_structured(
                logger,
                "info",
                "No connection found for Garmin user (userPermissions) — skipping",
                provider="garmin",
                trace_id=trace_id,
                garmin_user_id=garmin_user_id,
            )
            continue

        permissions = entry.get("permissions", [])
        new_scope = " ".join(sorted(permissions)) if permissions else None
        old_scope = connection.scope
        connection_repo.update_scope(db, connection, new_scope)

        log_structured(
            logger,
            "info",
            "Updated user permissions scope",
            provider="garmin",
            trace_id=trace_id,
            garmin_user_id=garmin_user_id,
            user_id=str(connection.user_id),
            old_scope=old_scope,
            new_scope=new_scope,
        )
        results["updated"] += 1

    return results


def process_deregistrations(
    db: DbSession,
    connection_repo: UserConnectionRepository,
    deregistrations_list: list[dict[str, Any]],
    trace_id: str,
) -> dict[str, Any]:
    """Handle deregistration entries — mark connections as revoked."""
    results: dict[str, Any] = {"revoked": 0, "errors": []}

    if not isinstance(deregistrations_list, list):
        return {"revoked": 0, "errors": ["Invalid deregistrations payload format"]}

    for entry in deregistrations_list:
        if not isinstance(entry, dict):
            results["errors"].append("Invalid deregistrations entry format")
            continue

        garmin_user_id: str | None = entry.get("userId")
        if not garmin_user_id:
            results["errors"].append("Missing userId in deregistrations entry")
            continue

        connection = connection_repo.get_by_provider_user_id(db, "garmin", garmin_user_id)
        if not connection:
            log_structured(
                logger,
                "info",
                "No connection found for Garmin user (deregistration) — skipping",
                provider="garmin",
                trace_id=trace_id,
                garmin_user_id=garmin_user_id,
            )
            continue

        connection_repo.mark_as_revoked(db, connection)

        log_structured(
            logger,
            "info",
            "Revoked connection via deregistration webhook",
            provider="garmin",
            trace_id=trace_id,
            garmin_user_id=garmin_user_id,
            user_id=str(connection.user_id),
        )
        results["revoked"] += 1

    return results
