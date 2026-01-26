from logging import getLogger
from uuid import UUID

from app.database import SessionLocal
from app.integrations.celery.tasks.finalize_stale_sleep_task import finalize_stale_sleeps
from app.models import User
from app.repositories.user_connection_repository import UserConnectionRepository
from app.repositories.user_repository import UserRepository
from app.services.apple.auto_export.import_service import import_service as ae_import_service
from app.services.apple.healthkit.import_service import import_service as hk_import_service
from celery import shared_task

logger = getLogger(__name__)


@shared_task
def process_apple_upload(
    content: str, content_type: str, user_id: str, source: str = "healthion"
) -> dict[str, int | str]:
    """
    Process Apple Health data import asynchronously (HealthKit/Auto Health Export).

    Args:
        content: The request content as string (JSON or multipart data)
        content_type: The content type header value
        user_id: User ID to associate with the data
        source: Import source - "healthion" or "auto-health-export"

    Returns:
        Dictionary with status_code and response message
    """
    # Validate user_id format
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        logger.warning(f"Invalid user_id format: {user_id}")
        return {"status": "error", "reason": "invalid_user_id"}

    # Validate user exists before processing
    with SessionLocal() as db:
        user_repo = UserRepository(User)
        if not user_repo.get(db, user_uuid):
            logger.warning(f"Skipping import for non-existent user: {user_id}")
            return {"status": "skipped", "reason": "user_not_found"}

    with SessionLocal() as db:
        # Ensure Apple connection exists for this user (SDK-based, no OAuth tokens)
        connection_repo = UserConnectionRepository()
        connection_repo.ensure_sdk_connection(db, user_uuid, "apple")

        # Select the appropriate import service based on source
        import_service = hk_import_service if source == "healthion" else ae_import_service

        result = import_service.import_data_from_request(db, content, content_type, user_id).model_dump()

        finalize_stale_sleeps.delay()

        return result
