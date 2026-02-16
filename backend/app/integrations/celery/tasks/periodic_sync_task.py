from logging import getLogger

from app.database import SessionLocal
from app.integrations.celery.tasks.sync_vendor_data_task import sync_vendor_data
from app.repositories.user_connection_repository import UserConnectionRepository
from app.schemas import SyncAllUsersResult
from app.utils.structured_logging import log_structured
from celery import shared_task

logger = getLogger(__name__)


@shared_task
def sync_all_users(
    start_date: str | None = None,
    end_date: str | None = None,
    user_id: str | None = None,
) -> dict:
    """
    Sync all users with active connections.
    Calls sync_vendor_data for each user with the same parameters.

    Args:
        start_date: ISO 8601 date string for start of sync period
        end_date: ISO 8601 date string for end of sync period
    """
    log_structured(logger, "info", "Starting sync for all users", task="sync_all_users")

    user_connection_repo = UserConnectionRepository()

    with SessionLocal() as db:
        active_user_ids = user_connection_repo.get_all_active_users(db)

        log_structured(
            logger,
            "info",
            f"Found {len(active_user_ids)} users with active connections",
            provider="sync_all_users",
            task="sync_all_users",
            active_user_ids=active_user_ids,
        )

        for active_user_id in active_user_ids:
            sync_vendor_data.delay(user_id=str(active_user_id), start_date=start_date, end_date=end_date)

        return SyncAllUsersResult(users_for_sync=len(active_user_ids)).model_dump()
