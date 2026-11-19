import contextlib
import time
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from logging import getLogger
from uuid import UUID, uuid4

from sqlalchemy import delete, select, text

from app.config import settings
from app.constants.series_types.sdk import (
    SleepPhase,
    get_apple_sleep_phase,
)
from app.constants.sleep import SleepStageType
from app.database import DbSession, engine
from app.integrations.redis_client import get_redis_client
from app.models.sleep_session import SleepSession
from app.schemas.model_crud.activities import (
    EventRecordCreate,
    EventRecordDetailCreate,
    SleepStage,
)
from app.schemas.providers.mobile_sdk import (
    SLEEP_START_STATES,
    SleepState,
    SleepStateStage,
)
from app.schemas.providers.mobile_sdk import (
    SyncRequest as SDKSyncRequest,
)
from app.services.apple.healthkit.device_resolution import extract_device_info
from app.services.event_record_service import event_record_service
from app.utils.sentry_helpers import log_and_capture_error
from app.utils.structured_logging import log_structured

logger = getLogger(__name__)

_STAGE_TO_METRIC: dict[str, str] = {
    "awake": "awake_seconds",
    "sleeping": "sleeping_seconds",
    "light": "light_seconds",
    "deep": "deep_seconds",
    "rem": "rem_seconds",
}


def _use_postgres() -> bool:
    """Whether in-progress sleep sessions live in Postgres instead of Redis.

    Inline mode (``task_execution_mode="inline"``) is the Redis-free deployment
    profile, so sleep state is stored in the ``sleep_session`` table and serialized
    with a Postgres advisory lock. Default (``"celery"``) keeps the Redis backend.
    """
    return settings.task_execution_mode == "inline"


def key(user_id: str) -> str:
    """Generate a key for the sleep state."""
    return f"sleep:active:{user_id}"


def active_users_key() -> str:
    """Generate a key for the active users."""
    return "sleep:active_users"


def load_sleep_state(db_session: DbSession, user_id: str) -> SleepState | None:
    """Load the in-progress sleep state for a user (Postgres or Redis)."""
    if _use_postgres():
        row = db_session.get(SleepSession, UUID(str(user_id)))
        if row is None:
            return None
        try:
            return SleepState.model_validate(row.state)
        except Exception as e:
            logger.error(f"Failed to parse sleep state for user {user_id}: {e}; session will be dropped")
            return None

    state = get_redis_client().get(key(user_id))
    if not state:
        return None
    try:
        if isinstance(state, bytes):
            state = state.decode("utf-8")
        return SleepState.model_validate_json(state)
    except Exception as e:
        logger.error(f"Failed to parse sleep state for user {user_id}: {e}; session will be dropped")
        return None


def save_sleep_state(db_session: DbSession, user_id: str, state: SleepState) -> None:
    if _use_postgres():
        user_uuid = UUID(str(user_id))
        payload = state.model_dump(mode="json")
        row = db_session.get(SleepSession, user_uuid)
        if row is None:
            row = SleepSession(
                user_id=user_uuid,
                state=payload,
                start_time=state.start_time,
                end_time=state.end_time,
            )
            db_session.add(row)
        else:
            row.state = payload
            row.start_time = state.start_time
            row.end_time = state.end_time
        db_session.commit()
        return

    get_redis_client().set(key(user_id), state.model_dump_json())
    get_redis_client().expire(key(user_id), settings.redis_sleep_ttl_seconds)
    get_redis_client().sadd(active_users_key(), user_id)


def delete_sleep_state(db_session: DbSession, user_id: str) -> None:
    if _use_postgres():
        db_session.execute(delete(SleepSession).where(SleepSession.user_id == UUID(str(user_id))))
        db_session.commit()
        return

    get_redis_client().delete(key(user_id))
    get_redis_client().srem(active_users_key(), user_id)


def iter_active_user_ids(db_session: DbSession) -> list[str]:
    """Return the user ids that currently have an in-progress sleep session."""
    if _use_postgres():
        rows = db_session.execute(select(SleepSession.user_id)).scalars().all()
        return [str(uid) for uid in rows]

    return [str(uid) for uid in get_redis_client().smembers(active_users_key())]


