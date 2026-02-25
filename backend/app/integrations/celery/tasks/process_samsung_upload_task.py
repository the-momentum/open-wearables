import uuid
from logging import getLogger
from uuid import UUID

from app.database import SessionLocal
from app.integrations.celery.tasks.finalize_stale_sleep_task import finalize_stale_sleeps
from app.models import User
from app.repositories.user_connection_repository import UserConnectionRepository
from app.repositories.user_repository import UserRepository
from app.services.apple.healthkit.import_service import ImportService
from app.utils.structured_logging import log_structured
from celery import shared_task

logger = getLogger(__name__)

# Samsung-specific import service instance
# Reuses Apple/HealthKit import logic since Samsung SDK payload format is identical
samsung_import_service = ImportService(
    log=getLogger(__name__),
)


@shared_task(queue="samsung_sync")
def process_samsung_upload(
    content: str,
    content_type: str,
    user_id: str,
    batch_id: str | None = None,
) -> dict[str, int | str]:
    """
    Process Samsung Health data import asynchronously.

    Samsung Health SDK uses the same payload format as Apple HealthKit,
    so we reuse the import service with Samsung-specific provider settings.

    Args:
        content: The request content as string (JSON data)
        content_type: The content type header value
        user_id: User ID to associate with the data
        batch_id: Unique batch identifier for tracking (optional for backwards compatibility)

    Returns:
        Dictionary with status_code and response message
    """
    # Generate batch_id if not provided (backwards compatibility)
    if not batch_id:
        batch_id = str(uuid.uuid4())

    # Validate user_id format
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        log_structured(
            logger,
            "warning",
            "Invalid user_id format",
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
                action="validate_user_exists",
                batch_id=batch_id,
                user_id=user_id,
            )
            return {"status": "skipped", "reason": "user_not_found", "batch_id": batch_id}

    # Log task start
    log_structured(
        logger,
        "info",
        "Samsung sync batch processing started",
        action="samsung_batch_processing_start",
        batch_id=batch_id,
        user_id=user_id,
    )

    with SessionLocal() as db:
        # Ensure Samsung connection exists for this user (SDK-based, no OAuth tokens)
        connection_repo = UserConnectionRepository()
        connection_repo.ensure_sdk_connection(db, user_uuid, "samsung")

        result = samsung_import_service.import_data_from_request(
            db, content, content_type, user_id, batch_id=batch_id
        ).model_dump()

        # Log processing completion with results
        log_structured(
            logger,
            "info",
            "Samsung sync batch processing completed",
            action="samsung_batch_processing_complete",
            batch_id=batch_id,
            user_id=user_id,
            status_code=result.get("status_code"),
            response=result.get("response"),
            # Include counts from result if available
            records_saved=result.get("records_saved", 0),
            workouts_saved=result.get("workouts_saved", 0),
            sleep_saved=result.get("sleep_saved", 0),
        )

        finalize_stale_sleeps.delay()

        return {**result, "batch_id": batch_id}
