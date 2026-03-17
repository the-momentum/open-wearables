"""SSE (Server-Sent Events) endpoint for real-time sync progress.

Subscribes to a per-user Redis Pub/Sub channel and streams every sync
event to the browser over an open HTTP connection.
"""

import asyncio
import json
from collections.abc import AsyncGenerator
from logging import getLogger
from typing import Annotated
from uuid import UUID

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.config import settings
from app.integrations.sync_events import SYNC_CHANNEL_PREFIX
from app.utils.auth import verify_query_token

logger = getLogger(__name__)

router = APIRouter()


async def _event_generator(user_id: str) -> AsyncGenerator[str, None]:
    """Yield SSE-formatted messages from a Redis Pub/Sub channel.

    The ``timeout=15.0`` parameter in ``pubsub.get_message()`` controls
    the keep-alive interval, NOT message latency.

    - If a sync event arrives (e.g., at t=0.1s), Redis delivers it **immediately**.
    - If NO event arrives for 15 seconds, ``get_message()`` returns None.
    - We then yield a ``: keepalive`` comment to prevent the browser/proxy
      from closing the idle connection.

    This ensures instant updates while maintaining a stable long-lived connection.
    """
    channel = f"{SYNC_CHANNEL_PREFIX}:{user_id}"

    redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
    pubsub = redis_client.pubsub()

    try:
        await pubsub.subscribe(channel)

        while True:
            # Wait up to 15 s for a message, then send a keep-alive comment
            # This does NOT delay messages - they are returned as soon as published.
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=15.0)

            if message and message["type"] == "message":
                raw = message["data"]

                # Parse to extract event type for SSE "event:" field
                try:
                    payload = json.loads(raw)
                    event_type = payload.get("type", "message")
                except (json.JSONDecodeError, TypeError):
                    event_type = "message"
                    raw = json.dumps({"type": "message", "data": raw})

                yield f"event: {event_type}\ndata: {raw}\n\n"

                # If this was a terminal event, close the stream
                if event_type in ("sync:completed", "sync:error"):
                    return
            else:
                # SSE keep-alive comment (ignored by EventSource)
                yield ": keepalive\n\n"

    except asyncio.CancelledError:
        pass
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.close()
        await redis_client.aclose()


@router.get("/users/{user_id}/sync/events")
async def sync_events_stream(
    user_id: UUID,
    _developer_id: Annotated[str, Depends(verify_query_token)],
) -> StreamingResponse:
    """Stream real-time sync progress events via Server-Sent Events (SSE).

    **Authentication:**
    Pass your JWT token as a ``token`` query parameter
    (``EventSource`` does not support custom headers).

    **Event types emitted:**
    (See ``SyncEventType`` in frontend types for full list)

    The stream closes automatically after a terminal event.
    """
    return StreamingResponse(
        _event_generator(str(user_id)),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
