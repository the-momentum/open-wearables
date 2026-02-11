import time
from contextlib import suppress
from datetime import datetime, timedelta
from logging import getLogger
from typing import Any, cast
from uuid import UUID

from opentelemetry import trace

from app.database import SessionLocal
from app.integrations.observability import record_histogram, record_metric
from app.repositories.user_connection_repository import UserConnectionRepository
from app.schemas import ProviderSyncResult, SyncVendorDataResult
from app.services.providers.factory import ProviderFactory
from app.utils.sentry_helpers import log_and_capture_error
from celery import shared_task

logger = getLogger(__name__)
tracer = trace.get_tracer(__name__)


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
    with tracer.start_as_current_span("sync_vendor_data") as span:
        span.set_attribute("user.id", user_id)
        if start_date:
            span.set_attribute("sync.start_date", start_date)
        if end_date:
            span.set_attribute("sync.end_date", end_date)

        factory = ProviderFactory()
        user_connection_repo = UserConnectionRepository()

        try:
            user_uuid = UUID(user_id)
        except ValueError as e:
            logger.error(
                "Invalid user_id format",
                extra={"user_id": user_id, "error": str(e)},
            )
            span.set_attribute("error", True)
            span.set_attribute("error.type", "invalid_user_id")
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
                    logger.info(
                        "No active connections found for user",
                        extra={"user_id": user_id},
                    )
                    result.message = "No active provider connections found"
                    span.set_attribute("sync.connections_count", 0)
                    return result.model_dump()

                span.set_attribute("sync.connections_count", len(connections))
                logger.info(
                    "Found active connections for user",
                    extra={"user_id": user_id, "connections_count": len(connections)},
                )

                for connection in connections:
                    provider_name = connection.provider
                    _sync_single_provider(
                        span,
                        db,
                        user_uuid,
                        user_id,
                        provider_name,
                        connection,
                        factory,
                        user_connection_repo,
                        start_date,
                        end_date,
                        result,
                    )

                span.set_attribute("sync.providers_synced", len(result.providers_synced))
                span.set_attribute("sync.errors_count", len(result.errors))
                return result.model_dump()

            except Exception as e:
                log_and_capture_error(
                    e,
                    logger,
                    f"Error processing user {user_id}: {str(e)}",
                    extra={"user_id": user_id},
                )
                span.set_attribute("error", True)
                span.record_exception(e)
                result.errors["general"] = str(e)
                return result.model_dump()


def _sync_single_provider(
    parent_span: trace.Span,
    db: Any,
    user_uuid: UUID,
    user_id: str,
    provider_name: str,
    connection: Any,
    factory: ProviderFactory,
    user_connection_repo: UserConnectionRepository,
    start_date: str | None,
    end_date: str | None,
    result: SyncVendorDataResult,
) -> None:
    """Sync data from a single provider with tracing and metrics."""
    with tracer.start_as_current_span(f"sync_provider.{provider_name}") as span:
        span.set_attribute("provider.name", provider_name)
        span.set_attribute("user.id", user_id)

        sync_start_time = time.time()

        logger.info(
            "Syncing data from provider",
            extra={"provider": provider_name, "user_id": user_id},
        )

        try:
            strategy = factory.get_provider(provider_name)
            provider_result = ProviderSyncResult(success=True, params={})

            # Sync workouts
            if strategy.workouts:
                with tracer.start_as_current_span("sync_workouts") as workout_span:
                    workout_span.set_attribute("provider.name", provider_name)
                    params = _build_sync_params(provider_name, start_date, end_date)
                    try:
                        success = strategy.workouts.load_data(db, user_uuid, **params)
                        provider_result.params["workouts"] = {"success": success, **params}
                        workout_span.set_attribute("sync.success", success)
                        if success:
                            record_metric("workouts_synced", labels={"provider": provider_name})
                    except Exception as e:
                        logger.warning(
                            "Workouts sync failed",
                            extra={"provider": provider_name, "error": str(e)},
                        )
                        provider_result.params["workouts"] = {"success": False, "error": str(e)}
                        workout_span.set_attribute("error", True)
                        workout_span.record_exception(e)

            # Sync 247 data (sleep, recovery, activity) and SAVE to database
            if hasattr(strategy, "data_247") and strategy.data_247:
                with tracer.start_as_current_span("sync_247_data") as data_span:
                    data_span.set_attribute("provider.name", provider_name)
                    is_first_sync = connection.last_synced_at is None
                    data_span.set_attribute("sync.is_first_sync", is_first_sync)

                    start_dt = datetime.now() - timedelta(days=30)
                    end_dt = datetime.now()

                    if start_date:
                        with suppress(ValueError):
                            start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
                    if end_date:
                        with suppress(ValueError):
                            end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))

                    try:
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
                            data_span.set_attribute("sync.saved", True)
                        else:
                            results_247 = strategy.data_247.load_all_247_data(
                                db,
                                user_uuid,
                                start_time=start_dt,
                                end_time=end_dt,
                            )
                            provider_result.params["data_247"] = {"success": True, "saved": False, **results_247}
                            data_span.set_attribute("sync.saved", False)

                        logger.info(
                            "247 data synced",
                            extra={"provider": provider_name, "results": results_247},
                        )
                        record_metric("activities_synced", labels={"provider": provider_name})
                    except Exception as e:
                        logger.warning(
                            "247 data sync failed",
                            extra={"provider": provider_name, "error": str(e)},
                        )
                        provider_result.params["data_247"] = {"success": False, "error": str(e)}
                        data_span.set_attribute("error", True)
                        data_span.record_exception(e)

            user_connection_repo.update_last_synced_at(db, connection)

            result.providers_synced[provider_name] = provider_result
            span.set_attribute("sync.success", True)

            sync_duration = time.time() - sync_start_time
            record_metric("provider_syncs", labels={"provider": provider_name, "status": "success"})
            record_histogram("provider_sync_duration", sync_duration, {"provider": provider_name})

            logger.info(
                "Successfully synced provider",
                extra={
                    "provider": provider_name,
                    "user_id": user_id,
                    "duration_seconds": round(sync_duration, 2),
                },
            )

        except Exception as e:
            log_and_capture_error(
                e,
                logger,
                f"Error syncing {provider_name} for user {user_id}: {str(e)}",
                extra={"user_id": user_id, "provider": provider_name},
            )
            span.set_attribute("error", True)
            span.record_exception(e)
            result.errors[provider_name] = str(e)
            record_metric(
                "provider_sync_errors",
                labels={"provider": provider_name, "error_type": type(e).__name__},
            )


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
