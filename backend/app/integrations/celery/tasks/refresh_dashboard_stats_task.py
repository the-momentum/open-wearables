from logging import getLogger

from celery import shared_task

from app.database import SessionLocal
from app.services import dashboard_stats_cache
from app.services.timeseries_service import timeseries_service
from app.utils.sentry_helpers import log_and_capture_error

logger = getLogger(__name__)


@shared_task
def refresh_dashboard_total_data_points(token: str | None = None) -> None:
    """Recount data points exactly and cache the result.

    Triggered on-demand from a dashboard request when the cache is cold or stale (never on a
    schedule), so the expensive scan runs off the request thread and only when someone is
    actually looking at the dashboard. ``token`` identifies the lock this run owns.
    """
    try:
        with SessionLocal() as db:
            count = timeseries_service.get_total_count(db)
        dashboard_stats_cache.store_total_data_points(count)
        # Release the lock only on success and only if we still own it; on failure leave it to
        # expire so the lock's TTL acts as a backoff instead of re-running on every dashboard load.
        if token is not None:
            dashboard_stats_cache.release_refresh_lock(token)
        logger.info("Refreshed dashboard total data points: %s", count)
    except Exception as e:
        log_and_capture_error(e, logger, "Failed to refresh dashboard total data points")
