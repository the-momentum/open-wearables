"""Convenience helpers for emitting outgoing webhook events.

Call these functions after data is committed to the database.
Each schedules a Celery task and returns immediately — Svix delivery
happens in the worker process.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from app.constants.webhooks.events import SERIES_TYPE_TO_WEBHOOK_EVENT
from app.schemas.webhooks.event_types import WebhookEventType

logger = logging.getLogger(__name__)


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


def on_activity_created(
    *,
    record_id: UUID,
    user_id: UUID,
    provider: str,
    device: str | None,
    activity_type: str | None,
    start_time: str,
    end_time: str,
    zone_offset: str | None,
    duration_seconds: float | None,
) -> None:
    _dispatch(
        WebhookEventType.ACTIVITY_CREATED,
        {
            "type": WebhookEventType.ACTIVITY_CREATED,
            "data": {
                "id": str(record_id),
                "user_id": str(user_id),
                "type": activity_type,
                "start_time": start_time,
                "end_time": end_time,
                "zone_offset": zone_offset,
                "duration_seconds": duration_seconds,
                "source": {"provider": provider, "device": device},
            },
        },
        idempotency_key=f"activity.created.{record_id}",
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
) -> None:
    """Emit one webhook event per data-type per ingestion batch."""
    event_type = SERIES_TYPE_TO_WEBHOOK_EVENT.get(series_type, WebhookEventType.TIMESERIES_CREATED)
    idempotency_key = f"timeseries.{user_id}.{provider}.{series_type}.{start_time or ''}.{end_time or ''}"
    _dispatch(
        event_type,
        {
            "type": event_type,
            "data": {
                "user_id": str(user_id),
                "provider": provider,
                "series_type": series_type,
                "sample_count": sample_count,
                "start_time": start_time,
                "end_time": end_time,
            },
        },
        idempotency_key=idempotency_key,
        channels=[f"user.{user_id}"],
    )


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
