"""Server-Sent Events (SSE) for live sync status streaming.

Endpoints exposed under ``/users/{user_id}/sync/...``:

- ``GET /sync/stream``   — SSE feed of every sync event for the user
- ``GET /sync/recent``   — last N events stored in Redis (24 h TTL)
- ``GET /sync/runs``     — aggregated per-run status summaries

All three are tagged ``External: Sync Status`` and protected by
``ApiKeyDep`` which accepts both a developer JWT bearer token and an
``X-Open-Wearables-API-Key`` header — no separate /dashboard variants
are needed.

The SSE feed covers events from every sync source: pull syncs
(``sync_vendor_data``), Garmin webhook live + 30-day backfill, mobile
SDK uploads (Apple HealthKit, Samsung Health, Google), and Apple XML
import.
"""

from __future__ import annotations

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from app.database import DbSession
from app.schemas.sync_status import SyncRunSummary, SyncStatusEvent
from app.services import ApiKeyDep, user_service
from app.services.sync_status_service import (
    get_all_run_summaries,
    get_recent_events,
    get_run_summaries,
    stream_user_events,
)

logger = logging.getLogger(__name__)

router = APIRouter()

_SSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "X-Accel-Buffering": "no",  # disable nginx buffering
    "Connection": "keep-alive",
}


def _ensure_user_exists(db: DbSession, user_id: UUID) -> None:
    user = user_service.get(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")


@router.get(
    "/users/{user_id}/sync/stream",
    response_class=StreamingResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Server-Sent Events stream of sync status updates.",
            "content": {"text/event-stream": {}},
        },
    },
)
def stream_user_sync_status(
    user_id: UUID,
    db: DbSession,
    _api_key: ApiKeyDep,
    replay: Annotated[int, Query(ge=1, le=200, description="Replay last N events on connect.")] = 20,
) -> StreamingResponse:
    """Open a Server-Sent Events stream of sync status for a user.

    The stream emits ``event: sync.status`` messages whose ``data``
    payload is a JSON-encoded ``SyncStatusEvent``. Heartbeats are sent
    every ~15 s as SSE comments (lines starting with ``:``) to keep the
    connection alive across proxies.

    Covers events from:

    - REST pull syncs (e.g. Whoop, Oura, Polar, Suunto)
    - Garmin webhook live + 30-day backfill
    - Mobile SDK uploads (Apple HealthKit, Samsung Health, Google)
    - Apple Health XML imports

    The stream remains open until the client disconnects. ``EventSource``
    in browsers reconnects automatically.
    """
    _ensure_user_exists(db, user_id)
    return StreamingResponse(
        stream_user_events(user_id, replay_last=replay),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


@router.get(
    "/users/{user_id}/sync/recent",
    response_model=list[SyncStatusEvent],
    status_code=status.HTTP_200_OK,
)
def list_recent_sync_events(
    user_id: UUID,
    db: DbSession,
    _api_key: ApiKeyDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[SyncStatusEvent]:
    """Return the most recent stored sync events (newest first).

    Events are kept in Redis for 24 h. Use this to seed the UI before
    opening the SSE stream, or to inspect history without subscribing.
    """
    _ensure_user_exists(db, user_id)
    return get_recent_events(user_id, limit=limit)


@router.get(
    "/users/{user_id}/sync/runs",
    response_model=list[SyncRunSummary],
    status_code=status.HTTP_200_OK,
)
def list_sync_run_summaries(
    user_id: UUID,
    db: DbSession,
    _api_key: ApiKeyDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 20,
) -> list[SyncRunSummary]:
    """Return aggregated per-run summaries for recent sync activity."""
    _ensure_user_exists(db, user_id)
    return get_run_summaries(user_id, limit=limit)


@router.get(
    "/sync/runs",
    response_model=list[SyncRunSummary],
    status_code=status.HTTP_200_OK,
)
def list_all_sync_run_summaries(
    _api_key: ApiKeyDep,
    limit: Annotated[int, Query(ge=1, le=10_000)] = 50,
    user_id: Annotated[UUID | None, Query(description="Filter by user ID.")] = None,
    provider: Annotated[str | None, Query(description="Filter by provider name.")] = None,
    status: Annotated[str | None, Query(description="Filter by status.")] = None,
    source: Annotated[str | None, Query(description="Filter by source.")] = None,
) -> list[SyncRunSummary]:
    """Return aggregated per-run summaries across all users (admin view).

    Supports optional filtering by user_id, provider, status, and source.
    """
    return get_all_run_summaries(
        limit=limit,
        user_id_filter=user_id,
        provider_filter=provider,
        status_filter=status,
        source_filter=source,
    )


__all__ = ["router"]
