from contextlib import suppress
from datetime import datetime, timedelta
from logging import getLogger
from typing import Any, cast
from uuid import UUID

from app.database import SessionLocal
from app.repositories.user_connection_repository import UserConnectionRepository
from app.schemas import ProviderSyncResult, SyncVendorDataResult
from app.services.providers.factory import ProviderFactory
from app.utils.sentry_helpers import log_and_capture_error
from celery import shared_task

logger = getLogger(__name__)


@shared_task
def sync_vendor_data(
    user_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
    providers: list[str] | None = None,
) -> dict[str, Any]:
    """
    Synchronize workout/exercise/activity data from all providers the user is connected to.

    Args:
        user_id: UUID of the user to sync data for
        start_date: ISO 8601 date string for start of sync period (None = full history)
        end_date: ISO 8601 date string for end of sync period (None = current time)
        providers: Optional list of provider names to sync (None = all active providers)

    Returns:
        dict with sync results per provider
    """
    factory = ProviderFactory()
    user_connection_repo = UserConnectionRepository()

    try:
        user_uuid = UUID(user_id)
    except ValueError as e:
        logger.error(f"[sync_vendor_data] Invalid user_id format: {user_id}")
        return SyncVendorDataResult(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            errors={"user_id": f"Invalid UUID format: {str(e)}"},
        ).model_dump()

    result = SyncVendorDataResult(
        user_id=user_uuid,
        start_date=start_date,
        end_date=end_date,
    )

    with SessionLocal() as db:
        try:
            connections = user_connection_repo.get_all_active_by_user(db, user_uuid)

            if providers:
                connections = [c for c in connections if c.provider in providers]

            if not connections:
                logger.info(f"[sync_vendor_data] No active connections found for user {user_id}")
                result.message = "No active provider connections found"
                return result.model_dump()

            logger.info(
                f"[sync_vendor_data] Found {len(connections)} active connections for user {user_id}",
            )

            for connection in connections:
                provider_name = connection.provider
                logger.info(f"[sync_vendor_data] Syncing data from {provider_name} for user {user_id}")

                try:
                    strategy = factory.get_provider(provider_name)
                    provider_result = ProviderSyncResult(success=True, params={})

                    # Sync workouts
                    if strategy.workouts:
                        params = _build_sync_params(provider_name, start_date, end_date)
                        try:
                            success = strategy.workouts.load_data(db, user_uuid, **params)
                            provider_result.params["workouts"] = {"success": success, **params}
                        except Exception as e:
                            logger.warning(f"[sync_vendor_data] Workouts sync failed for {provider_name}: {e}")
                            provider_result.params["workouts"] = {"success": False, "error": str(e)}

                    # Sync 247 data (sleep, recovery, activity) and SAVE to database
                    if hasattr(strategy, "data_247") and strategy.data_247:
                        # Determine if this is first sync (max timeframe) or subsequent sync
                        is_first_sync = connection.last_synced_at is None

                        # Parse dates
                        start_dt = datetime.now() - timedelta(days=30)
                        end_dt = datetime.now()

                        if start_date:
                            with suppress(ValueError):
                                start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
                        if end_date:
                            with suppress(ValueError):
                                end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))

                        try:
                            # Use load_and_save_all if available (saves data to DB)
                            # Otherwise fallback to load_all_247_data (just returns data)
                            provider_any = cast(Any, strategy.data_247)
                            if hasattr(provider_any, "load_and_save_all"):
                                results_247 = provider_any.load_and_save_all(
                                    db,
                                    user_uuid,
                                    start_time=start_dt,
                                    end_time=end_dt,
                                    is_first_sync=is_first_sync,
                                )
                                provider_result.params["data_247"] = {"success": True, "saved": True, **results_247}
                            else:
                                results_247 = strategy.data_247.load_all_247_data(
                                    db,
                                    user_uuid,
                                    start_time=start_dt,
                                    end_time=end_dt,
                                )
                                provider_result.params["data_247"] = {"success": True, "saved": False, **results_247}
                            logger.info(f"[sync_vendor_data] 247 data synced for {provider_name}: {results_247}")
                        except Exception as e:
                            logger.warning(f"[sync_vendor_data] 247 data sync failed for {provider_name}: {e}")
                            provider_result.params["data_247"] = {"success": False, "error": str(e)}

                    user_connection_repo.update_last_synced_at(db, connection)

                    result.providers_synced[provider_name] = provider_result
                    logger.info(
                        f"[sync_vendor_data] Successfully synced {provider_name} for user {user_id}",
                    )

                except Exception as e:
                    log_and_capture_error(
                        e,
                        logger,
                        f"[sync_vendor_data] Error syncing {provider_name} for user {user_id}: {str(e)}",
                        extra={"user_id": user_id, "provider": provider_name},
                    )
                    result.errors[provider_name] = str(e)
                    continue

            return result.model_dump()

        except Exception as e:
            log_and_capture_error(
                e,
                logger,
                f"[sync_vendor_data] Error processing user {user_id}: {str(e)}",
                extra={"user_id": user_id},
            )
            result.errors["general"] = str(e)
            return result.model_dump()


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
    params: dict[str, Any] = {
        "start_date": start_date,
        "end_date": end_date,
    }

    # Convert date strings to appropriate formats
    start_timestamp = None
    end_timestamp = None

    if start_date:
        try:
            if isinstance(start_date, datetime):
                start_dt = start_date
            else:
                start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
            start_timestamp = int(start_dt.timestamp())
        except (ValueError, AttributeError) as e:
            logger.warning(f"[_build_sync_params] Invalid start_date format: {start_date}, error: {e}")

    if end_date:
        try:
            if isinstance(end_date, datetime):
                end_dt = end_date
            else:
                end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
            end_timestamp = int(end_dt.timestamp())
        except (ValueError, AttributeError) as e:
            logger.warning(f"[_build_sync_params] Invalid end_date format: {end_date}, error: {e}")

    # Provider-specific parameter mapping
    if provider_name == "polar":
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

    elif provider_name == "whoop":
        # Whoop API uses 'start' and 'end' parameters (ISO 8601 strings)
        if start_date:
            params["start"] = start_date
        if end_date:
            params["end"] = end_date

    # Add generic parameters for providers that might use them
    if start_timestamp:
        params["since"] = start_timestamp
    if end_timestamp:
        params["until"] = end_timestamp

    return params
