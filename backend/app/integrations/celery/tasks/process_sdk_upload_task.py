import uuid
from logging import getLogger
from typing import Any
from uuid import UUID

from celery import shared_task

from app.config import settings
from app.database import SessionLocal
from app.models import User
from app.repositories.user_connection_repository import UserConnectionRepository
from app.repositories.user_repository import UserRepository
from app.schemas.sync_status import (
    DataTypeKind,
    DataTypeOutcome,
    SyncScope,
    SyncSource,
    SyncStatus,
)
from app.services.apple.healthkit.import_service import (
    ImportService as SDKImportService,
)
from app.services.apple.healthkit.import_service import (
    import_service as sdk_import_service,
)
from app.services.raw_payload_storage import delete_payload_from_s3, get_payload_from_s3
from app.services.sync_status_service import (
    emit_sync_completed,
    emit_sync_failed,
    emit_sync_started,
    try_record_data_types,
)
from app.utils.structured_logging import log_structured

logger = getLogger(__name__)


def _get_import_service(provider: str) -> SDKImportService:
    if provider in ("apple", "samsung", "google"):
        return sdk_import_service
    raise ValueError(f"Unsupported provider: {provider}")


def _batch_outcomes(types: list[str], workouts_saved: int, sleep_saved: int) -> list[DataTypeOutcome]:
    """What this batch wrote, per data type.

    types holds series type slugs only, since the importer collects it from the samples it
    writes. Workouts and sleep are event records counted separately, so they would go
    unrecorded without their own entries.
    """
    outcomes = [
        DataTypeOutcome(data_type=data_type, kind=DataTypeKind.SERIES, status=SyncStatus.SUCCESS) for data_type in types
    ]
    for name, saved in (("workouts", workouts_saved), ("sleep", sleep_saved)):
        if saved:
            outcomes.append(
                DataTypeOutcome(
                    data_type=name,
                    kind=DataTypeKind.EVENT,
                    status=SyncStatus.SUCCESS,
                    items_inserted=saved,
                )
            )
    return outcomes


@shared_task(queue="sdk_sync")
def process_sdk_upload(
    content: str | None,
    content_type: str,
    user_id: str,
    provider: str,
    batch_id: str | None = None,
    payload_ref: str | None = None,
    sync_session_id: str | None = None,
    sync_type: str | None = None,
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
        sync_session_id: Device-generated id shared by every batch of one historical
            export. Absent on SDK versions that do not send it yet.
        sync_type: Whether this batch belongs to a historical export or to live sync.

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

    # A historical export spans many batches, so its run is keyed by the device's session
    # id. Without one the batch is its own run, which is why live syncs are not persisted.
    scope = SyncScope.HISTORICAL if sync_type == SyncScope.HISTORICAL and sync_session_id else SyncScope.LIVE
    run_id = f"sdk_{sync_session_id}" if scope == SyncScope.HISTORICAL else batch_id

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

    emit_sync_started(
        user_uuid,
        provider,
        SyncSource.SDK,
        scope=scope,
        run_id=run_id,
        message=f"Processing {provider} SDK batch",
        metadata={"batch_id": batch_id},
    )

    with SessionLocal() as db:
        # Ensure SDK connection exists for this user (SDK-based, no OAuth tokens)
        connection_repo = UserConnectionRepository()
        connection_repo.ensure_sdk_connection(db, user_uuid, provider)

        # Select the appropriate import service based on source
        import_service = _get_import_service(provider)

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
        workouts_saved = int(result.get("workouts_saved", 0) or 0)
        sleep_saved = int(result.get("sleep_saved", 0) or 0)
        dropped_count = int(result.get("dropped_count", 0) or 0)
        types = result.get("types") or []
        items_total = records_saved + workouts_saved + sleep_saved

        if isinstance(status_code, int) and 200 <= status_code < 300:
            message = f"{provider.capitalize()} batch saved"
            if dropped_count:
                message += f" ({dropped_count} record(s) dropped by validation)"
            emit_sync_completed(
                user_uuid,
                provider,
                SyncSource.SDK,
                scope=scope,
                run_id=run_id,
                status=SyncStatus.SUCCESS,
                message=message,
                items_processed=items_total,
                metadata={
                    "batch_id": batch_id,
                    "inserted": items_total,
                    "records_saved": records_saved,
                    "workouts_saved": workouts_saved,
                    "sleep_saved": sleep_saved,
                    "types": types,
                    "dropped_count": dropped_count,
                },
            )
            try_record_data_types(run_id, _batch_outcomes(types, workouts_saved, sleep_saved), scope=scope)
            if payload_ref and settings.raw_payload_storage == "disabled":
                # Transport-only copy and the data is committed, so drop it. A failed batch
                # keeps its payload for diagnosis.
                delete_payload_from_s3(payload_ref)
        else:
            emit_sync_failed(
                user_uuid,
                provider,
                SyncSource.SDK,
                scope=scope,
                run_id=run_id,
                error=str(result.get("response", "Unknown error")),
                message=f"{provider.capitalize()} batch failed",
                metadata={"batch_id": batch_id, "status_code": status_code},
            )

        return {**result, "batch_id": batch_id}