def _advisory_lock_param(user_id: str) -> str:
    return f"sleep:{user_id}"


@contextlib.contextmanager
def user_sleep_lock(user_id: str, wait_seconds: float = 15.0) -> Iterator[bool]:
    """Serialize concurrent sleep processing for a single user.

    Yields ``True`` if the lock was acquired, ``False`` otherwise (caller should
    skip the batch). In Postgres mode a session-level advisory lock is held on a
    dedicated connection so it survives the commits ``finish_sleep`` performs on
    the request's session; it is always released in ``finally``. In Redis mode the
    existing redis-py lock is used.
    """
    if _use_postgres():
        conn = engine.connect()
        # Non-Postgres dialects (e.g. SQLite in some tests) have no advisory locks.
        if conn.dialect.name != "postgresql":
            try:
                yield True
            finally:
                conn.close()
            return

        acquired = False
        param = {"k": _advisory_lock_param(user_id)}
        try:
            deadline = time.monotonic() + wait_seconds
            while True:
                acquired = bool(conn.execute(text("SELECT pg_try_advisory_lock(hashtext(:k)::bigint)"), param).scalar())
                if acquired or time.monotonic() >= deadline:
                    break
                time.sleep(0.25)
            yield acquired
        finally:
            if acquired:
                with contextlib.suppress(Exception):
                    conn.execute(text("SELECT pg_advisory_unlock(hashtext(:k)::bigint)"), param)
            conn.close()
        return

    lock = get_redis_client().lock(f"sleep:lock:{user_id}", timeout=30, blocking_timeout=wait_seconds)
    acquired = False
    try:
        acquired = bool(lock.acquire(blocking=wait_seconds > 0))
        yield acquired
    finally:
        if acquired:
            with contextlib.suppress(Exception):
                lock.release()


def finalize_stale_sleep_for_user(db_session: DbSession, user_id: UUID | str) -> bool:
    """Finalize one user's in-progress sleep session if it has gone stale.

    This is used by read paths in inline/serverless deployments where there is no
    Celery beat to wake up later and close a quiet sleep session.
    """
    user_id_str = str(user_id)
    try:
        with user_sleep_lock(user_id_str, wait_seconds=0) as acquired:
            if not acquired:
                return False

            state = load_sleep_state(db_session, user_id_str)
            if not state:
                return False

            session_end = state.end_time
            if session_end.tzinfo is None:
                session_end = session_end.replace(tzinfo=timezone.utc)

            if datetime.now(timezone.utc) - session_end < timedelta(minutes=settings.sleep_end_gap_minutes):
                return False

            finish_sleep(db_session, user_id_str, state)
            return True
    except Exception as e:
        log_and_capture_error(
            e,
            logger,
            f"Failed to finalize stale sleep session for user {user_id_str}: {e}",
            extra={"action": "sleep_finalize_stale_on_read_failed", "user_id": user_id_str},
        )
        return False


