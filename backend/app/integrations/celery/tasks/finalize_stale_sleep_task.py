from datetime import datetime, timedelta, timezone
from logging import getLogger

from celery import shared_task

from app.config import settings
from app.database import SessionLocal
from app.services.apple.healthkit.sleep_service import (
    finish_sleep,
    iter_active_user_ids,
    load_sleep_state,
    user_sleep_lock,
)
from app.utils.sentry_helpers import log_and_capture_error

logger = getLogger(__name__)


@shared_task
def finalize_stale_sleeps() -> None:
    now = datetime.now(timezone.utc)

    with SessionLocal() as db:
        for user_id in iter_active_user_ids(db):
            try:
                # Skip users whose upload is currently in progress (non-blocking).
                with user_sleep_lock(user_id, wait_seconds=0) as acquired:
                    if not acquired:
                        continue

                    state = load_sleep_state(db, user_id)
                    if not state:
                        continue

                    end_time = state.end_time
                    if end_time.tzinfo is None:
                        end_time = end_time.replace(tzinfo=timezone.utc)

                    if now - end_time >= timedelta(minutes=settings.sleep_end_gap_minutes):
                        finish_sleep(db, user_id, state)

            except Exception as e:
                log_and_capture_error(
                    e,
                    logger,
                    f"Error finalizing stale sleep for user {user_id}: {e}",
                    extra={"user_id": user_id},
                )
