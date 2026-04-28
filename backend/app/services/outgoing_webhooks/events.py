"""Convenience helpers for emitting outgoing webhook events.

Call these functions after data is committed to the database.
Each schedules a Celery task and returns immediately — Svix delivery
happens in the worker process.
"""

from __future__ import annotations

import logging
import re
from typing import Any
from uuid import UUID

from app.constants.webhooks.events import SERIES_TYPE_TO_GRANULAR_EVENT, SERIES_TYPE_TO_GROUP_EVENT
from app.schemas.webhooks.event_types import WebhookEventType

logger = logging.getLogger(__name__)

# Maximum number of samples included in a single Svix message.
# At ~200 bytes per serialised sample, 2 500 samples ≈ 500 KB — well within
# Svix's 1 MB payload limit.  Batches larger than this are split into
# consecutive chunk events, each carrying a ``chunk_index`` / ``total_chunks``
# envelope so consumers can reassemble if needed.
SVIX_MAX_SAMPLES_PER_EVENT = 2500

# Svix eventId must match [a-zA-Z0-9\-_.] — colons, plus-signs, and other
# characters in ISO 8601 timestamps are not allowed.
_SVIX_ID_SAFE = re.compile(r"[^a-zA-Z0-9\-_.]")


def _safe_key(raw: str) -> str:
    """Replace characters forbidden in a Svix eventId with underscores."""
    return _SVIX_ID_SAFE.sub("_", raw)


def _dispatch(
    event_type: str,
    payload: dict[str, Any],
    *,
    channels: list[str] | None = None,
    idempotency_key: str | None = None,
) -> None:
    """Schedule the Celery emit task.

    Import is deferred to avoid circular dependencies. Silently drops the
    event when the broker (Redis) is unreachable so that data ingestion is
    never blocked by webhook infrastructure.
    """
    try:
        from app.integrations.celery.tasks.emit_webhook_event_task import emit_webhook_event

        emit_webhook_event.delay(event_type, payload, channels=channels, idempotency_key=idempotency_key)
    except Exception:
        logger.warning("Could not enqueue webhook event %s", event_type, exc_info=True)


def on_workout_created(
    *,
    record_id: UUID,
    user_id: UUID,
    provider: str,
    device: str | None,
    workout_type: str | None,
    start_time: str,
    end_time: str,
    zone_offset: str | None,
    duration_seconds: float | None,
    calories_kcal: float | None = None,
    distance_meters: float | None = None,
    avg_heart_rate_bpm: int | None = None,
    max_heart_rate_bpm: int | None = None,
    elevation_gain_meters: float | None = None,
    avg_pace_sec_per_km: int | None = None,
) -> None:
    _dispatch(
        WebhookEventType.WORKOUT_CREATED,
        {
            "type": WebhookEventType.WORKOUT_CREATED,
            "data": {
                "id": str(record_id),
                "user_id": str(user_id),
                "type": workout_type,
                "start_time": start_time,
                "end_time": end_time,
                "zone_offset": zone_offset,
                "duration_seconds": duration_seconds,
                "source": {"provider": provider, "device": device},
                "calories_kcal": calories_kcal,
                "distance_meters": distance_meters,
                "avg_heart_rate_bpm": avg_heart_rate_bpm,
                "max_heart_rate_bpm": max_heart_rate_bpm,
                "avg_pace_sec_per_km": avg_pace_sec_per_km,
                "elevation_gain_meters": elevation_gain_meters,
            },
        },
        idempotency_key=f"workout.created.{record_id}",
        channels=[f"user.{user_id}"],
    )


def on_sleep_created(
    *,
    record_id: UUID,
    user_id: UUID,
    provider: str,
    device: str | None,
    start_time: str,
    end_time: str,
    zone_offset: str | None,
    duration_seconds: float | None,
    efficiency_percent: float | None = None,
    stages: dict[str, int | None] | None = None,
    is_nap: bool | None = None,
) -> None:
    _dispatch(
        WebhookEventType.SLEEP_CREATED,
        {
            "type": WebhookEventType.SLEEP_CREATED,
            "data": {
                "id": str(record_id),
                "user_id": str(user_id),
                "start_time": start_time,
                "end_time": end_time,
                "zone_offset": zone_offset,
                "duration_seconds": duration_seconds,
                "source": {"provider": provider, "device": device},
                "efficiency_percent": efficiency_percent,
                "stages": stages,
                "is_nap": is_nap,
            },
        },
        idempotency_key=f"sleep.created.{record_id}",
        channels=[f"user.{user_id}"],
    )


