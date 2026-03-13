import json
from datetime import datetime, timedelta, timezone
from logging import getLogger
from uuid import UUID, uuid4

from app.config import settings
from app.constants.series_types.apple import (
    SleepPhase,
    get_apple_sleep_phase,
)
from app.constants.sleep import SleepStageType
from app.database import DbSession
from app.integrations.redis_client import get_redis_client
from app.schemas import (
    EventRecordCreate,
    EventRecordDetailCreate,
    SDKSyncRequest,
)
from app.schemas.apple.healthkit.sleep_state import SLEEP_START_STATES, SleepState, SleepStateStage
from app.schemas.sleep import SleepStage
from app.services.apple.healthkit.device_resolution import extract_device_info
from app.services.event_record_service import event_record_service
from app.utils.structured_logging import log_structured

logger = getLogger(__name__)

_STAGE_TO_METRIC: dict[str, str] = {
    "awake": "awake_seconds",
    "sleeping": "sleeping_seconds",
    "light": "light_seconds",
    "deep": "deep_seconds",
    "rem": "rem_seconds",
}


def key(user_id: str) -> str:
    """Generate a key for the sleep state."""
    return f"sleep:active:{user_id}"


def active_users_key() -> str:
    """Generate a key for the active users."""
    return "sleep:active_users"


def load_sleep_state(user_id: str) -> SleepState | None:
    """Load the sleep state from Redis."""
    sleep_state_key = key(user_id)
    state = get_redis_client().get(sleep_state_key)
    if not state:
        return None
    try:
        if isinstance(state, bytes):
            state = state.decode("utf-8")
        return SleepState.model_validate_json(state)
    except Exception as e:
        logger.error(f"Failed to parse sleep state for user {user_id}: {e}")
        try:
            raw = json.loads(state)
            return SleepState.model_validate(raw)
        except Exception as fallback_e:
            logger.error(f"Legacy state migration failed for user {user_id}: {fallback_e}; session will be dropped")
            return None


def save_sleep_state(user_id: str, state: SleepState) -> None:
    get_redis_client().set(key(user_id), state.model_dump_json())
    get_redis_client().expire(key(user_id), settings.redis_sleep_ttl_seconds)
    get_redis_client().sadd(active_users_key(), user_id)


def delete_sleep_state(user_id: str) -> None:
    get_redis_client().delete(key(user_id))
    get_redis_client().srem(active_users_key(), user_id)


