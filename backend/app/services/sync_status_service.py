"""Sync status service.

Centralised emission, persistence, and distribution of sync status events.

Architecture:
- Producers (Celery tasks, webhook handlers) call ``emit()`` to publish a
  :class:`SyncStatusEvent`.
- Events are appended to a capped per-user Redis list (``recent``) and a
  per-run hash so that consumers can replay history when the SSE stream
  starts and inspect the state of any individual run.
- Events are also published on Redis pub/sub channels so any FastAPI
  worker can fan them out to connected SSE clients in real time.

Channels:
- ``sync:status:user:<user_id>``  — all events for a single user
- ``sync:status:all``             — every event (used by admin/dashboard
  consumers)

Keys (all TTL'd to ``HISTORY_TTL_SECONDS``):
- ``sync:status:user:<user_id>:recent``     — list of JSON events (LPUSH)
- ``sync:status:user:<user_id>:runs``       — set of run_ids
- ``sync:status:run:<run_id>``              — JSON-encoded latest event
"""

import logging
import threading
import time
from collections.abc import Generator
from contextlib import suppress
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from app.integrations.redis_client import get_redis_client
from app.schemas.sync_status import (
    SyncRunSummary,
    SyncSource,
    SyncStage,
    SyncStatus,
    SyncStatusEvent,
)
from app.utils.sse import format_comment, format_event

logger = logging.getLogger(__name__)

HISTORY_TTL_SECONDS = 24 * 60 * 60  # 24h
MAX_RECENT_EVENTS = 200
SSE_HEARTBEAT_SECONDS = 15.0
SSE_POLL_TIMEOUT_SECONDS = 1.0


def _user_channel(user_id: str | UUID) -> str:
    return f"sync:status:user:{user_id}"


def _global_channel() -> str:
    return "sync:status:all"


def _user_recent_key(user_id: str | UUID) -> str:
    return f"sync:status:user:{user_id}:recent"


def _user_runs_key(user_id: str | UUID) -> str:
    return f"sync:status:user:{user_id}:runs"


def _run_key(run_id: str) -> str:
    return f"sync:status:run:{run_id}"


def new_run_id(prefix: str = "run") -> str:
    """Allocate a fresh run identifier."""
    return f"{prefix}_{uuid4().hex[:16]}"


def emit(event: SyncStatusEvent) -> None:
    """Persist and broadcast a sync status event.

    Failures are logged but never raised — sync flow must not be blocked
    by Redis problems.
    """
    try:
        client = get_redis_client()
        payload = event.model_dump_json()
        user_id = str(event.user_id)

        pipe = client.pipeline(transaction=False)
        pipe.lpush(_user_recent_key(user_id), payload)
        pipe.ltrim(_user_recent_key(user_id), 0, MAX_RECENT_EVENTS - 1)
        pipe.expire(_user_recent_key(user_id), HISTORY_TTL_SECONDS)
        pipe.sadd(_user_runs_key(user_id), event.run_id)
        pipe.expire(_user_runs_key(user_id), HISTORY_TTL_SECONDS)
        pipe.set(_run_key(event.run_id), payload, ex=HISTORY_TTL_SECONDS)
        pipe.publish(_user_channel(user_id), payload)
        pipe.publish(_global_channel(), payload)
        pipe.execute()
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Failed to emit sync status event: %s", exc, exc_info=True)

    # Dispatch outgoing webhooks in a background thread so the Svix HTTP
    # round-trip (~2 s) does not block the Celery task or inflate sync duration.
    threading.Thread(
        target=_maybe_dispatch_outgoing_webhook,
        args=(event,),
        daemon=True,
    ).start()


def _maybe_dispatch_outgoing_webhook(event: SyncStatusEvent) -> None:
    """Forward terminal sync events as outgoing webhooks (Svix).

    We only forward terminal transitions (started / completed / failed) to
    avoid spamming subscribers with intermediate progress updates.
    """
    try:
        # Imported lazily to avoid circular imports between services.
        from app.services.outgoing_webhooks import events as outgoing

        stage = event.stage if isinstance(event.stage, str) else event.stage.value
        status = event.status if isinstance(event.status, str) else event.status.value
        source = event.source if isinstance(event.source, str) else event.source.value

        if stage == "started":
            outgoing.on_sync_started(
                user_id=event.user_id,
                provider=event.provider,
                source=source,
                run_id=event.run_id,
                message=event.message,
                metadata=event.metadata,
            )
        elif stage == "completed":
            outgoing.on_sync_completed(
                user_id=event.user_id,
                provider=event.provider,
                source=source,
                run_id=event.run_id,
                status=status,
                message=event.message,
                items_processed=event.items_processed,
                metadata=event.metadata,
            )
        elif stage == "failed":
            outgoing.on_sync_failed(
                user_id=event.user_id,
                provider=event.provider,
                source=source,
                run_id=event.run_id,
                error=event.error or "unknown",
                message=event.message,
                metadata=event.metadata,
            )
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("Failed to dispatch outgoing sync webhook: %s", exc, exc_info=True)


