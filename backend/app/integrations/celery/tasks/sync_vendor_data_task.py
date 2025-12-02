from datetime import datetime
from logging import getLogger
from typing import Any
from uuid import UUID

from celery import shared_task

from app.database import SessionLocal
from app.repositories.user_connection_repository import UserConnectionRepository
from app.services.providers.factory import ProviderFactory

logger = getLogger(__name__)


@shared_task
def sync_vendor_data(
    user_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    """
    Synchronize workout/exercise/activity data from all providers the user is connected to.

    Args:
        user_id: UUID of the user to sync data for
        start_date: ISO 8601 date string for start of sync period (None = full history)
        end_date: ISO 8601 date string for end of sync period (None = current time)

    Returns:
        dict with sync results per provider
    """
    factory = ProviderFactory()
    user_connection_repo = UserConnectionRepository()
    
    results: dict[str, Any] = {
        "user_id": user_id,
        "start_date": start_date,
        "end_date": end_date,
        "providers_synced": {},
        "errors": {},
    }

    try:
        user_uuid = UUID(user_id)
    except ValueError as e:
        logger.error(f"[sync_vendor_data] Invalid user_id format: {user_id}")
        results["errors"]["user_id"] = f"Invalid UUID format: {str(e)}"
        return results

    with SessionLocal() as db:
        try:
            connections = user_connection_repo.get_all_active_by_user(db, user_uuid)

            if not connections:
                logger.info(f"[sync_vendor_data] No active connections found for user {user_id}")
                results["message"] = "No active provider connections found"
                return results

            logger.info(
                f"[sync_vendor_data] Found {len(connections)} active connections for user {user_id}",
            )

            for connection in connections:
                provider_name = connection.provider
                logger.info(f"[sync_vendor_data] Syncing data from {provider_name} for user {user_id}")

                try:
                    strategy = factory.get_provider(provider_name)

                    if not strategy.workouts:
                        logger.warning(
                            f"[sync_vendor_data] Provider {provider_name} does not support workouts",
                        )
                        results["errors"][provider_name] = "Workouts not supported"
                        continue

                    params = _build_sync_params(provider_name, start_date, end_date)

                    success = strategy.workouts.load_data(db, user_uuid, **params)

                    if success:
                        connection.last_synced_at = datetime.now()
                        db.add(connection)
                        db.commit()

                        results["providers_synced"][provider_name] = {
                            "success": True,
                            "params": params,
                        }
                        logger.info(
                            f"[sync_vendor_data] Successfully synced {provider_name} for user {user_id}",
                        )
                    else:
                        results["errors"][provider_name] = "Sync returned False"
                        logger.warning(
                            f"[sync_vendor_data] Sync returned False for {provider_name}, user {user_id}",
                        )

                except Exception as e:
                    logger.error(
                        f"[sync_vendor_data] Error syncing {provider_name} for user {user_id}: {str(e)}",
                        exc_info=True,
                    )
                    results["errors"][provider_name] = str(e)
                    continue

            return results

        except Exception as e:
            logger.error(
                f"[sync_vendor_data] Error processing user {user_id}: {str(e)}",
                exc_info=True,
            )
            results["errors"]["general"] = str(e)
            return results


def _build_sync_params(provider_name: str, start_date: str | None, end_date: str | None) -> dict[str, Any]:
    """
    Build provider-specific parameters for syncing data.

    Args:
        provider_name: Name of the provider ('suunto', 'garmin', 'polar', etc.)
        start_date: ISO 8601 date string for start of sync period
        end_date: ISO 8601 date string for end of sync period

    Returns:
        Dictionary of parameters for the provider's load_data method
    """
    params: dict[str, Any] = {}

    # Convert date strings to appropriate formats
    start_timestamp = None
    end_timestamp = None

    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
            start_timestamp = int(start_dt.timestamp())
        except (ValueError, AttributeError) as e:
            logger.warning(f"[_build_sync_params] Invalid start_date format: {start_date}, error: {e}")

    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
            end_timestamp = int(end_dt.timestamp())
        except (ValueError, AttributeError) as e:
            logger.warning(f"[_build_sync_params] Invalid end_date format: {end_date}, error: {e}")

    # Provider-specific parameters
    if provider_name == "suunto":
        # Suunto parameters
        params["since"] = start_timestamp if start_timestamp else 0  # 0 = all history
        params["limit"] = 100  # Max allowed by Suunto
        params["offset"] = 0
        params["filter_by_modification_time"] = True

    elif provider_name == "polar":
        # Polar parameters
        # Note: Polar typically uses its own pagination, but we can include optional flags
        params["samples"] = False  # Can be enabled for detailed sample data
        params["zones"] = False
        params["route"] = False

    elif provider_name == "garmin":
        # Garmin backfill API parameters
        if start_date:
            params["summary_start_time"] = start_date
        if end_date:
            params["summary_end_time"] = end_date

    # Add generic parameters for providers that might use them
    if start_timestamp:
        params["since"] = start_timestamp
    if end_timestamp:
        params["until"] = end_timestamp

    return params
