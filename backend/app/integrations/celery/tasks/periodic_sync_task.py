from logging import getLogger

from celery import shared_task

from app.database import SessionLocal
from app.integrations.celery.tasks.sync_vendor_data_task import sync_vendor_data
from app.repositories.user_connection_repository import UserConnectionRepository
from app.schemas.responses.upload import SyncAllUsersResult
from app.services.provider_settings_service import provider_settings_service
from app.utils.structured_logging import log_structured

logger = getLogger(__name__)


@shared_task
def sync_all_users(
    start_date: str | None = None,
    end_date: str | None = None,
    user_id: str | None = None,
) -> dict:
    """
    Sync all users with an active connection to a provider in pull mode.
    Calls sync_vendor_data for each user with the same parameters.

    Args:
        start_date: ISO 8601 date string for start of sync period
        end_date: ISO 8601 date string for end of sync period
    """
    log_structured(logger, "info", "Starting sync for all users", task="sync_all_users")

    with SessionLocal() as db:
        eligible_providers = provider_settings_service.get_pull_eligible_providers(db)
        active_user_ids = UserConnectionRepository().get_all_active_users(db, eligible_providers)

    log_structured(
        logger,
        "info",
        f"Found {len(active_user_ids)} users with a pull-mode connection",
        provider="sync_all_users",
        task="sync_all_users",
        eligible_providers=eligible_providers,
    )

    for active_user_id in active_user_ids:
        sync_vendor_data.delay(user_id=str(active_user_id), start_date=start_date, end_date=end_date)

    return SyncAllUsersResult(users_for_sync=len(active_user_ids)).model_dump()