def emit_event(
    *,
    user_id: str | UUID,
    provider: str,
    source: SyncSource | str,
    stage: SyncStage | str,
    status: SyncStatus | str,
    run_id: str | None = None,
    message: str | None = None,
    progress: float | None = None,
    items_processed: int | None = None,
    items_total: int | None = None,
    error: str | None = None,
    metadata: dict[str, Any] | None = None,
    started_at: datetime | None = None,
    ended_at: datetime | None = None,
) -> SyncStatusEvent:
    """Convenience helper that builds and emits a :class:`SyncStatusEvent`."""
    event = SyncStatusEvent(
        run_id=run_id or new_run_id(),
        user_id=user_id if isinstance(user_id, UUID) else UUID(str(user_id)),
        provider=provider,
        source=SyncSource(source) if not isinstance(source, SyncSource) else source,
        stage=SyncStage(stage) if not isinstance(stage, SyncStage) else stage,
        status=SyncStatus(status) if not isinstance(status, SyncStatus) else status,
        message=message,
        progress=progress,
        items_processed=items_processed,
        items_total=items_total,
        error=error,
        metadata=metadata or {},
        started_at=started_at,
        ended_at=ended_at,
    )
    emit(event)
    return event


def get_recent_events(user_id: str | UUID, limit: int = 50) -> list[SyncStatusEvent]:
    """Return the most recent stored events for a user (newest first)."""
    raw = get_redis_client().lrange(_user_recent_key(user_id), 0, max(0, limit - 1))
    events: list[SyncStatusEvent] = []
    for item in raw:
        with suppress(ValueError, TypeError):
            events.append(SyncStatusEvent.model_validate_json(item))
    return events


def get_run_summaries(user_id: str | UUID, limit: int = 20) -> list[SyncRunSummary]:
    """Aggregate recent events into per-run summaries (newest first).

    Reads the per-user runs set to discover all known run IDs, then fetches
    the latest event for each run from its dedicated hash key.  This avoids
    the hard ceiling imposed by reading only the capped recent-events list
    (``MAX_RECENT_EVENTS`` raw events / ~4 events-per-run ≈ 50 runs max).

    Terminal events (completed / failed / cancelled) don't carry
    ``started_at``; we recover it by scanning the recent-events list once
    and building a run → started_at lookup so duration can be calculated.
    """
    client = get_redis_client()

    raw_run_ids: set[str | bytes] = client.smembers(_user_runs_key(user_id))
    if not raw_run_ids:
        return []

    run_ids = [r if isinstance(r, str) else r.decode("utf-8") for r in raw_run_ids]

    # Build started_at lookup from the recent-events list.  Terminal events
    # don't carry started_at, so we need this to compute run duration.
    started_at_by_run: dict[str, datetime] = {}
    for evt in get_recent_events(user_id, limit=MAX_RECENT_EVENTS):
        if evt.started_at is not None and evt.run_id not in started_at_by_run:
            started_at_by_run[evt.run_id] = evt.started_at

    pipe = client.pipeline(transaction=False)
    for rid in run_ids:
        pipe.get(_run_key(rid))
    raw_events = pipe.execute()

    summaries: list[SyncRunSummary] = []
    for item in raw_events:
        if not item:
            continue
        with suppress(ValueError, TypeError):
            event = SyncStatusEvent.model_validate_json(item)
            summaries.append(
                SyncRunSummary(
                    run_id=event.run_id,
                    user_id=event.user_id,
                    provider=event.provider,
                    source=str(event.source),
                    stage=str(event.stage),
                    status=str(event.status),
                    message=event.message,
                    progress=event.progress,
                    items_processed=event.items_processed,
                    items_total=event.items_total,
                    error=event.error,
                    started_at=event.started_at or started_at_by_run.get(event.run_id),
                    ended_at=event.ended_at,
                    last_update=event.timestamp,
                )
            )

    summaries.sort(key=lambda s: s.last_update, reverse=True)
    return summaries[:limit]


def get_all_run_summaries(
    limit: int = 50,
    user_id_filter: str | UUID | None = None,
    provider_filter: str | None = None,
    status_filter: str | None = None,
    source_filter: str | None = None,
) -> list[SyncRunSummary]:
    """Aggregate run summaries across all users (for admin view).

    Uses SCAN to discover users with recent sync data, then merges their
    per-run summaries. Optional filters narrow results before sorting.
    """
    client = get_redis_client()

    if user_id_filter:
        user_ids = [str(user_id_filter)]
    else:
        pattern = "sync:status:user:*:runs"
        user_ids = []
        cursor: int = 0
        while True:
            cursor, keys = client.scan(cursor=cursor, match=pattern, count=200)
            for key in keys:
                k = key if isinstance(key, str) else key.decode("utf-8")
                parts = k.split(":")
                if len(parts) >= 4:
                    user_ids.append(parts[3])
            if cursor == 0:
                break

    all_summaries: list[SyncRunSummary] = []
    for uid in user_ids:
        all_summaries.extend(get_run_summaries(uid, limit=MAX_RECENT_EVENTS))

    if provider_filter:
        all_summaries = [s for s in all_summaries if s.provider == provider_filter]
    if status_filter:
        all_summaries = [s for s in all_summaries if s.status == status_filter]
    if source_filter:
        all_summaries = [s for s in all_summaries if s.source == source_filter]

    all_summaries.sort(key=lambda s: s.last_update, reverse=True)
    return all_summaries[:limit]


