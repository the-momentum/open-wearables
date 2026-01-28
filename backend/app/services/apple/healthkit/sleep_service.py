import json
from datetime import datetime
from decimal import Decimal
from logging import getLogger
from uuid import UUID, uuid4

from app.config import settings
from app.constants.series_types import (
    SleepPhase,
    get_apple_sleep_phase,
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
from app.utils.sentry_helpers import log_and_capture_error

redis_client = get_redis_client()

logger = getLogger(__name__)


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
    return json.loads(state)


def save_sleep_state(user_id: str, state: SleepState) -> None:
    redis_client.set(key(user_id), json.dumps(state))
    redis_client.expire(key(user_id), settings.redis_sleep_ttl_seconds)
    redis_client.sadd(active_users_key(), user_id)


def delete_sleep_state(user_id: str) -> None:
    redis_client.delete(key(user_id))
    redis_client.srem(active_users_key(), user_id)


def _create_new_sleep_state(
    start_time: datetime,
    uuid: str | None = None,
    source_name: str | None = None,
) -> SleepState:
    return {
        "uuid": uuid or str(uuid4()),
        "source_name": source_name or "Apple",
        "start_time": start_time.isoformat(),
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
    sleep_phase: SleepPhase,
    start_time: datetime,
    end_time: datetime,
    uuid: str | None = None,
    source_name: str | None = None,
) -> SleepState:
    """Apply a transition to the sleep state."""

    last_timestamp = datetime.fromisoformat(state["last_timestamp"])
    delta_seconds = (start_time - last_timestamp).total_seconds()

    if delta_seconds < 0:
        return state

    if delta_seconds > settings.sleep_end_gap_minutes * 60:
        finish_sleep(db_session, user_id, state)
        return _create_new_sleep_state(start_time, uuid, source_name)

    duration_seconds = (end_time - start_time).total_seconds()

    match sleep_phase:
        case SleepPhase.IN_BED:
            state["in_bed"] += duration_seconds
        case SleepPhase.AWAKE:
            state["awake"] += duration_seconds
        case SleepPhase.ASLEEP_CORE:
            state["light"] += duration_seconds
        case SleepPhase.ASLEEP_DEEP:
            state["deep"] += duration_seconds
        case SleepPhase.ASLEEP_REM:
            state["rem"] += duration_seconds
        case SleepPhase.ASLEEP_UNSPECIFIED:
            state["deep"] += duration_seconds
        case _:
            pass

    state["last_timestamp"] = end_time.isoformat()
    return state


def handle_sleep_data(
    db_session: DbSession,
    raw: dict,
    user_id: str,
) -> None:
    """
    Process Apple HealthKit sleep data and track sleep sessions using Redis state.

    Sleep sessions are tracked in Redis and automatically finalized to the database when
    a gap of more than 1 hour is detected between consecutive sleep records.

    Args:
        db_session: Database session for persisting finalized sleep records
        raw: Raw JSON data from Apple HealthKit containing sleep records
        user_id: User identifier for associating sleep data

    Flow:
        - If no active session exists: Create new session in Redis (only for valid start states)
        - If active session exists: Check gap between last record's end and current record's start
          * Gap > 1 hour: Finalize existing session, start new one
          * Otherwise: Accumulate sleep stage durations in existing session
    """
    root = RootJSON(**raw)
    sleep_raw = root.data.get("sleep", [])

    current_state = load_sleep_state(user_id)

    for s in sleep_raw:
        sjson = HKRecordJSON(**s)
        source_name = sjson.source.name
        sleep_phase = get_apple_sleep_phase(int(sjson.value))

        if sleep_phase is None:
            continue

        if not current_state:
            if sleep_phase not in SLEEP_START_STATES:
                continue

            current_state = _create_new_sleep_state(sjson.startDate, sjson.uuid, source_name)
            # Store endDate as last_timestamp since that's when this period actually ends
            current_state["last_timestamp"] = sjson.endDate.isoformat()
            save_sleep_state(user_id, current_state)
            continue

        # Check if there's a gap between the last record's end and this record's start
        current_state = _apply_transition(
            db_session,
            user_id,
            current_state,
            sleep_phase,
            sjson.startDate,
            sjson.endDate,
            sjson.uuid,
            source_name,
        )
        save_sleep_state(user_id, current_state)


def finish_sleep(db_session: DbSession, user_id: str, state: SleepState) -> None:
    """Finish a sleep session and save the record to the database."""

    end_time = datetime.fromisoformat(state["last_timestamp"])
    start_time = datetime.fromisoformat(state["start_time"])

    total_duration = (end_time - start_time).total_seconds()
    total_sleep_seconds = state["light"] + state["deep"] + state["rem"]
    in_bed = state["in_bed"]

    efficiency = (total_sleep_seconds / total_duration) * 100 if total_duration > 0 else None
    efficiency_score = Decimal(str(efficiency)) if efficiency is not None else None

    sleep_record = EventRecordCreate(
        id=uuid4(),
        external_id=state.get("uuid"),
        user_id=UUID(user_id),
        start_datetime=start_time,
        end_datetime=end_time,
        duration_seconds=total_sleep_seconds,
        category="sleep",
        type="sleep_session",
        source_name=state.get("source_name") or "Apple",
        device_id=None,
    )

    detail = EventRecordDetailCreate(
        record_id=sleep_record.id,
        sleep_total_duration_minutes=total_sleep_seconds // 60,
        sleep_time_in_bed_minutes=in_bed // 60,
        sleep_efficiency_score=efficiency_score,
        sleep_deep_minutes=state["deep"] // 60,
        sleep_rem_minutes=state["rem"] // 60,
        sleep_light_minutes=state["light"] // 60,
        sleep_awake_minutes=state["awake"] // 60,
        is_nap=False,
    )

    delete_sleep_state(user_id)

    try:
        created_or_existing_record = event_record_service.create(db_session, sleep_record)
        # Always use the returned record's ID (whether newly created or existing)
        detail_for_record = detail.model_copy(update={"record_id": created_or_existing_record.id})
        event_record_service.create_detail(db_session, detail_for_record, detail_type="sleep")
    except Exception as e:
        log_and_capture_error(
            e,
            logger,
            f"Error saving sleep record {sleep_record.id} for user {user_id}: {e}",
            extra={"user_id": user_id},
        )