def _create_new_sleep_state(
    start_time: datetime,
    end_time: datetime,
    id: str | None = None,
    provider: str | None = None,
    source_name: str | None = None,
    device_model: str | None = None,
) -> SleepState:
    return SleepState(
        uuid=id or str(uuid4()),
        source_name=source_name or "unknown",
        device_model=device_model,
        provider=provider,
        start_time=start_time,
        end_time=end_time,
        last_start_timestamp=start_time,
        last_end_timestamp=end_time,
        in_bed_seconds=0,
        awake_seconds=0,
        sleeping_seconds=0,
        light_seconds=0,
        deep_seconds=0,
        rem_seconds=0,
        stages=[],
    )


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

    last_start_timestamp = state.last_start_timestamp
    last_end_timestamp = state.last_end_timestamp

    delta_seconds = min(
        abs((start_time - last_start_timestamp).total_seconds()), abs((end_time - last_end_timestamp).total_seconds())
    )

    if delta_seconds > settings.sleep_end_gap_minutes * 60:
        finish_sleep(db_session, user_id, state)
        state = _create_new_sleep_state(start_time, end_time, uuid, provider, source_name, device_model)

    duration_seconds = (end_time - start_time).total_seconds()

    stage_label: SleepStageType

    match sleep_phase:
        case SleepPhase.IN_BED:
            state.in_bed_seconds += duration_seconds
            stage_label = SleepStageType.IN_BED
        case SleepPhase.AWAKE:
            state.awake_seconds += duration_seconds
            stage_label = SleepStageType.AWAKE
        case SleepPhase.ASLEEP_LIGHT:
            state.light_seconds += duration_seconds
            stage_label = SleepStageType.LIGHT
        case SleepPhase.ASLEEP_DEEP:
            state.deep_seconds += duration_seconds
            stage_label = SleepStageType.DEEP
        case SleepPhase.SLEEPING:
            state.sleeping_seconds += duration_seconds
            stage_label = SleepStageType.SLEEPING
        case SleepPhase.ASLEEP_REM:
            state.rem_seconds += duration_seconds
            stage_label = SleepStageType.REM
        case _:
            stage_label = SleepStageType.UNKNOWN

    if end_time > state.end_time:
        state.end_time = end_time
    elif start_time < state.start_time:
        state.start_time = start_time

    state.last_start_timestamp = start_time
    state.last_end_timestamp = end_time

    state.stages.append(
        SleepStateStage(
            stage=stage_label,
            start_time=start_time,
            end_time=end_time,
        )
    )

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
        - Deduplicate incoming data based on start/end/stage/source
        - If no active session exists: Create new session in Redis (only for valid start states)
        - If active session exists: Check gap between last record's end and current record's start
          * Gap > 2 hours: Finalize existing session, start new one
          * Otherwise: Accumulate sleep stage durations in existing session
    """
    current_state = load_sleep_state(user_id)
    provider = request.provider

    # Deduplicate and sort
    seen = set()
    unique_data = []

    # Sort first by startDate to ensure chronological processing
    sorted_raw = sorted(request.data.sleep, key=lambda x: x.startDate)

    for item in sorted_raw:
        # Create a unique key for deduplication
        # SourceInfo is not hashable, use JSON dump
        source_key = item.source.model_dump_json() if item.source else None
        key_tuple = (item.startDate, item.endDate, item.stage, source_key)

        if key_tuple not in seen:
            seen.add(key_tuple)
            unique_data.append(item)

    for sjson in unique_data:
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

    # Finalize the remaining session synchronously if it is already stale.
    # With chronological sorting, the most recent night is always processed last
    # and left in Redis. If it ended more than sleep_end_gap_minutes ago it can
    # be persisted right away instead of waiting for the periodic Celery beat.
    if current_state:
        end_time = current_state.end_time
        if end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        if now - end_time >= timedelta(minutes=settings.sleep_end_gap_minutes):
            finish_sleep(db_session, user_id, current_state)
            current_state = None

    # import not at module level in order to avoid circular import
    from app.integrations.celery.tasks.finalize_stale_sleep_task import finalize_stale_sleeps

    # Dispatch async task for any other active users or if this session
    # was too fresh to finalize synchronously above.
    finalize_stale_sleeps.delay()


def _calculate_final_metrics(stages: list[SleepStateStage]) -> tuple[dict, list[SleepStage]]:
    """
    Recalculate metrics from stages, handling overlaps by prioritizing earlier segments.
    Returns (metrics_dict, cleaned_stages_list).

    Input stages are now list[SleepStateStage] Pydantic models with normalized stage values.
    """
    metrics = {
        "in_bed_seconds": 0,
        "awake_seconds": 0,
        "sleeping_seconds": 0,
        "light_seconds": 0,
        "deep_seconds": 0,
        "rem_seconds": 0,
    }

    # Determine processing strategy based on what stage types are present:
    # - Only in_bed (no sleeping/light/deep/rem): treat in_bed as sleeping (legacy devices)
    # - Detailed phases present (light/deep/rem): use only detailed + awake, drop sleeping wrapper
    # - Only sleeping (no detailed): use sleeping + awake as-is
    has_detailed = any(s.stage in ("light", "deep", "rem") for s in stages)
    has_sleep_data = any(s.stage in ("sleeping", "light", "deep", "rem") for s in stages)

    if not has_sleep_data:
        processable = [
            SleepStateStage(stage=SleepStageType.SLEEPING, start_time=s.start_time, end_time=s.end_time)
            if s.stage == "in_bed"
            else s
            for s in stages
            if s.stage != "unknown"
        ]
    elif has_detailed:
        processable = [s for s in stages if s.stage not in ("in_bed", "sleeping", "unknown")]
    else:
        processable = [s for s in stages if s.stage not in ("in_bed", "unknown")]

    sorted_processable = sorted(processable, key=lambda x: x.start_time)

    cleaned_stages: list[SleepStage] = []
    last_end = None

    for stage in sorted_processable:
        start = stage.start_time
        end = stage.end_time

        if last_end and start < last_end:
            start = last_end

        if start >= end:
            continue

        duration = (end - start).total_seconds()

        # Safe to access .stage (Pydantic model)
        phase_str = str(stage.stage)

        metric_key = _STAGE_TO_METRIC.get(phase_str)
        if metric_key:
            metrics[metric_key] += duration

        cleaned_stages.append(SleepStage(stage=SleepStageType(phase_str), start_time=start, end_time=end))
        last_end = end

    # 2. Process IN_BED duration separately (union of intervals)
    in_bed_raw = [s for s in stages if s.stage == "in_bed"]
    if in_bed_raw:
        sorted_in_bed = sorted(in_bed_raw, key=lambda x: x.start_time)
        current_start = None
        current_end = None

        for stage in sorted_in_bed:
            start = stage.start_time
            end = stage.end_time

            if current_start is None:
                current_start = start
                current_end = end
                continue

            if start < current_end:
                current_end = max(current_end, end)
            else:
                metrics["in_bed_seconds"] += (current_end - current_start).total_seconds()
                current_start = start
                current_end = end

        if current_start and current_end:
            metrics["in_bed_seconds"] += (current_end - current_start).total_seconds()
    else:
        metrics["in_bed_seconds"] = (
            metrics["awake_seconds"]
            + metrics["sleeping_seconds"]
            + metrics["light_seconds"]
            + metrics["deep_seconds"]
            + metrics["rem_seconds"]
        )

    return metrics, cleaned_stages


def finish_sleep(db_session: DbSession, user_id: str, state: SleepState) -> None:
    """Finish a sleep session and save the record to the database."""

    # Recalculate metrics from stages to handle overlaps/duplicates
    # state.stages is a list[SleepStateStage]
    metrics, cleaned_stages = _calculate_final_metrics(state.stages)

    if cleaned_stages:
        start_time = cleaned_stages[0].start_time
        end_time = cleaned_stages[-1].end_time
    else:
        end_time = state.end_time
        start_time = state.start_time

    total_duration = (end_time - start_time).total_seconds()
    total_sleep_seconds = (
        metrics["sleeping_seconds"] + metrics["light_seconds"] + metrics["deep_seconds"] + metrics["rem_seconds"]
    )

    sleep_record = EventRecordCreate(
        id=uuid4(),
        external_id=state.uuid,
        user_id=UUID(user_id),
        start_datetime=start_time,
        end_datetime=end_time,
        duration_seconds=int(total_duration),
        category="sleep",
        type="sleep_session",
        source_name=state.source_name or "unknown",
        source=state.provider or "unknown",
        device_model=state.device_model,
    )

    detail = EventRecordDetailCreate(
        record_id=sleep_record.id,
        sleep_total_duration_minutes=int(total_sleep_seconds // 60),
        sleep_time_in_bed_minutes=int(metrics["in_bed_seconds"] // 60),
        sleep_deep_minutes=int(metrics["deep_seconds"] // 60),
        sleep_rem_minutes=int(metrics["rem_seconds"] // 60),
        sleep_light_minutes=int(metrics["light_seconds"] // 60),
        sleep_awake_minutes=int(metrics["awake_seconds"] // 60),
        sleep_efficiency_score=None,  # TODO: Implement efficiency score
        is_nap=False,  # TODO: Infer if nap, maybe from sleep length < 1 hour / 2 hours?
        sleep_stages=cleaned_stages or None,
    )

    try:
        created_or_existing_record = event_record_service.create(db_session, sleep_record)
        # Always use the returned record's ID (whether newly created or existing)
        detail_for_record = detail.model_copy(update={"record_id": created_or_existing_record.id})
        event_record_service.create_detail(db_session, detail_for_record, detail_type="sleep")
        # Delete from Redis only after a successful DB write so a transient error
        # keeps the session available for the next periodic finalization attempt.
        delete_sleep_state(user_id)
    except Exception as e:
        log_structured(
            logger,
            "error",
            f"Error saving sleep record {sleep_record.id} for user {user_id}: {e}",
            provider=state.provider or "unknown",
            action="sleep_record_save_error",
            user_id=user_id,
            sleep_record_id=sleep_record.id,
            error=str(e),
        )
