"""Convenience helpers for emitting outgoing webhook events.

Call these functions after data is committed to the database.
Each schedules a Celery task and returns immediately — Svix delivery
happens in the worker process.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from app.constants.webhook_events import SERIES_TYPE_TO_WEBHOOK_EVENT
from app.schemas.webhooks.event_types import WebhookEventType

logger = logging.getLogger(__name__)


def _dispatch(event_type: str, payload: dict[str, Any], *, idempotency_key: str | None = None) -> None:
    """Schedule the Celery emit task.

    Import is deferred to avoid circular dependencies. Silently drops the
    event when the broker (Redis) is unreachable so that data ingestion is
    never blocked by webhook infrastructure.
    """
    try:
        from app.integrations.celery.tasks.emit_webhook_event_task import emit_webhook_event

        emit_webhook_event.delay(event_type, payload, idempotency_key=idempotency_key)
    except Exception:
        logger.debug("Could not enqueue webhook event %s (broker unavailable?)", event_type)


def on_workout_created(
    *,
    record_id: UUID,
    user_id: UUID,
    provider: str,
    workout_type: str | None,
    start_datetime: str,
    end_datetime: str,
    duration_seconds: float | None,
) -> None:
    _dispatch(
        WebhookEventType.WORKOUT_CREATED,
        {
            "type": WebhookEventType.WORKOUT_CREATED,
            "data": {
                "record_id": str(record_id),
                "user_id": str(user_id),
                "provider": provider,
                "workout_type": workout_type,
                "start_datetime": start_datetime,
                "end_datetime": end_datetime,
                "duration_seconds": duration_seconds,
            },
        },
        idempotency_key=f"workout.created.{record_id}",
    )


def on_sleep_created(
    *,
    record_id: UUID,
    user_id: UUID,
    provider: str,
    start_datetime: str,
    end_datetime: str,
    duration_seconds: float | None,
) -> None:
    _dispatch(
        WebhookEventType.SLEEP_CREATED,
        {
            "type": WebhookEventType.SLEEP_CREATED,
            "data": {
                "record_id": str(record_id),
                "user_id": str(user_id),
                "provider": provider,
                "start_datetime": start_datetime,
                "end_datetime": end_datetime,
                "duration_seconds": duration_seconds,
            },
        },
        idempotency_key=f"sleep.created.{record_id}",
    )


def on_activity_created(
    *,
    record_id: UUID,
    user_id: UUID,
    provider: str,
    activity_type: str | None,
    start_datetime: str,
    end_datetime: str,
) -> None:
    _dispatch(
        WebhookEventType.ACTIVITY_CREATED,
        {
            "type": WebhookEventType.ACTIVITY_CREATED,
            "data": {
                "record_id": str(record_id),
                "user_id": str(user_id),
                "provider": provider,
                "activity_type": activity_type,
                "start_datetime": start_datetime,
                "end_datetime": end_datetime,
            },
        },
        idempotency_key=f"activity.created.{record_id}",
    )


def on_timeseries_batch_saved(
    *,
    user_id: UUID,
    provider: str,
    series_type: str,
    sample_count: int,
    start_datetime: str | None = None,
    end_datetime: str | None = None,
) -> None:
    """Emit one webhook event per data-type per ingestion batch."""
    event_type = SERIES_TYPE_TO_WEBHOOK_EVENT.get(series_type, WebhookEventType.TIMESERIES_UPDATED)
    _dispatch(
        event_type,
        {
            "type": event_type,
            "data": {
                "user_id": str(user_id),
                "provider": provider,
                "series_type": series_type,
                "sample_count": sample_count,
                "start_datetime": start_datetime,
                "end_datetime": end_datetime,
            },
        },
    )
