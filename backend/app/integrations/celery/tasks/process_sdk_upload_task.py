import json
import uuid
from logging import getLogger
from typing import Any
from uuid import UUID

from celery import shared_task

from app.config import settings
from app.database import SessionLocal
from app.models import User
from app.repositories.user_repository import UserRepository
from app.schemas.sync_status import SyncSource, SyncStatus
from app.services.apple.healthkit.import_service import (
    ImportService as SDKImportService,
)
from app.services.apple.healthkit.import_service import (
    import_service as sdk_import_service,
)
from app.services.apple.healthkit.sleep_service import finalize_pending_sleep
from app.services.raw_payload_storage import delete_payload_from_s3, get_payload_from_s3
from app.services.sdk_ingestion_context import sdk_ingestion_context
from app.services.sdk_sync_run_service import sdk_sync_run_service
from app.services.sync_status_service import completed, failed, started
from app.services.user_connection_service import user_connection_service
from app.utils.structured_logging import log_structured

logger = getLogger(__name__)


def _submitted_item_count(content: str) -> int:
    try:
        body = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return 0
    data = body.get("data") if isinstance(body, dict) else None
    if not isinstance(data, dict):
        return 0
    return sum(len(value) for key in ("records", "workouts", "sleep") if isinstance((value := data.get(key)), list))


def _get_import_service(provider: str) -> SDKImportService:
    if provider in ("apple", "samsung", "google"):
        return sdk_import_service
    raise ValueError(f"Unsupported provider: {provider}")


