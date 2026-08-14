from datetime import datetime, timedelta, timezone
from logging import getLogger

from celery import shared_task

from app.config import settings
from app.database import SessionLocal
from app.repositories.sync_run_repository import sync_run_repository
from app.utils.structured_logging import log_structured

logger = getLogger(__name__)


@shared_task
def close_stale_sync_runs() -> dict:
    """Close sync runs that never reported an outcome.

    A run is written when it starts and updated when it ends, so one whose worker died
    stays in progress forever. Age is the only thing that distinguishes those from runs
    still going.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=settings.sync_run_stale_after_hours)

    with SessionLocal() as db:
        run_keys = sync_run_repository.close_stale(db, cutoff, now)

    if run_keys:
        log_structured(
            logger,
            "warning",
            f"Closed {len(run_keys)} stale sync run(s)",
            action="sync_run_sweep_complete",
            stale_after_hours=settings.sync_run_stale_after_hours,
            closed_count=len(run_keys),
            run_keys=run_keys,
        )

    return {"closed_count": len(run_keys), "run_keys": run_keys}
