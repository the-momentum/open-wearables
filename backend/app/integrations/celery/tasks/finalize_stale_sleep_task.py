from datetime import datetime, timedelta, timezone

from celery import shared_task

from app.integrations.redis_client import get_redis_client
from app.services.apple.healthkit.sleep_service import (
    finish_sleep,
    load_sleep_state,
    active_users_key,
)
from app.config import settings


@shared_task
def finalize_stale_sleeps():
    now = datetime.now(timezone.utc)
    redis_client = get_redis_client()

    for user_id in redis_client.smembers(active_users_key()):
        state = load_sleep_state(user_id)
        if not state:
            continue
        last = datetime.fromisoformat(state["last_timestamp"])
        if now - last >= timedelta(minutes=settings.sleep_end_gap_minutes):
            finish_sleep(user_id, state)