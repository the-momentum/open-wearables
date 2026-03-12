import json
from datetime import datetime
from logging import getLogger
from uuid import UUID, uuid4

from app.config import settings
from app.constants.series_types.apple import (
    SleepPhase,
    get_apple_sleep_phase,
)
from app.database import DbSession
from app.integrations.redis_client import get_redis_client
from app.schemas import (
    EventRecordCreate,
    EventRecordDetailCreate,
    SDKSyncRequest,
)
from app.schemas.apple.healthkit.sleep_state import SLEEP_START_STATES, SleepState
from app.services.apple.healthkit.device_resolution import extract_device_info
from app.services.event_record_service import event_record_service
from app.utils.structured_logging import log_structured

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
    end_time: datetime,
    id: str | None = None,
    provider: str | None = None,
    source_name: str | None = None,
    device_model: str | None = None,
) -> SleepState:
    return {
        "uuid": id or str(uuid4()),
        "source_name": source_name or "unknown",
        "device_model": device_model,
        "provider": provider,
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "last_start_timestamp": start_time.isoformat(),
        "last_end_timestamp": end_time.isoformat(),
        "in_bed_seconds": 0,
        "awake_seconds": 0,
        "light_seconds": 0,
        "deep_seconds": 0,
        "rem_seconds": 0,
    }


def _apply_transition(
    db_session: DbSession,
    user_id: str,
    state: SleepState,
    sleep_phase: SleepPhase,
    start_time: datetime,
    end_time: datetime,
    provider: str,
    uuid: str | None = None,
    source_name: str | None = None,
    device_model: str | None = None,
) -> SleepState:
    """Apply a transition to the sleep state."""

    last_start_timestamp = datetime.fromisoformat(state["last_start_timestamp"])
    last_end_timestamp = datetime.fromisoformat(state["last_end_timestamp"])

    delta_seconds = min(
        abs((start_time - last_start_timestamp).total_seconds()), abs((end_time - last_end_timestamp).total_seconds())
    )

    if delta_seconds > settings.sleep_end_gap_minutes * 60:
        finish_sleep(db_session, user_id, state)
        state = _create_new_sleep_state(start_time, end_time, uuid, provider, source_name, device_model)

    duration_seconds = (end_time - start_time).total_seconds()

    match sleep_phase:
        case SleepPhase.IN_BED:
            state["in_bed_seconds"] += duration_seconds
        case SleepPhase.AWAKE:
            state["awake_seconds"] += duration_seconds
        case SleepPhase.ASLEEP_LIGHT:
            state["light_seconds"] += duration_seconds
        case SleepPhase.ASLEEP_DEEP:
            state["deep_seconds"] += duration_seconds
        case SleepPhase.ASLEEP_REM:
            state["rem_seconds"] += duration_seconds
        case SleepPhase.SLEEPING:
            state["deep_seconds"] += duration_seconds
        case _:
            pass

    if end_time > datetime.fromisoformat(state["end_time"]):
        state["end_time"] = end_time.isoformat()
    elif start_time < datetime.fromisoformat(state["start_time"]):
        state["start_time"] = start_time.isoformat()

    state["last_start_timestamp"] = start_time.isoformat()
    state["last_end_timestamp"] = end_time.isoformat()

    return state


def handle_sleep_data(
    db_session: DbSession,
    request: SDKSyncRequest,
    user_id: str,
) -> None:
    """
    Process SDK sleep data and track sleep sessions using Redis state.

    Sleep sessions are tracked in Redis and automatically finalized to the database when
    a gap of more than 2 hours (configurable) is detected between consecutive sleep records.

    Handles bidirectional gaps between records - the service works fine whether the SDK
    sends records in chronological order or reverse chronological order.

    Args:
        db_session: Database session for persisting finalized sleep records
        request: Parsed SDKSyncRequest containing sleep records
        user_id: User identifier for associating sleep data

    Flow:
        - If no active session exists: Create new session in Redis (only for valid start states)
        - If active session exists: Check gap between last record's end and current record's start
          * Gap > 2 hours: Finalize existing session, start new one
          * Otherwise: Accumulate sleep stage durations in existing session
    """
    current_state = load_sleep_state(user_id)
    provider = request.provider
    for sjson in request.data.sleep:
        # Extract device info
        device_model, software_version, original_source_name = extract_device_info(sjson.source)

        sleep_phase = get_apple_sleep_phase(sjson.stage)

        if sleep_phase is None:
            continue

        if not current_state:
            if sleep_phase not in SLEEP_START_STATES:
                continue

            current_state = _create_new_sleep_state(
                sjson.startDate, sjson.endDate, sjson.id, provider, original_source_name, device_model
            )

        # Check if there's a gap between the last record's end and this record's start
        current_state = _apply_transition(
            db_session,
            user_id,
            current_state,
            sleep_phase,
            sjson.startDate,
            sjson.endDate,
            provider,
            sjson.id,
            original_source_name,
            device_model,
        )
        save_sleep_state(user_id, current_state)

    # import not at module level in order to avoid circular import
    from app.integrations.celery.tasks.finalize_stale_sleep_task import finalize_stale_sleeps

    # if we dont call the task, last sleep session in payload will stay
    # in redis until celery beat task runs
    finalize_stale_sleeps.delay()


def finish_sleep(db_session: DbSession, user_id: str, state: SleepState) -> None:
    """Finish a sleep session and save the record to the database."""

    end_time = datetime.fromisoformat(state["end_time"])
    start_time = datetime.fromisoformat(state["start_time"])

    total_duration = (end_time - start_time).total_seconds()
    total_sleep_seconds = state["light_seconds"] + state["deep_seconds"] + state["rem_seconds"]

    sleep_record = EventRecordCreate(
        id=uuid4(),
        external_id=state.get("uuid"),
        user_id=UUID(user_id),
        start_datetime=start_time,
        end_datetime=end_time,
        duration_seconds=int(total_duration),
        category="sleep",
        type="sleep_session",
        source_name=state.get("source_name") or "unknown",
        source=state.get("provider") or "unknown",
        device_model=state.get("device_model"),
    )

    detail = EventRecordDetailCreate(
        record_id=sleep_record.id,
        sleep_total_duration_minutes=total_sleep_seconds // 60,
        sleep_time_in_bed_minutes=state["in_bed_seconds"] // 60,
        sleep_deep_minutes=state["deep_seconds"] // 60,
        sleep_rem_minutes=state["rem_seconds"] // 60,
        sleep_light_minutes=state["light_seconds"] // 60,
        sleep_awake_minutes=state["awake_seconds"] // 60,
        sleep_efficiency_score=None,  # TODO: Implement efficiency score
        is_nap=False,  # TODO: Infer if nap, maybe from sleep length < 1 hour / 2 hours?
    )

    delete_sleep_state(user_id)

    try:
        created_or_existing_record = event_record_service.create(db_session, sleep_record)
        # Always use the returned record's ID (whether newly created or existing)
        detail_for_record = detail.model_copy(update={"record_id": created_or_existing_record.id})
        event_record_service.create_detail(db_session, detail_for_record, detail_type="sleep")
    except Exception as e:
        log_structured(
            logger,
            "error",
            f"Error saving sleep record {sleep_record.id} for user {user_id}: {e}",
            provider=state.get("provider") or "unknown",
            action="sleep_record_save_error",
            user_id=user_id,
            sleep_record_id=sleep_record.id,
            error=str(e),
        )
