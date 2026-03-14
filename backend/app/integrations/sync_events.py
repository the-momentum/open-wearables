"""Redis Pub/Sub sync event publisher for real-time SSE updates.

Celery tasks call publish_sync_event() to notify connected SSE clients
of sync progress. Events are published to a per-user Redis channel.
"""

import json
from datetime import datetime, timezone
from logging import getLogger
from typing import Any

from app.integrations.redis_client import get_redis_client

logger = getLogger(__name__)

SYNC_CHANNEL_PREFIX = "sync:events"


def _channel_for_user(user_id: str) -> str:
    """Return the Redis Pub/Sub channel name for a given user."""
    return f"{SYNC_CHANNEL_PREFIX}:{user_id}"


def publish_sync_event(
    user_id: str,
    event_type: str,
    *,
    task_id: str | None = None,
    provider: str | None = None,
    data: dict[str, Any] | None = None,
) -> None:
    """Publish a sync progress event to the user's Redis Pub/Sub channel.

    Args:
        user_id: UUID of the user (as string).
        event_type: Event type identifier (e.g. "sync:started").
        task_id: Celery task ID, if applicable.
        provider: Provider name being synced, if applicable.
        data: Additional event payload.
    """
    channel = _channel_for_user(user_id)
    message: dict[str, Any] = {
        "type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if task_id:
        message["task_id"] = task_id
    if provider:
        message["provider"] = provider
    if data:
        message["data"] = data

    try:
        redis_client = get_redis_client()
        redis_client.publish(channel, json.dumps(message))
    except Exception:
        # Publishing is best-effort — never break the sync task
        logger.debug("Failed to publish sync event %s for user %s", event_type, user_id, exc_info=True)
