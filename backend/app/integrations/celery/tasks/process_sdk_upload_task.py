import uuid
from logging import getLogger
from uuid import UUID

from app.database import SessionLocal
from app.integrations.celery.tasks.finalize_stale_sleep_task import finalize_stale_sleeps
from app.models import User
from app.repositories.user_connection_repository import UserConnectionRepository
from app.repositories.user_repository import UserRepository
from app.services.apple.auto_export.import_service import (
    ImportService as AEImportService,
)
from app.services.apple.auto_export.import_service import (
    import_service as ae_import_service,
)
from app.services.apple.healthkit.import_service import (
    ImportService as SDKImportService,
)
from app.services.apple.healthkit.import_service import (
    import_service as sdk_import_service,
)
from app.utils.structured_logging import log_structured
from celery import shared_task

logger = getLogger(__name__)


def _get_import_service(provider: str) -> SDKImportService | AEImportService:
    if provider in ("apple", "samsung", "google"):
        return sdk_import_service
    if provider == "auto-health-export":
        return ae_import_service
    raise ValueError(f"Unsupported provider: {provider}")


@shared_task(queue="sdk_sync")
def process_sdk_upload(
    content: str,
    content_type: str,
    user_id: str,
    provider: str,
    batch_id: str | None = None,
) -> dict[str, int | str]:
    """
    Process SDK data import asynchronously.

    Args:
        content: The request content as string (JSON or multipart data)
        content_type: The content type header value
        user_id: User ID to associate with the data
        provider: Import provider - "apple", "samsung", "google", "auto-health-export"
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

    with SessionLocal() as db:
        # Ensure SDK connection exists for this user (SDK-based, no OAuth tokens)
        connection_repo = UserConnectionRepository()
        connection_repo.ensure_sdk_connection(db, user_uuid, provider)

        # # Select the appropriate import service based on source
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

        finalize_stale_sleeps.delay()

        return {**result, "batch_id": batch_id}