def stream_user_events(
    user_id: str | UUID,
    *,
    replay_last: int = 20,
    stop_event: threading.Event | None = None,
) -> Generator[str, None, None]:
    """Yield SSE-formatted strings for a user's status events.

    Subscribes to the per-user pub/sub channel **before** the replay so
    no events are dropped between the historical fetch and the live
    subscription. A heartbeat comment is sent every
    ``SSE_HEARTBEAT_SECONDS`` seconds so proxies don't close idle
    connections.
    """
    pubsub = get_redis_client().pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe(_user_channel(user_id))
    # Drain the SUBSCRIBE acknowledgement so the subscription is fully
    # registered with Redis before we yield control to the consumer. Without
    # this, a publish that occurs immediately after the consumer connects
    # could race the subscribe and be missed.
    with suppress(Exception):
        pubsub.get_message(ignore_subscribe_messages=False, timeout=1.0)

    yield format_comment("connected")

    if replay_last > 0:
        for event in reversed(get_recent_events(user_id, limit=replay_last)):
            yield format_event(event.model_dump_json(), event_type="sync.status")

    last_heartbeat = time.monotonic()
    try:
        while stop_event is None or not stop_event.is_set():
            message = pubsub.get_message(
                ignore_subscribe_messages=True,
                timeout=SSE_POLL_TIMEOUT_SECONDS,
            )
            if message and message.get("type") == "message":
                data = message.get("data")
                if isinstance(data, bytes):
                    data = data.decode("utf-8")
                if isinstance(data, str):
                    yield format_event(data, event_type="sync.status")
                    last_heartbeat = time.monotonic()
                    continue

            now = time.monotonic()
            if now - last_heartbeat >= SSE_HEARTBEAT_SECONDS:
                yield format_comment("heartbeat")
                last_heartbeat = now
    finally:
        with suppress(Exception):
            pubsub.unsubscribe(_user_channel(user_id))
            pubsub.close()


# ---------------------------------------------------------------------------
# Convenience helpers for common state transitions
# ---------------------------------------------------------------------------


def started(
    user_id: str | UUID,
    provider: str,
    source: SyncSource | str,
    *,
    run_id: str | None = None,
    message: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> SyncStatusEvent:
    """Emit a STARTED / IN_PROGRESS event."""
    return emit_event(
        user_id=user_id,
        provider=provider,
        source=source,
        stage=SyncStage.STARTED,
        status=SyncStatus.IN_PROGRESS,
        run_id=run_id,
        message=message,
        metadata=metadata,
        started_at=datetime.now(timezone.utc),
    )


def progress(
    user_id: str | UUID,
    provider: str,
    source: SyncSource | str,
    *,
    run_id: str,
    stage: SyncStage | str = SyncStage.PROCESSING,
    message: str | None = None,
    progress_value: float | None = None,
    items_processed: int | None = None,
    items_total: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> SyncStatusEvent:
    """Emit a progress update."""
    return emit_event(
        user_id=user_id,
        provider=provider,
        source=source,
        stage=stage,
        status=SyncStatus.IN_PROGRESS,
        run_id=run_id,
        message=message,
        progress=progress_value,
        items_processed=items_processed,
        items_total=items_total,
        metadata=metadata,
    )


def completed(
    user_id: str | UUID,
    provider: str,
    source: SyncSource | str,
    *,
    run_id: str,
    status: SyncStatus | str = SyncStatus.SUCCESS,
    message: str | None = None,
    items_processed: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> SyncStatusEvent:
    """Emit a COMPLETED terminal event."""
    return emit_event(
        user_id=user_id,
        provider=provider,
        source=source,
        stage=SyncStage.COMPLETED,
        status=status,
        run_id=run_id,
        message=message,
        items_processed=items_processed,
        progress=1.0,
        metadata=metadata,
        ended_at=datetime.now(timezone.utc),
    )


def failed(
    user_id: str | UUID,
    provider: str,
    source: SyncSource | str,
    *,
    run_id: str,
    error: str,
    message: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> SyncStatusEvent:
    """Emit a FAILED terminal event."""
    return emit_event(
        user_id=user_id,
        provider=provider,
        source=source,
        stage=SyncStage.FAILED,
        status=SyncStatus.FAILED,
        run_id=run_id,
        error=error,
        message=message,
        metadata=metadata,
        ended_at=datetime.now(timezone.utc),
    )


def cancelled(
    user_id: str | UUID,
    provider: str,
    source: SyncSource | str,
    *,
    run_id: str,
    message: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> SyncStatusEvent:
    """Emit a CANCELLED terminal event."""
    return emit_event(
        user_id=user_id,
        provider=provider,
        source=source,
        stage=SyncStage.CANCELLED,
        status=SyncStatus.CANCELLED,
        run_id=run_id,
        message=message,
        metadata=metadata,
        ended_at=datetime.now(timezone.utc),
    )