@shared_task(
    queue="sdk_sync",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=8,
)
def process_sdk_upload(
    content: str | None,
    content_type: str,
    user_id: str,
    provider: str,
    batch_id: str | None = None,
    payload_ref: str | None = None,
    client_sync_id: str | None = None,
    client_sync_chunk_index: int | None = None,
    client_sync_final: bool | None = None,
    client_sync_total_items: int | None = None,
) -> dict[str, Any]:
    """
    Process SDK data import asynchronously.

    Args:
        content: The request content as string (JSON or multipart data). None when the
            payload was offloaded to S3 - see ``payload_ref``.
        content_type: The content type header value
        user_id: User ID to associate with the data
        provider: Import provider - "apple", "samsung", "google"
        batch_id: Unique batch identifier for tracking (optional for backwards compatibility)
        payload_ref: ``s3://bucket/key`` of the stored payload. When set (and ``content`` is
            None) the body is loaded from S3 here, so it never travels through the broker.

    Returns:
        Dictionary with status_code and response message
    """
    # Generate batch_id if not provided (backwards compatibility)
    if not batch_id:
        batch_id = str(uuid.uuid4())

    # Payload was offloaded to S3, so the body never travelled through the broker. A read
    # failure propagates: boto3 has already retried the transient cases, and CeleryIntegration
    # reports the exception to Sentry.
    if content is None and payload_ref:
        try:
            content = get_payload_from_s3(payload_ref)
        except Exception:
            log_structured(
                logger,
                "error",
                "Failed to load SDK payload from S3",
                provider=provider,
                action="load_payload_ref",
                batch_id=batch_id,
                user_id=user_id,
                payload_ref=payload_ref,
            )
            raise

    if content is None:
        log_structured(
            logger,
            "warning",
            "No payload content or reference provided",
            provider=provider,
            action="validate_payload_present",
            batch_id=batch_id,
            user_id=user_id,
        )
        return {"status": "error", "reason": "missing_payload", "batch_id": batch_id}

    # Validate user_id format
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        log_structured(
            logger,
            "warning",
            "Invalid user_id format",
            provider=provider,
            action="validate_user_id",
            batch_id=batch_id,
            user_id=user_id,
        )
        return {"status": "error", "reason": "invalid_user_id", "batch_id": batch_id}

    # Validate user exists before processing
    with SessionLocal() as db:
        user_repo = UserRepository(User)
        if not user_repo.get(db, user_uuid):
            log_structured(
                logger,
                "warning",
                "Skipping import for non-existent user",
                provider=provider,
                action="validate_user_exists",
                batch_id=batch_id,
                user_id=user_id,
            )
            return {"status": "skipped", "reason": "user_not_found", "batch_id": batch_id}

    # Log task start
    log_structured(
        logger,
        "info",
        f"{provider.capitalize()} sync batch processing started",
        action=f"{provider}_batch_processing_start",
        batch_id=batch_id,
        user_id=user_id,
        provider=provider,
    )

    sdk_manifest = None
    if client_sync_id is not None:
        sdk_manifest = {
            "client_sync_id": client_sync_id,
            "batch_id": batch_id,
            "chunk_index": client_sync_chunk_index,
            "is_final": client_sync_final,
            "declared_total_items": client_sync_total_items,
        }
        with SessionLocal() as db:
            run, should_emit_started = sdk_sync_run_service.mark_started(db, batch_id=batch_id)
        if should_emit_started:
            started(
                user_uuid,
                provider,
                SyncSource.SDK,
                run_id=client_sync_id,
                message=f"Processing {provider} SDK sync",
                metadata={
                    "client_sync_id": client_sync_id,
                    "received_chunks": run.received_chunks,
                    "received_items": run.received_items,
                },
            )
    else:
        started(
            user_uuid,
            provider,
            SyncSource.SDK,
            run_id=batch_id,
            message=f"Processing {provider} SDK batch",
            metadata={"batch_id": batch_id},
        )

    with SessionLocal() as db:
        # Ensure SDK connection exists for this user (SDK-based, no OAuth tokens).
        # Goes through the service so a new/reactivated connection emits connection.created.
        user_connection_service.ensure_sdk_connection(db, user_uuid, provider)

        # Select the appropriate import service based on source
        import_service = _get_import_service(provider)

        with sdk_ingestion_context(sdk_manifest):
            result = import_service.import_data_from_request(
                db, content, content_type, user_id, batch_id=batch_id
            ).model_dump()

        # Log processing completion with results
        log_structured(
            logger,
            "info",
            f"{provider.capitalize()} sync batch processing completed",
            action=f"{provider}_batch_processing_complete",
            batch_id=batch_id,
            user_id=user_id,
            provider=provider,
            status_code=result.get("status_code"),
            response=result.get("response"),
            # Include counts from result if available
            records_saved=result.get("records_saved", 0),
            workouts_saved=result.get("workouts_saved", 0),
            sleep_saved=result.get("sleep_saved", 0),
        )

        status_code = result.get("status_code", 200)
        records_saved = int(result.get("records_saved", 0) or 0)
        records_inserted = int(result.get("records_inserted", 0) or 0)
        records_updated = int(result.get("records_updated", 0) or 0)
        workouts_saved = int(result.get("workouts_saved", 0) or 0)
        sleep_saved = int(result.get("sleep_saved", 0) or 0)
        dropped_count = int(result.get("dropped_count", 0) or 0)
        types = result.get("types") or []
        items_total = records_saved + workouts_saved + sleep_saved
        submitted_items = _submitted_item_count(content)

        if isinstance(status_code, int) and 200 <= status_code < 300:
            # Same wording as webhook_push_task; records_saved counts samples submitted.
            message = f"{provider.capitalize()} batch saved: {records_inserted} new, {records_updated} updated"
            if dropped_count:
                message += f" ({dropped_count} record(s) dropped by validation)"
            if client_sync_id is not None:
                with SessionLocal() as manifest_db:
                    run, is_terminal, count_mismatch = sdk_sync_run_service.mark_processed(
                        manifest_db,
                        batch_id=batch_id,
                        processed_items=max(0, submitted_items - dropped_count),
                    )
                if is_terminal and count_mismatch:
                    failed(
                        user_uuid,
                        provider,
                        SyncSource.SDK,
                        run_id=client_sync_id,
                        error="whole-sync item count mismatch",
                        message=f"{provider.capitalize()} SDK sync count mismatch",
                        metadata={
                            "client_sync_id": client_sync_id,
                            "expected_chunks": run.expected_chunks,
                            "received_chunks": run.received_chunks,
                            "processed_chunks": run.processed_chunks,
                            "declared_total_items": run.declared_total_items,
                            "received_items": run.received_items,
                            "processed_items": run.processed_items,
                        },
                    )
                elif is_terminal:
                    try:
                        if provider == "apple" and run.received_sleep_items > 0:
                            with sdk_ingestion_context(sdk_manifest):
                                finalize_pending_sleep(db, user_id)
                    except Exception as exc:
                        with SessionLocal() as manifest_db:
                            run, should_emit_failed = sdk_sync_run_service.mark_failed(
                                manifest_db,
                                batch_id=batch_id,
                            )
                        if should_emit_failed:
                            failed(
                                user_uuid,
                                provider,
                                SyncSource.SDK,
                                run_id=client_sync_id,
                                error=str(exc),
                                message=f"{provider.capitalize()} SDK sleep finalization failed",
                                metadata={
                                    "client_sync_id": client_sync_id,
                                    "received_sleep_items": run.received_sleep_items,
                                },
                            )
                    else:
                        completed(
                            user_uuid,
                            provider,
                            SyncSource.SDK,
                            run_id=client_sync_id,
                            status=SyncStatus.SUCCESS,
                            message=f"{provider.capitalize()} whole SDK sync completed",
                            items_processed=run.processed_items,
                            metadata={
                                "client_sync_id": client_sync_id,
                                "expected_chunks": run.expected_chunks,
                                "received_chunks": run.received_chunks,
                                "processed_chunks": run.processed_chunks,
                                "declared_total_items": run.declared_total_items,
                                "received_items": run.received_items,
                                "processed_items": run.processed_items,
                                "received_sleep_items": run.received_sleep_items,
                            },
                        )
            else:
                completed(
                    user_uuid,
                    provider,
                    SyncSource.SDK,
                    run_id=batch_id,
                    status=SyncStatus.SUCCESS,
                    message=message,
                    items_processed=items_total,
                    metadata={
                        "batch_id": batch_id,
                        "records_saved": records_saved,
                        "inserted": records_inserted,
                        "updated": records_updated,
                        "workouts_saved": workouts_saved,
                        "sleep_saved": sleep_saved,
                        "types": types,
                        "dropped_count": dropped_count,
                    },
                )
            if payload_ref and settings.raw_payload_storage == "disabled":
                # Transport-only copy and the data is committed, so drop it. A failed batch
                # keeps its payload for diagnosis.
                delete_payload_from_s3(payload_ref)
        else:
            terminal_run_id = batch_id
            should_emit_failed = True
            failure_metadata = {"batch_id": batch_id, "status_code": status_code}
            if client_sync_id is not None:
                terminal_run_id = client_sync_id
                with SessionLocal() as manifest_db:
                    run, should_emit_failed = sdk_sync_run_service.mark_failed(
                        manifest_db,
                        batch_id=batch_id,
                    )
                failure_metadata = {
                    **failure_metadata,
                    "client_sync_id": client_sync_id,
                    "received_chunks": run.received_chunks,
                    "processed_chunks": run.processed_chunks,
                }
            if should_emit_failed:
                failed(
                    user_uuid,
                    provider,
                    SyncSource.SDK,
                    run_id=terminal_run_id,
                    error=str(result.get("response", "Unknown error")),
                    message=f"{provider.capitalize()} batch failed",
                    metadata=failure_metadata,
                )

        return {**result, "batch_id": batch_id, "client_sync_id": client_sync_id}