def _create_new_sleep_state(
    start_time: datetime,
    end_time: datetime,
    id: str | None = None,
    provider: str | None = None,
    source_name: str | None = None,
    device_model: str | None = None,
    zone_offset: str | None = None,
) -> SleepState:
    return SleepState(
        uuid=id or str(uuid4()),
        source_name=source_name or "unknown",
        device_model=device_model,
        provider=provider,
        zone_offset=zone_offset,
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
    zone_offset: str | None = None,
) -> SleepState:
    """Apply a transition to the sleep state."""

    # Compute the gap using session boundaries (start_time / end_time) rather than
    # the timestamps of the last-processed sample.  This correctly handles payloads
    # that arrive out of chronological order: a sample that chains directly onto an
    # earlier part of the night will have a near-zero distance to the session window
    # even if it was enqueued after a later-night payload was already processed.
    if start_time <= state.end_time and end_time >= state.start_time:
        # New sample overlaps with the current session window → same session.
        delta_seconds = 0.0
    elif end_time <= state.start_time:
        # New sample is entirely before the session start.
        delta_seconds = (state.start_time - end_time).total_seconds()
    else:
        # New sample is entirely after the session end.
        delta_seconds = (start_time - state.end_time).total_seconds()

    if delta_seconds > settings.sleep_end_gap_minutes * 60:
        finish_sleep(db_session, user_id, state)
        state = _create_new_sleep_state(start_time, end_time, uuid, provider, source_name, device_model, zone_offset)

    if zone_offset and not state.zone_offset:
        state.zone_offset = zone_offset

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
    Process SDK sleep data and track in-progress sleep sessions.

    Sleep sessions are tracked in the configured backend (Postgres in inline mode,
    Redis otherwise) and automatically finalized to the database when a gap of more
    than 2 hours (configurable) is detected between consecutive sleep records.

    A per-user lock serializes concurrent calls so that parallel uploads
    (e.g. from a bulk historical upload) accumulate stages into the same session
    instead of overwriting each other's state.

    Stale detection uses ``end_time`` (the last sleep-sample timestamp).  When a bulk
    historical upload finalizes a session whose ``end_time`` is in the past, the new
    session is merged with any adjacent record already in the database, so consecutive
    payloads within the same night are combined into a single session rather than being
    stored as separate fragments.

    Args:
        db_session: Database session for persisting finalized sleep records
        request: Parsed SDKSyncRequest containing sleep records
        user_id: User identifier for associating sleep data

    Flow:
        - Acquire a per-user lock to prevent concurrent state corruption
        - Deduplicate incoming data based on start/end/stage/source
        - If no active session exists: Create new session (only for valid start states)
        - If active session exists: Check gap between new sample and the session window
          * Gap > 2 hours: Finalize existing session, start new one
          * Otherwise: Accumulate sleep stage durations in existing session
        - Persist state once after the whole batch; finalize stale sessions
    """
    with user_sleep_lock(user_id, wait_seconds=15) as acquired:
        if not acquired:
            logger.warning("Could not acquire sleep processing lock for user %s; skipping batch", user_id)
            return

        current_state = load_sleep_state(db_session, user_id)
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
                    sjson.startDate,
                    sjson.endDate,
                    sjson.id,
                    provider,
                    original_source_name,
                    device_model,
                    sjson.zoneOffset,
                )

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
                sjson.zoneOffset,
            )

        # Persist the accumulated state only once after processing the entire batch
        if current_state:
            save_sleep_state(db_session, user_id, current_state)

        # Finalise synchronously if the session is already stale.  Historical
        # uploads have end_time far in the past so this fires immediately, but
        # finish_sleep now merges the result with any adjacent record already in
        # the DB — so each payload extends the growing record rather than
        # creating a separate session.
        if current_state:
            session_end = current_state.end_time
            if session_end.tzinfo is None:
                session_end = session_end.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) - session_end >= timedelta(minutes=settings.sleep_end_gap_minutes):
                finish_sleep(db_session, user_id, current_state)

    # In celery mode, dispatch the stale-sleep task so sessions that have gone quiet
    # (including other users' sessions) are finalised promptly without waiting for the
    # next beat. In inline mode there is no beat: a user's own stale session is
    # finalised by the synchronous check above on their next upload.
    if settings.task_execution_mode != "inline":
        # import not at module level in order to avoid circular import
        from app.integrations.celery.tasks.finalize_stale_sleep_task import finalize_stale_sleeps

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

            if start < current_end:  # ty:ignore[unsupported-operator]
                current_end = max(current_end, end)  # ty:ignore[invalid-argument-type]
            else:
                metrics["in_bed_seconds"] += (current_end - current_start).total_seconds()  # ty:ignore[unsupported-operator]
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
    """Finish a sleep session and save the record to the database.

    Before creating a new record the function checks whether an existing adjacent
    sleep session is already in the database (gap ≤ ``sleep_end_gap_minutes``).
    When found, the two sessions are merged: the existing record is deleted and a
    new record is created from the combined stages.  This handles the Apple SDK
    pattern of sending one night's sleep as many consecutive small payloads — each
    payload is finalized immediately (historical data is available right away) and
    each merge step extends the accumulated DB record until the whole night is
    represented as a single session.
    """

    # Recalculate metrics from stages to handle overlaps/duplicates
    # state.stages is a list[SleepStateStage]
    metrics, cleaned_stages = _calculate_final_metrics(state.stages)

    if cleaned_stages:
        start_time = cleaned_stages[0].start_time
        end_time = cleaned_stages[-1].end_time
    else:
        end_time = state.end_time
        start_time = state.start_time

    # --- Merge with an adjacent existing session if one exists ---
    source_for_lookup = state.source_name if state.source_name != "unknown" else None
    adjacent = event_record_service.find_adjacent_sleep_record(
        db_session,
        UUID(user_id),
        start_time,
        end_time,
        settings.sleep_end_gap_minutes,
        source=source_for_lookup,
        provider=state.provider,
    )

    if adjacent is not None:
        # Deserialise the stored stages back to SleepStateStage so we can feed
        # them into _calculate_final_metrics together with the new stages.
        existing_state_stages: list[SleepStateStage] = []
        if adjacent.detail and adjacent.detail.sleep_stages:
            for s in adjacent.detail.sleep_stages:
                with contextlib.suppress(Exception):
                    existing_state_stages.append(SleepStateStage.model_validate(s))

        # Recalculate from the union of both stage lists.
        metrics, cleaned_stages = _calculate_final_metrics(existing_state_stages + state.stages)

        # Expand the session window to cover both records.
        start_time = min(adjacent.start_datetime, start_time)
        end_time = max(adjacent.end_datetime, end_time)
        if cleaned_stages:
            start_time = min(start_time, cleaned_stages[0].start_time)
            end_time = max(end_time, cleaned_stages[-1].end_time)

        # Remove the old record before creating the merged one (cascade deletes detail).
        event_record_service.delete(db_session, adjacent.id)

    # ---

    total_duration = (end_time - start_time).total_seconds()
    total_sleep_seconds = (
        metrics["sleeping_seconds"] + metrics["light_seconds"] + metrics["deep_seconds"] + metrics["rem_seconds"]
    )
    time_in_bed_seconds = max(metrics["in_bed_seconds"], total_sleep_seconds + metrics["awake_seconds"])
    sleep_efficiency = (
        Decimal(str(total_sleep_seconds / time_in_bed_seconds * 100)) if time_in_bed_seconds > 0 else None
    )

    sleep_record = EventRecordCreate(
        id=uuid4(),
        external_id=state.uuid,
        user_id=UUID(user_id),
        start_datetime=start_time,
        end_datetime=end_time,
        zone_offset=state.zone_offset,
        duration_seconds=int(total_duration),
        category="sleep",
        type="sleep_session",
        source_name=state.source_name or "unknown",
        source=source_for_lookup,
        provider=state.provider,
        device_model=state.device_model,
    )

    detail = EventRecordDetailCreate(
        record_id=sleep_record.id,
        sleep_total_duration_minutes=int(total_sleep_seconds // 60),
        sleep_time_in_bed_minutes=int(time_in_bed_seconds // 60),
        sleep_deep_minutes=int(metrics["deep_seconds"] // 60),
        sleep_rem_minutes=int(metrics["rem_seconds"] // 60),
        sleep_light_minutes=int(metrics["light_seconds"] // 60),
        sleep_awake_minutes=int(metrics["awake_seconds"] // 60),
        sleep_efficiency_score=sleep_efficiency,
        is_nap=False,  # TODO: Infer if nap, maybe from sleep length < 1 hour / 2 hours?
        sleep_stages=cleaned_stages or None,
    )

    try:
        created_or_existing_record = event_record_service.create(db_session, sleep_record)
        # Always use the returned record's ID (whether newly created or existing)
        detail_for_record = detail.model_copy(update={"record_id": created_or_existing_record.id})
        event_record_service.create_detail(db_session, detail_for_record, detail_type="sleep")
        # Delete the in-progress session only after a successful DB write so a transient
        # error keeps the session available for the next finalization attempt.
        delete_sleep_state(db_session, user_id)
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
