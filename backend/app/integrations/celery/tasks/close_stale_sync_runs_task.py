from datetime import datetime, timedelta, timezone
from logging import getLogger

from celery import shared_task

from app.config import settings
from app.database import SessionLocal
from app.repositories.sync_run_repository import sync_run_repository
from app.services.sync_status_service import last_event_at
from app.utils.structured_logging import log_structured

logger = getLogger(__name__)


@shared_task
def close_stale_sync_runs() -> dict:
    """Close sync runs that stopped reporting without an outcome.

    Postgres only receives a run's start and its terminal event, so one whose worker died
    stays in progress forever. Age alone would also catch a long backfill that is still
    working, so candidates are checked against Redis first: progress events keep the
    run's Redis entry fresh even though they are never persisted. A run that emitted
    something after the cutoff is alive and left alone.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=settings.sync_run_stale_after_hours)

    with SessionLocal() as db:
        candidates = sync_run_repository.find_stale(db, cutoff)
        if not candidates:
            return {"closed_count": 0, "run_keys": [], "still_active": 0}

        last_seen = last_event_at(candidates)
        stale = [
            key for key in candidates if (last_seen.get(key) or datetime.min.replace(tzinfo=timezone.utc)) < cutoff
        ]
        closed = sync_run_repository.close_as_stale(db, stale, now)

    if closed:
        log_structured(
            logger,
            "warning",
            f"Closed {len(closed)} stale sync run(s)",
            action="sync_run_sweep_complete",
            stale_after_hours=settings.sync_run_stale_after_hours,
            closed_count=len(closed),
            still_active=len(candidates) - len(stale),
            run_keys=closed,
        )

    return {"closed_count": len(closed), "run_keys": closed, "still_active": len(candidates) - len(stale)}
