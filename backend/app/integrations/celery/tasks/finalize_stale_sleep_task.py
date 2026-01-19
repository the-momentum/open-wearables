from datetime import datetime, timedelta, timezone

from app.config import settings
from app.database import SessionLocal
from app.integrations.redis_client import get_redis_client
from app.services.apple.healthkit.sleep_service import (
    active_users_key,
    finish_sleep,
    load_sleep_state,
)
from celery import shared_task


@shared_task
def finalize_stale_sleeps() -> None:
    now = datetime.now(timezone.utc)
    redis_client = get_redis_client()

    with SessionLocal() as db:
        for user_id in redis_client.smembers(active_users_key()):
            state = load_sleep_state(user_id)
            if not state:
                continue
            last = datetime.fromisoformat(state["last_timestamp"])
            if now - last >= timedelta(minutes=settings.sleep_end_gap_minutes):
                finish_sleep(db, user_id, state)