def on_timeseries_batch_saved(
    *,
    user_id: UUID,
    provider: str,
    series_type: str,
    sample_count: int,
    start_time: str | None = None,
    end_time: str | None = None,
    samples: list[dict[str, Any]] | None = None,
) -> None:
    """Emit one webhook event per data-type per ingestion batch.

    Each event carries the full ``samples`` array so consumers can operate in
    a webhook-first architecture without issuing follow-up API calls.

    When ``samples`` exceeds ``SVIX_MAX_SAMPLES_PER_EVENT`` the batch is split
    into multiple consecutive chunk events.  Every chunk includes
    ``chunk_index`` (0-based) and ``total_chunks`` so consumers can detect and
    reassemble split deliveries.  Single-chunk payloads omit these fields to
    keep the common case clean.

    Two events are emitted per batch:
    - a *group* event (e.g. ``heart_rate.created``) for broad subscriptions
    - a *granular* event (e.g. ``series.resting_heart_rate.created``) for
      narrow subscriptions to a specific metric
    """
    group_event = SERIES_TYPE_TO_GROUP_EVENT.get(series_type)
    if group_event is None:
        return
    granular_event = SERIES_TYPE_TO_GRANULAR_EVENT.get(series_type)
    if granular_event and granular_event != group_event:
        event_types_to_emit = [group_event, granular_event]
    else:
        event_types_to_emit = [group_event]
    samples = samples or []

    def _emit(event_type: str, payload_data: dict[str, Any], ikey: str) -> None:
        _dispatch(
            event_type,
            {"type": event_type, "data": payload_data},
            idempotency_key=_safe_key(f"{ikey}.{event_type}"),
            channels=[f"user.{user_id}"],
        )

    if len(samples) <= SVIX_MAX_SAMPLES_PER_EVENT:
        base_key = f"timeseries.{user_id}.{provider}.{series_type}.{start_time or ''}.{end_time or ''}"
        data: dict[str, Any] = {
            "user_id": str(user_id),
            "provider": provider,
            "series_type": series_type,
            "sample_count": sample_count,
            "start_time": start_time,
            "end_time": end_time,
            "samples": samples,
        }
        for event_type in event_types_to_emit:
            _emit(event_type, data, base_key)
    else:
        chunks = [
            samples[i : i + SVIX_MAX_SAMPLES_PER_EVENT] for i in range(0, len(samples), SVIX_MAX_SAMPLES_PER_EVENT)
        ]
        total_chunks = len(chunks)
        for chunk_index, chunk in enumerate(chunks):
            chunk_start = chunk[0]["timestamp"] if chunk else start_time
            chunk_end = chunk[-1]["timestamp"] if chunk else end_time
            base_key = (
                f"timeseries.{user_id}.{provider}.{series_type}.{start_time or ''}.{end_time or ''}.chunk{chunk_index}"
            )
            data = {
                "user_id": str(user_id),
                "provider": provider,
                "series_type": series_type,
                "sample_count": sample_count,
                "start_time": chunk_start,
                "end_time": chunk_end,
                "samples": chunk,
                "chunk_index": chunk_index,
                "total_chunks": total_chunks,
            }
            for event_type in event_types_to_emit:
                _emit(event_type, data, base_key)


def on_connection_created(
    *,
    user_id: UUID,
    provider: str,
    connection_id: UUID,
    connected_at: str,
) -> None:
    _dispatch(
        WebhookEventType.CONNECTION_CREATED,
        {
            "type": WebhookEventType.CONNECTION_CREATED,
            "data": {
                "user_id": str(user_id),
                "provider": provider,
                "connection_id": str(connection_id),
                "connected_at": connected_at,
            },
        },
        idempotency_key=f"connection.created.{user_id}.{provider}",
        channels=[f"user.{user_id}"],
    )


def on_sync_started(
    *,
    user_id: UUID,
    provider: str,
    source: str,
    run_id: str,
    message: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    _dispatch(
        WebhookEventType.SYNC_STARTED,
        {
            "type": WebhookEventType.SYNC_STARTED,
            "data": {
                "user_id": str(user_id),
                "provider": provider,
                "source": source,
                "run_id": run_id,
                "message": message,
                "metadata": metadata or {},
            },
        },
        idempotency_key=f"sync.started.{run_id}",
        channels=[f"user.{user_id}"],
    )


def on_sync_completed(
    *,
    user_id: UUID,
    provider: str,
    source: str,
    run_id: str,
    status: str,
    message: str | None = None,
    items_processed: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    _dispatch(
        WebhookEventType.SYNC_COMPLETED,
        {
            "type": WebhookEventType.SYNC_COMPLETED,
            "data": {
                "user_id": str(user_id),
                "provider": provider,
                "source": source,
                "run_id": run_id,
                "status": status,
                "message": message,
                "items_processed": items_processed,
                "metadata": metadata or {},
            },
        },
        idempotency_key=f"sync.completed.{run_id}",
        channels=[f"user.{user_id}"],
    )


def on_sync_failed(
    *,
    user_id: UUID,
    provider: str,
    source: str,
    run_id: str,
    error: str,
    message: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    _dispatch(
        WebhookEventType.SYNC_FAILED,
        {
            "type": WebhookEventType.SYNC_FAILED,
            "data": {
                "user_id": str(user_id),
                "provider": provider,
                "source": source,
                "run_id": run_id,
                "error": error,
                "message": message,
                "metadata": metadata or {},
            },
        },
        idempotency_key=f"sync.failed.{run_id}",
        channels=[f"user.{user_id}"],
    )
