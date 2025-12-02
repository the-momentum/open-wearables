from logging import getLogger

from celery import shared_task

from app.database import SessionLocal
from app.integrations.celery.tasks.sync_vendor_data_task import sync_vendor_data
from app.models import UserConnection

logger = getLogger(__name__)


@shared_task
def sync_all_users(start_date: str | None = None, end_date: str | None = None) -> dict:
    """
    Sync all users with active connections.
    Calls sync_vendor_data for each user with the same parameters.
    """
    logger.info("[sync_all_users] Starting sync for all users")

    with SessionLocal() as db:
        # Get all unique user IDs with active connections
        user_ids = [
            str(conn.user_id)
            for conn in db.query(UserConnection.user_id)
            .filter(UserConnection.status == "active")
            .distinct()
            .all()
        ]

        logger.info(f"[sync_all_users] Found {len(user_ids)} users with active connections")

        # Dispatch sync tasks for each user
        for user_id in user_ids:
            sync_vendor_data.delay(user_id, start_date, end_date)

        return {"users_synced": len(user_ids)}
