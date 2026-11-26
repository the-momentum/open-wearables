"""Celery task for generating seed data via the dashboard."""

from celery import shared_task

from app.constants.celery_tasks import CeleryTask
from app.database import SessionLocal
from app.schemas.utils.seed_data import SeedDataRequest
from app.services.seed_data import seed_data_service
from app.utils.structured_logging import get_logger

logger = get_logger(__name__)


@shared_task(
    name=CeleryTask.GENERATE_SEED_DATA,
    soft_time_limit=600,  # 10 min soft limit
    time_limit=660,  # 11 min hard limit
    acks_late=True,
)
def generate_seed_data(request_data: dict) -> dict:
    """Generate synthetic user data based on the provided profile configuration."""
    config = SeedDataRequest.model_validate(request_data)
    with SessionLocal() as db:
        try:
            summary = seed_data_service.generate(db, config)
            logger.info("Seed data generation completed", summary=summary)
            return summary
        except Exception as e:
            logger.error("Seed data generation failed", exc_info=e)
            raise
