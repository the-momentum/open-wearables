from datetime import datetime
import json
from uuid import UUID


from app.schemas.apple.healthkit.redis_sleep import SleepState, SLEEP_START_STATES
from app.schemas import RootJSON, HKRecordJSON
from app.constants.series_types import get_apple_sleep_type
from app.schemas import UploadDataResponse
from app.integrations.redis_client import get_redis_client
from app.config import settings


redis_client = get_redis_client()


def key(user_id: str) -> str:
    """Generate a key for the sleep state."""
    return f"sleep:active:{user_id}"

def active_users_key() -> str:
    """Generate a key for the active users."""
    return "sleep:active_users"

def load_sleep_state(user_id: str) -> SleepState | None:
    """Load the sleep state from Redis."""
    key = key(user_id)
    return redis_client.hgetall(key)

def save_sleep_state(user_id: str, state: SleepState) -> None:
    redis_client.set(key(user_id), json.dumps(state), ex=settings.redis_ttl_seconds)
    redis_client.sadd(active_users_key(), user_id)


def delete_sleep_state(user_id: str) -> None:
    redis_client.delete(key(user_id))
    redis_client.srem(active_users_key(), user_id)


def _apply_transition(state: SleepState, sleep_state: SleepState, start_time: datetime) -> SleepState:
    """Apply a transition to the sleep state."""
    
    last_timestamp = datetime.fromisoformat(state["last_timestamp"])
    delta_seconds = (start_time - last_timestamp).total_seconds()
    
    last_type = get_apple_sleep_type(state["last_type"])

    match last_type:
        case SleepState.IN_BED:
            state["in_bed"] += delta_seconds
        case SleepState.AWAKE:
            state["awake"] += delta_seconds
        case SleepState.ASLEEP_CORE:
            state["deep"] += delta_seconds
        case SleepState.ASLEEP_REM:
            state["rem"] += delta_seconds
        case _:
            pass

    state["last_type"] = int(sleep_state)
    state["last_timestamp"] = start_time.isoformat()
    return state

def handle_sleep_data(
        raw: dict,
        user_id: str,
    ) -> UploadDataResponse:
        root = RootJSON(**raw)
        sleep_raw = root.data.get("sleep", [])

        current_state = load_sleep_state(user_id)

        for s in sleep_raw:
            sjson = HKRecordJSON(**s)
            sleep_state = get_apple_sleep_type(sjson.value)

            if not current_state:
                if sleep_state not in SLEEP_START_STATES:
                    return

                current_state = SleepState(
                    start_time=sjson.startDate,
                    last_type=sleep_state,
                    last_timestamp=sjson.startDate,
                    in_bed=0,
                    awake=0,
                    light=0,
                    deep=0,
                    rem=0,
                )
                save_sleep_state(user_id, current_state)
                return

            current_state = _apply_transition(current_state, sleep_state, sjson.startDate)
            save_sleep_state(user_id, current_state)


