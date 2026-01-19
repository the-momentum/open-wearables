import json
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from app.config import settings
from app.constants.series_types import (
    SleepType,
    get_apple_sleep_type,
)
from app.database import DbSession
from app.integrations.redis_client import get_redis_client
from app.schemas import (
    EventRecordCreate,
    EventRecordDetailCreate,
    HKRecordJSON,
    RootJSON,
)
from app.schemas.apple.healthkit.redis_sleep import SLEEP_START_STATES, SleepState
from app.services.event_record_service import event_record_service

redis_client = get_redis_client()


def key(user_id: str) -> str:
    """Generate a key for the sleep state."""
    return f"sleep:active:{user_id}"


def active_users_key() -> str:
    """Generate a key for the active users."""
    return "sleep:active_users"


def load_sleep_state(user_id: str) -> SleepState | None:
    """Load the sleep state from Redis."""
    sleep_state_key = key(user_id)
    state = redis_client.get(sleep_state_key)
    if not state:
        return None
    return json.loads(state.decode("utf-8"))


def save_sleep_state(user_id: str, state: SleepState) -> None:
    redis_client.set(key(user_id), json.dumps(state).encode("utf-8"))
    redis_client.expire(key(user_id), settings.redis_sleep_ttl_seconds)
    redis_client.sadd(active_users_key(), user_id)


def delete_sleep_state(user_id: str) -> None:
    redis_client.delete(key(user_id))
    redis_client.srem(active_users_key(), user_id)


def _create_new_sleep_state(start_time: datetime, sleep_state: SleepType) -> SleepState:
    return {
        "uuid": str(uuid4()),
        "start_time": start_time.isoformat(),
        "last_type": sleep_state,
        "last_timestamp": start_time.isoformat(),
        "in_bed": 0,
        "awake": 0,
        "light": 0,
        "deep": 0,
        "rem": 0,
    }


def _apply_transition(
    db_session: DbSession,
    user_id: str,
    state: SleepState,
    sleep_state: SleepType,
    start_time: datetime,
) -> SleepState:
    """Apply a transition to the sleep state."""

    last_timestamp = datetime.fromisoformat(state["last_timestamp"])
    delta_seconds = (start_time - last_timestamp).total_seconds()

    if delta_seconds <= 0:
        return state

    if delta_seconds > 3600:
        finish_sleep(db_session, user_id, state)
        return _create_new_sleep_state(start_time, sleep_state)

    last_type = get_apple_sleep_type(state["last_type"])

    match last_type:
        case SleepType.IN_BED:
            state["in_bed"] += delta_seconds
        case SleepType.AWAKE:
            state["awake"] += delta_seconds
        case SleepType.ASLEEP_CORE:
            state["deep"] += delta_seconds
        case SleepType.ASLEEP_REM:
            state["rem"] += delta_seconds
        case _:
            pass

    state["last_type"] = int(sleep_state)
    state["last_timestamp"] = start_time.isoformat()
    return state


def handle_sleep_data(
    db_session: DbSession,
    raw: dict,
    user_id: str,
) -> None:
    root = RootJSON(**raw)
    sleep_raw = root.data.get("sleep", [])

    current_state = load_sleep_state(user_id)

    for s in sleep_raw:
        sjson = HKRecordJSON(**s)
        sleep_state = get_apple_sleep_type(int(sjson.value))
        if sleep_state is None:
            continue

        if not current_state:
            if sleep_state not in SLEEP_START_STATES:
                continue

            current_state = _create_new_sleep_state(sjson.startDate, sleep_state)
            save_sleep_state(user_id, current_state)
            continue

        current_state = _apply_transition(db_session, user_id, current_state, sleep_state, sjson.startDate)
        save_sleep_state(user_id, current_state)


def finish_sleep(db_session: DbSession, user_id: str, state: SleepState) -> None:
    """Finish a sleep session."""

    end_time = datetime.fromisoformat(state["last_timestamp"])
    start_time = datetime.fromisoformat(state["start_time"])

    total_sleep = state["light"] + state["deep"] + state["rem"]
    in_bed = state["in_bed"]

    efficiency = total_sleep / in_bed if in_bed > 0 else 0

    sleep_record = EventRecordCreate(
        id=UUID(state["uuid"]),
        user_id=UUID(user_id),
        start_datetime=start_time,
        end_datetime=end_time,
        category="sleep",
        type="sleep",
        source_name="apple",
        device_id=None,
        duration_seconds=total_sleep,
    )

    detail = EventRecordDetailCreate(
        record_id=sleep_record.id,
        sleep_total_duration_minutes=total_sleep,
        sleep_time_in_bed_minutes=in_bed,
        sleep_efficiency_score=Decimal(efficiency),
        sleep_deep_minutes=state["deep"],
        sleep_rem_minutes=state["rem"],
        sleep_light_minutes=state["light"],
        sleep_awake_minutes=state["awake"],
        is_nap=False,
    )

    delete_sleep_state(user_id)

    created_or_existing_record = event_record_service.create(db_session, sleep_record)
    # Always use the returned record's ID (whether newly created or existing)
    detail_for_record = detail.model_copy(update={"record_id": created_or_existing_record.id})
    event_record_service.create_detail(db_session, detail_for_record)
