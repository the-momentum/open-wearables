import contextlib
from datetime import datetime, timezone
from logging import getLogger
from typing import cast

from celery import shared_task

from app.constants.celery_tasks import CeleryTask
from app.database import SessionLocal
from app.integrations.redis_client import get_redis_client
from app.services.sdk.sleep_service import (
    active_users_key,
    finish_sleep,
    is_ready_to_finish,
    load_sleep_state,
)
from app.utils.sentry_helpers import log_and_capture_error

logger = getLogger(__name__)


@shared_task(name=CeleryTask.FINALIZE_STALE_SLEEPS)
def finalize_stale_sleeps() -> None:
    now = datetime.now(timezone.utc)
    redis_client = get_redis_client()

    with SessionLocal() as db:
        for user_id in cast(set[str], redis_client.smembers(active_users_key())):
            try:
                # Skip users whose upload is currently in progress.
                lock = redis_client.lock(f"sleep:lock:{user_id}", timeout=30, blocking_timeout=0)
                if not lock.acquire(blocking=False):
                    continue

                try:
                    state = load_sleep_state(user_id)
                    if state and is_ready_to_finish(state, now):
                        finish_sleep(db, user_id, state)
                finally:
                    with contextlib.suppress(Exception):
                        lock.release()

            except Exception as e:
                log_and_capture_error(
                    e,
                    logger,
                    f"Error finalizing stale sleep for user {user_id}: {e}",
                    extra={"user_id": user_id},
                )
