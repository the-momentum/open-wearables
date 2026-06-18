"""Celery task for processing full-payload (webhook_stream) provider push events.

A single shared task handles all webhook_stream providers (Garmin, Suunto, …).
The provider-specific logic lives in each provider's WebhookHandler.process_payload;
this task is a thin async wrapper providing acks_late and retry guarantees.

Queue and retry policy are configured per-provider at the call site (send_task with queue= kwarg).
"""

from logging import getLogger
from typing import Any
from uuid import UUID

from celery import Task, shared_task
from fastapi import HTTPException

from app.database import SessionLocal
from app.schemas.sync_status import SyncStatus
from app.services import sync_status_service
from app.services.providers.factory import ProviderFactory
from app.utils.structured_logging import log_structured

logger = getLogger(__name__)

# Upstream 4xx where retrying can't recover the object. 401 (token refresh) and
# 429 (rate limit) are excluded — those still benefit from a retry.
_NONRETRIABLE_UPSTREAM_STATUSES = frozenset({400, 403, 404, 410, 422})

# Providers whose webhook deliveries are surfaced in the sync log via this task.
# Garmin self-reports sync status from its own handler/backfill, so it is excluded
# here to avoid duplicate run entries.
_SYNC_LOG_PROVIDERS = frozenset({"oura", "strava", "polar", "whoop", "suunto"})

# process_payload "status" values that mean data was actually persisted.
_SAVED_STATUSES = frozenset({"processed", "saved", "accepted", "deleted", "success"})


def _extract_item_count(result: dict[str, Any]) -> int | None:
    """Best-effort count of records persisted, across provider result shapes."""
    for key in ("records_saved", "saved_count", "items_processed", "processed_count", "record_count"):
        value = result.get(key)
        if isinstance(value, int):
            return value
    saved = result.get("saved")
    if isinstance(saved, int):
        return saved
    if isinstance(saved, dict):
        return sum(v for v in saved.values() if isinstance(v, int))
    return None


def _extract_breakdown(result: dict[str, Any], count: Any) -> dict[str, int] | None:
    """New-vs-updated split, derived from WriteCounts carried on the count or the saved dict."""
    inserted = getattr(count, "inserted", None)
    updated = getattr(count, "updated", None)
    if inserted is None and updated is None:
        saved = result.get("saved")
        if isinstance(saved, dict):
            members = [v for v in saved.values() if hasattr(v, "inserted")]
            if members:
                inserted = sum(v.inserted for v in members)
                updated = sum(v.updated for v in members)
    if inserted is None and updated is None:
        inserted = result.get("records_inserted")
        updated = result.get("records_updated")
    if inserted is None and updated is None:
        return None
    return {"inserted": inserted or 0, "updated": updated or 0}


def _emit_webhook_sync_status(provider_name: str, result: Any) -> None:
    """Record a webhook delivery in the sync log (best-effort, never raises).

    Saves and errors become full run entries; ignored / duplicate / no-op
    deliveries are recorded as SKIPPED so the UI can filter them out.
    Deliveries that never resolved to a user (invalid payload, user_not_found)
    are skipped entirely — there is no user to attribute the run to.
    """
    try:
        if provider_name not in _SYNC_LOG_PROVIDERS or not isinstance(result, dict):
            return

        raw_user_id = result.get("user_id")
        if not raw_user_id:
            return
        try:
            user_id = UUID(str(raw_user_id))
        except (ValueError, TypeError):
            return

        status_str = str(result.get("status") or "").lower()
        count = _extract_item_count(result)
        descriptor = result.get("data_type") or result.get("event_type") or ""

        breakdown = _extract_breakdown(result, count)

        if status_str == "error":
            sync_status_service.webhook_delivered(
                user_id,
                provider_name,
                status=SyncStatus.FAILED,
                error=str(result.get("error") or "unknown"),
                message=f"webhook {descriptor}".strip(),
            )
        elif status_str in _SAVED_STATUSES and (count or 0) > 0:
            # Prefer the new/updated split so an upsert-in-place reads as
            # "0 new, 3 updated" rather than looking like freshly arrived data.
            detail = f"{breakdown['inserted']} new, {breakdown['updated']} updated" if breakdown else descriptor
            sync_status_service.webhook_delivered(
                user_id,
                provider_name,
                status=SyncStatus.SUCCESS,
                items_processed=count,
                message=f"webhook {detail}".strip(),
                metadata=breakdown,
            )
        else:
            # processed-but-no-data, ignored, duplicate, unknown_event_type, …
            reason = result.get("reason") or (descriptor if status_str in _SAVED_STATUSES else status_str)
            sync_status_service.webhook_delivered(
                user_id,
                provider_name,
                status=SyncStatus.SKIPPED,
                items_processed=count,
                message=f"skipped: {reason}".strip(),
                metadata=breakdown,
            )
    except Exception as exc:  # pragma: no cover - sync log must never break processing
        logger.debug("Failed to emit webhook sync status: %s", exc, exc_info=True)


@shared_task(
    bind=True,
    acks_late=True,
    reject_on_worker_lost=True,
    max_retries=3,
    default_retry_delay=30,
)
def process_webhook_push(
    self: Task, provider_name: str, payload: dict[str, Any], request_trace_id: str
) -> dict[str, Any]:
    """Process a full-payload webhook push event for any webhook_stream provider.

    Uses ProviderFactory to resolve the provider's WebhookHandler, then calls
    process_payload() with a fresh DB session. Retries up to 3 times on
    unexpected infrastructure errors.
    """
    try:
        factory = ProviderFactory()
        strategy = factory.get_provider(provider_name)
        if strategy.webhooks is None:
            raise ValueError(f"Provider '{provider_name}' has no webhook handler")
        with SessionLocal() as db:
            result = strategy.webhooks.process_payload(db, payload, request_trace_id)
        _emit_webhook_sync_status(provider_name, result)
        return result
    except ValueError as exc:
        # Configuration error (unknown provider, missing handler) — retrying won't help.
        log_structured(
            logger,
            "error",
            "Webhook push task aborted — configuration error",
            provider=provider_name,
            trace_id=request_trace_id,
            error=str(exc),
        )
        raise
    except HTTPException as exc:
        # Non-retriable upstream 4xx (deleted/unqueryable object): ack so the task
        # drops instead of retrying forever. 5xx and 401/429 fall through to retry.
        if exc.status_code in _NONRETRIABLE_UPSTREAM_STATUSES:
            log_structured(
                logger,
                "warning",
                "Webhook push task skipped — upstream non-retriable response",
                provider=provider_name,
                trace_id=request_trace_id,
                upstream_status=exc.status_code,
                error=str(exc.detail),
            )
            return {
                "status": "skipped",
                "reason": "upstream_non_retriable",
                "upstream_status": exc.status_code,
            }
        log_structured(
            logger,
            "error",
            "Webhook push task failed, scheduling retry",
            provider=provider_name,
            trace_id=request_trace_id,
            upstream_status=exc.status_code,
            error=str(exc.detail),
            attempt=self.request.retries,
            max_retries=self.max_retries,
        )
        raise self.retry(exc=exc)
    except Exception as exc:
        log_structured(
            logger,
            "error",
            "Webhook push task failed, scheduling retry",
            provider=provider_name,
            trace_id=request_trace_id,
            error=str(exc),
            attempt=self.request.retries,
            max_retries=self.max_retries,
        )
        raise self.retry(exc=exc)
