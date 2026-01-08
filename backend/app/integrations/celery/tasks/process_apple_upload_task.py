from app.database import SessionLocal
from app.services.apple.auto_export.import_service import import_service as ae_import_service
from app.services.apple.healthkit.import_service import import_service as hk_import_service
from celery import shared_task


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
    with SessionLocal() as db:
        # Select the appropriate import service based on source
        import_service = hk_import_service if source == "healthion" else ae_import_service

        return import_service.import_data_from_request(db, content, content_type, user_id).model_dump()
