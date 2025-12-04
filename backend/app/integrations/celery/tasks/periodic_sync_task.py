from logging import getLogger

from app.database import SessionLocal
from app.integrations.celery.tasks.sync_vendor_data_task import sync_vendor_data
from app.repositories.user_connection_repository import UserConnectionRepository
from app.schemas import SyncAllUsersResult
from celery import shared_task

logger = getLogger(__name__)


@shared_task
def sync_all_users(start_date: str | None = None, end_date: str | None = None) -> dict:
    """
    Sync all users with active connections.
    Calls sync_vendor_data for each user with the same parameters.
    """
    logger.info("[sync_all_users] Starting sync for all users")

    user_connection_repo = UserConnectionRepository()

    with SessionLocal() as db:
        user_ids = user_connection_repo.get_all_active_users(db)

        logger.info(f"[sync_all_users] Found {len(user_ids)} users with active connections")

        for user_id in user_ids:
            sync_vendor_data.delay(str(user_id), start_date, end_date)

        return SyncAllUsersResult(users_for_sync=len(user_ids)).model_dump()
