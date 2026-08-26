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
from app.schemas.sync_status import SyncSource, SyncStatus
from app.services.apple.healthkit.import_service import (
    ImportService as SDKImportService,
)
from app.services.apple.healthkit.import_service import (
    import_service as sdk_import_service,
)
from app.services.raw_payload_storage import delete_payload_from_s3, get_payload_from_s3
from app.services.sync_status_service import completed, failed, started
from app.utils.structured_logging import log_structured

logger = getLogger(__name__)


def _get_import_service(provider: str) -> SDKImportService:
    if provider in ("apple", "samsung", "google"):
        return sdk_import_service
    raise ValueError(f"Unsupported provider: {provider}")


@shared_task(queue="sdk_sync")
def process_sdk_upload(
    content: str | None,
    content_type: str,
    user_id: str,
    provider: str,
    batch_id: str | None = None,
    payload_ref: str | None = None,
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

    started(
        user_uuid,
        provider,
        SyncSource.SDK,
        run_id=batch_id,
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
            failed(
                user_uuid,
                provider,
                SyncSource.SDK,
                run_id=batch_id,
                error=str(result.get("response", "Unknown error")),
                message=f"{provider.capitalize()} batch failed",
                metadata={"batch_id": batch_id, "status_code": status_code},
            )

        return {**result, "batch_id": batch_id}
