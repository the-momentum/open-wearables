"""Garmin webhook endpoints for receiving push/ping notifications.
Processing can take longer than Garmin's 30-second webhook timeout, so
the endpoints immediately return 200 and offloads all work to celery tasks.

Garmin sends data via two webhook types:
- PING: Contains callbackURLs with temporary tokens to fetch data
- PUSH: Contains inline data (activity metadata, wellness summaries)

When multiple backfill requests happen within 5 minutes, Garmin may batch
the webhook responses into a single payload containing data for multiple types.
All 16 data types are handled in both PING and PUSH handlers.
"""

from logging import getLogger
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException

from app.integrations.celery.tasks import (
    process_garmin_ping,
    process_garmin_push,
)
from app.services.raw_payload_storage import store_raw_payload
from app.utils.structured_logging import log_structured

router = APIRouter()
logger = getLogger(__name__)


@router.post("/ping")
def garmin_ping_notification(
    payload: dict,
    garmin_client_id: Annotated[str | None, Header(alias="garmin-client-id")] = None,
) -> dict:
    """
    Receive Garmin PING notifications.

    Garmin sends ping notifications when new data is available.
    The notification contains a callbackURL to fetch the actual data.
    Processing is offloaded to a Celery background task so that Garmin's 30-second
    webhook timeout is never exceeded. The endpoint returns 200 immediately.

    When multiple backfill requests happen within 5 minutes, Garmin may batch
    the responses - a single payload can contain data for multiple types.

    Expected format:
    {
        "activities": [{
            "userId": "garmin_user_id",
            "callbackURL": "https://apis.garmin.com/wellness-api/rest/activities?...&token=XXXXX"
        }],
        "activityDetails": [...],
        "dailies": [...],
        ...
    }
    """
    # Verify request is from Garmin
    if not garmin_client_id:
        log_structured(logger, "warn", "Received webhook without garmin-client-id header", provider="garmin")
        raise HTTPException(status_code=401, detail="Missing garmin-client-id header")

    try:
        request_trace_id = str(uuid4())[:8]
        item_counts = {k: len(v) if isinstance(v, list) else 1 for k, v in payload.items()}

        task = process_garmin_ping.delay(payload, request_trace_id)
        task_id = getattr(task, "id", None)
        log_structured(
            logger,
            "info",
            "Enqueued Garmin ping processing task",
            provider="garmin",
            trace_id=request_trace_id,
            item_counts=item_counts,
            task_id=str(task_id) if task_id else None,
        )

        return {"status": "accepted"}

    except Exception as e:
        log_structured(logger, "error", "Error processing Garmin ping webhook", provider="garmin", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to process webhook")


@router.post("/push")
def garmin_push_notification(
    payload: dict,
    garmin_client_id: Annotated[str | None, Header(alias="garmin-client-id")] = None,
) -> dict:
    """
    Receive Garmin PUSH notifications.

    Push notifications contain inline data (activity metadata, wellness summaries).
    Processing is offloaded to a Celery background task so that Garmin's 30-second
    webhook timeout is never exceeded. The endpoint returns 200 immediately.

    When multiple backfill requests happen within 5 minutes, Garmin may batch
    the responses into a single payload containing data for multiple types.

    All 16 data types are processed:
    - activities: Saved as EventRecords via GarminWorkouts
    - sleeps, dailies, epochs, bodyComps, hrv: Core wellness data
    - stressDetails, respiration, pulseOx, bloodPressures: Vitals
    - userMetrics, skinTemp, healthSnapshot, moveiq, mct, activityDetails: Extended data

    Expected format:
    {
        "activities": [{
            "userId": "garmin_user_id",
            "summaryId": "21047282990",
            "activityId": 21047282990,
            "activityName": "Morning Run",
            "startTimeInSeconds": 1763597760,
            "startTimeOffsetInSeconds": 3600,
            "activityType": "RUNNING",
            "deviceName": "Forerunner 965",
            "manual": false,
            "isWebUpload": false
        }],
        "sleeps": [...],
        "dailies": [...],
        ...
    }
    """
    # Verify request is from Garmin
    if not garmin_client_id:
        log_structured(logger, "warn", "Received webhook without garmin-client-id header", provider="garmin")
        raise HTTPException(status_code=401, detail="Missing garmin-client-id header")

    try:
        request_trace_id = str(uuid4())[:8]
        item_counts = {k: len(v) if isinstance(v, list) else 1 for k, v in payload.items()}
        garmin_user_ids = list(
            {
                item.get("userId")
                for items in payload.values()
                if isinstance(items, list)
                for item in items
                if item.get("userId")
            }
        )

        store_raw_payload(
            source="webhook",
            provider="garmin",
            payload=payload,
            trace_id=request_trace_id,
        )

        task = process_garmin_push.delay(payload, request_trace_id)
        task_id = getattr(task, "id", None)

        log_structured(
            logger,
            "info",
            "Enqueued Garmin push processing task",
            provider="garmin",
            trace_id=request_trace_id,
            item_counts=item_counts,
            garmin_user_ids=garmin_user_ids,
            task_id=str(task_id) if task_id else None,
        )

        return {"status": "accepted"}

    except Exception as e:
        log_structured(logger, "error", "Error processing Garmin push webhook", provider="garmin", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to process webhook")


@router.get("/health")
def garmin_webhook_health() -> dict:
    """Health check endpoint for Garmin webhook configuration."""
    return {"status": "ok", "service": "garmin-webhooks"}
