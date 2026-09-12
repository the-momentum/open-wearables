from contextlib import suppress
from datetime import datetime, timedelta, timezone
from logging import getLogger
from typing import Any, cast
from uuid import UUID, uuid4

from celery import current_task, shared_task

from app.config import settings
from app.database import SessionLocal
from app.repositories.provider_settings_repository import ProviderSettingsRepository
from app.repositories.user_connection_repository import UserConnectionRepository
from app.schemas.auth import LiveSyncMode
from app.schemas.responses.upload import ProviderSyncResult, SyncVendorDataResult
from app.schemas.sync_status import (
    DataTypeKind,
    DataTypeOutcome,
    SyncScope,
    SyncSource,
    SyncStage,
    SyncStatus,
)
from app.services.providers.factory import ProviderFactory
from app.services.sync_cancel_service import SyncCancelledError, clear_cancel, is_cancel_requested
from app.services.sync_coordination import release_primary, release_stale_primary, try_become_primary
from app.services.sync_status_service import (
    emit_sync_cancelled,
    emit_sync_completed,
    emit_sync_failed,
    emit_sync_progress,
    emit_sync_started,
    new_run_id,
    run_status_from,
    try_record_data_types,
)
from app.utils.config_utils import format_duration
from app.utils.context import trace_id_var
from app.utils.memory_guard import check_memory_budget
from app.utils.sentry_helpers import log_and_capture_error
from app.utils.structured_logging import log_structured
from app.utils.sync_params import build_sync_params

logger = getLogger(__name__)

# Keys of load_and_save_all results that are not record counts, so they are not data
# types either. Whoop reports a partial sleep fetch this way.
_NON_COUNT_RESULT_KEYS = frozenset({"sleep_partial"})


def _current_task_id() -> str | None:
    """This task's Celery id, or None outside a worker (eager mode, tests).

    Read from current_task rather than binding the task, so the public
    signature stays identical to upstream's and the reconcile stays a
    one-line diff instead of a changed call convention.
    """
    try:
        request = current_task.request if current_task else None
        return str(request.id) if request is not None and request.id else None
    except Exception:  # noqa: BLE001 - never let telemetry break a sync
        return None


def _emit_sync_status(fn: Any, /, *args: Any, **kwargs: Any) -> None:
    """Best-effort sync status emission — never aborts the sync flow."""
    try:
        fn(*args, **kwargs)
    except Exception as exc:
        log_and_capture_error(
            exc,
            logger,
            "Failed to emit sync status event",
            extra={"detail": str(exc)},
        )


def _include_in_periodic_pull(caps: Any, live_sync_mode: LiveSyncMode | None, is_historical: bool) -> bool:
    """True if the provider should be included in this REST pull run.

    Historical backfill always uses REST for all rest_pull providers.
    For live sync, only providers explicitly in pull mode are polled periodically.
    """
    if not caps.rest_pull:
        return False
    if is_historical:
        return True
    return live_sync_mode == LiveSyncMode.PULL


# acks_late: a provider sync can run for hours on a historical backfill, and
# Celery's default acks the message on RECEIPT — so a worker killed by a rollout
# loses the task outright with no redelivery, leaving its sync:status:run:*
# record frozen at in_progress until its TTL. That is what shows in the UI as a
# "hanging sync": the run is not slow, it no longer exists. Two year-long
# backfills were orphaned this way on 2026-08-29.
#
# Safe for THIS task specifically because ingest is upsert-based (ON CONFLICT on
# uq_data_point_series_source_type_time), so a redelivered sync re-runs without
# duplicating rows. Set per-task rather than globally for that reason — the
# guarantee is a property of this task, not of the app.
#
# Pairs with broker_transport_options["visibility_timeout"] and
# worker_prefetch_multiplier in celery/core.py; see the comments there.
@shared_task(acks_late=True)
def sync_vendor_data(
    user_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
    providers: list[str] | None = None,
    is_historical: bool = False,
    _skip_linked_fan_out: bool = False,
    _linked_primary_user_id: str | None = None,
) -> dict[str, Any]:
    """
    Synchronize workout/exercise/activity data from all providers the user is connected to.

    Args:
        user_id: UUID of the user to sync data for
        start_date: ISO 8601 date string for start of sync period.
            When None, defaults to connection.last_synced_at (or now for first-ever sync)
            so that live syncs never re-pull history.
        end_date: ISO 8601 date string for end of sync period (None = current time)
        providers: Optional list of provider names to sync (None = all active providers)
        is_historical: When True, skips updating last_synced_at so the live-sync
            cursor is not clobbered by a user-initiated historical pull.
        _skip_linked_fan_out: Internal flag set to True when this task was triggered
            by another profile's fan-out.  Prevents infinite fan-out loops.

    Returns:
        dict with sync results per provider
    """
    factory = ProviderFactory()
    user_connection_repo = UserConnectionRepository()
    provider_settings_repo = ProviderSettingsRepository()
    trace_id = str(uuid4())[:8]
    trace_id_var.set(trace_id)

    try:
        user_uuid = UUID(user_id)
    except ValueError as e:
        log_structured(
            logger,
            "error",
            f"Invalid user_id format: {user_id}",
            task="sync_vendor_data",
            user_id=user_id,
        )
        log_and_capture_error(
            e,
            logger,
            f"Invalid user_id format: {user_id}",
            extra={"user_id": user_id, "task": "sync_vendor_data", "trace_id": trace_id},
        )
        return SyncVendorDataResult(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            errors={"user_id": f"Invalid UUID format: {str(e)}"},
        ).model_dump()

    result = SyncVendorDataResult(
        user_id=user_uuid,
        start_date=start_date,
        end_date=end_date,
    )

    with SessionLocal() as db:
        try:
            connections = user_connection_repo.get_all_active_by_user(db, user_uuid)

            if providers:
                connections = [c for c in connections if c.provider in providers]

            # Load provider settings once (live_sync_mode per provider).
            provider_settings = provider_settings_repo.get_all(db)

            # Only sync providers in pull mode. Push-only providers (Garmin, Apple SDK)
            # deliver data via webhooks/SDK and must not be polled here.
            # Historical backfill always uses REST regardless of live_sync_mode.
            connections = [
                c
                for c in connections
                if _include_in_periodic_pull(
                    factory.get_provider(c.provider).capabilities,
                    provider_settings[c.provider].live_sync_mode
                    if c.provider in provider_settings
                    else LiveSyncMode.PULL,
                    is_historical,
                )
            ]

            if not connections:
                log_structured(
                    logger,
                    "info",
                    f"No active connections found for user {user_id}",
                    task="sync_vendor_data",
                    user_id=user_id,
                )
                result.message = "No active provider connections found"
                return result.model_dump()

            log_structured(
                logger,
                "info",
                f"Found {len(connections)} active connections for user {user_id}",
                task="sync_vendor_data",
                user_id=user_id,
            )

            for connection in connections:
                provider_name = connection.provider
                log_structured(
                    logger,
                    "info",
                    f"Syncing data from {provider_name} for user {user_id}",
                    provider=provider_name,
                    task="sync_vendor_data",
                    user_id=user_id,
                )

                run_id = new_run_id(prefix="pull")

                # FORK DELTA: guard the worker before starting another provider.
                #
                # The threads pool shares one process across every task, so RSS
                # does NOT reset between them and a previous chunk's footprint
                # is still present here. A SIGKILL runs no Python at all: no
                # terminal event, no ack, and with acks_late the message is
                # redelivered every visibility_timeout to OOM again. Failing
                # here instead keeps that loop from ever starting, and the
                # exception reaches the handler below which reports the run.
                check_memory_budget(f"before {provider_name} sync")

                primary_uuid: UUID | None = None
                if _linked_primary_user_id:
                    with suppress(ValueError):
                        primary_uuid = UUID(_linked_primary_user_id)
                sync_source = (
                    SyncSource.LINKED_ACCOUNT
                    if _linked_primary_user_id
                    else (SyncSource.BACKFILL if is_historical else SyncSource.PULL)
                )
                sync_scope = SyncScope.HISTORICAL if is_historical else SyncScope.LIVE

                # If this provider account is shared across OW profiles, only one
                # should make the API call at a time.  The first to acquire the lock
                # is primary; concurrent duplicates skip and wait for the fan-out.
                # Fan-out tasks (_skip_linked_fan_out=True) bypass this check entirely.
                shared_token: str = ""
                if connection.provider_user_id and not _skip_linked_fan_out:
                    is_pull_primary, shared_token, existing_primary = try_become_primary(
                        provider_name, connection.provider_user_id, user_uuid, scope="pull"
                    )
                    if not is_pull_primary and existing_primary:
                        # If the lock holder no longer has an active connection (e.g. user
                        # deleted), the lock is stale and will never be released naturally.
                        # Steal it so this profile can become primary.
                        active = user_connection_repo.get_active_connection(db, existing_primary, provider_name)
                        if not active:
                            log_structured(
                                logger,
                                "info",
                                f"Stealing stale {provider_name} primary lock — holder has no active connection",
                                provider=provider_name,
                                task="sync_vendor_data",
                                user_id=user_id,
                                stale_primary_user_id=str(existing_primary),
                            )
                            release_stale_primary(provider_name, connection.provider_user_id, scope="pull")
                            is_pull_primary, shared_token, existing_primary = try_become_primary(
                                provider_name, connection.provider_user_id, user_uuid, scope="pull"
                            )

                    if not is_pull_primary:
                        log_structured(
                            logger,
                            "info",
                            f"Skipping {provider_name} pull — another linked profile is syncing",
                            provider=provider_name,
                            task="sync_vendor_data",
                            user_id=user_id,
                            primary_user_id=str(existing_primary) if existing_primary else None,
                        )
                        # No sync status event here — the primary will trigger a fan-out
                        # task for this profile that emits a LINKED_ACCOUNT completed event
                        # once the actual data delivery is done.  A pre-emptive event here
                        # would show up as a duplicate in the sync log.
                        if not is_historical:
                            user_connection_repo.update_last_synced_at(db, connection)
                        result.providers_synced[provider_name] = ProviderSyncResult(
                            success=True, params={"linked_account": True}
                        )
                        continue

                _emit_sync_status(
                    emit_sync_started,
                    user_uuid,
                    provider_name,
                    sync_source,
                    scope=sync_scope,
                    run_id=run_id,
                    message=(
                        f"Historical sync from {provider_name} started"
                        if is_historical
                        else f"Live sync from {provider_name} started"
                    ),
                    primary_user_id=primary_uuid,
                    metadata={
                        "trace_id": trace_id,
                        "is_historical": is_historical,
                        "start_date": start_date,
                        "end_date": end_date,
                        # FORK DELTA: carried so a cancel request can be matched
                        # to the Celery task, and so a liveness check can tell a
                        # run that is still executing from one whose worker died.
                        # metadata is a free-form dict on SyncStatusEvent, so
                        # this needs no schema change.
                        "task_id": _current_task_id(),
                    },
                )

                # FORK DELTA: cooperative cancellation checkpoint.
                # Checked per provider rather than mid-provider so a cancelled
                # run never leaves one provider half-written; see
                # sync_cancel_service for why this is a flag and not a revoke.
                if is_cancel_requested(run_id):
                    raise SyncCancelledError(f"Sync cancelled by request before {provider_name} fetch")

                try:
                    strategy = factory.get_provider(provider_name)
                    provider_result = ProviderSyncResult(success=True, params={})

                    # New-vs-updated split for the sync-log (timeseries upserts report it
                    # via WriteCounts). items_processed is derived from these so the headline
                    # count always equals "X new, Y updated".
                    pull_inserted = 0
                    pull_updated = 0
                    data_type_outcomes: list[DataTypeOutcome] = []
                    applied_lookback: timedelta | None = None  # set when the lookback actually widened the window

                    # Resolve effective start: explicit arg > last_synced_at > now
                    # This ensures live syncs never re-pull history.
                    effective_start = start_date
                    if effective_start is None:
                        last = connection.last_synced_at
                        if last is not None:
                            if last.tzinfo is None:
                                last = last.replace(tzinfo=timezone.utc)
                            # Optional trailing lookback so late provider revisions get
                            # re-fetched (live pull only; capped by max_historical_days).
                            lookback = settings.pull_sync_lookback
                            if lookback is not None and not is_historical:
                                last -= lookback
                                max_days = strategy.capabilities.max_historical_days
                                if max_days is not None:
                                    last = max(last, datetime.now(timezone.utc) - timedelta(days=max_days))
                                applied_lookback = lookback
                            effective_start = last.isoformat()
                        else:
                            # First ever sync — start from now, historical must be explicit
                            effective_start = datetime.now(timezone.utc).isoformat()

                    # effective_start is always set above; parse into datetime objects
                    start_dt = datetime.fromisoformat(effective_start.replace("Z", "+00:00"))
                    end_dt = datetime.now(timezone.utc)
                    if end_date:
                        with suppress(ValueError):
                            end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))

                    # Sync workouts
                    if strategy.workouts:
                        params = build_sync_params(effective_start, end_date)
                        _emit_sync_status(
                            emit_sync_progress,
                            user_uuid,
                            provider_name,
                            sync_source,
                            run_id=run_id,
                            stage=SyncStage.FETCHING,
                            message=f"Fetching workouts from {provider_name}",
                        )
                        try:
                            success = strategy.workouts.load_data(db, user_uuid, **params)
                            provider_result.params["workouts"] = {"success": success, **params}
                            # load_data returns how many workouts it wrote, not a boolean.
                            data_type_outcomes.append(
                                DataTypeOutcome(
                                    data_type="workouts",
                                    kind=DataTypeKind.TASK,
                                    native_type="workouts",
                                    status=SyncStatus.SUCCESS if success else SyncStatus.SKIPPED,
                                    items_inserted=int(success or 0),
                                    # Workouts are event records, which do not report a
                                    # written span, so coverage stays unknown here.
                                )
                            )
                        except Exception as e:
                            log_structured(
                                logger,
                                "warning",
                                f"Workouts sync failed for {provider_name}: {e}",
                                provider=provider_name,
                                task="sync_vendor_data",
                                user_id=user_id,
                            )
                            log_and_capture_error(
                                e,
                                logger,
                                f"Workouts sync failed for {provider_name}: {e}",
                                extra={
                                    "user_id": user_id,
                                    "provider": provider_name,
                                    "task": "sync_vendor_data",
                                    "trace_id": trace_id,
                                },
                            )
                            provider_result.params["workouts"] = {"success": False, "error": str(e)}
                            data_type_outcomes.append(
                                DataTypeOutcome(
                                    data_type="workouts",
                                    kind=DataTypeKind.TASK,
                                    native_type="workouts",
                                    status=SyncStatus.FAILED,
                                    error=str(e),
                                )
                            )

                    # Sync 247 data (sleep, recovery, activity) and SAVE to database
                    if hasattr(strategy, "data_247") and strategy.data_247:
                        # Determine if this is first sync (for API compatibility with providers)
                        is_first_sync = connection.last_synced_at is None

                        _emit_sync_status(
                            emit_sync_progress,
                            user_uuid,
                            provider_name,
                            sync_source,
                            run_id=run_id,
                            stage=SyncStage.FETCHING,
                            message=f"Fetching 24/7 data (sleep / recovery / activity) from {provider_name}",
                        )

                        try:
                            # Use load_and_save_all if available (saves data to DB)
                            # Otherwise fallback to load_all_247_data (just returns data)
                            provider_any = cast(Any, strategy.data_247)
                            if hasattr(provider_any, "load_and_save_all"):
                                results_247 = provider_any.load_and_save_all(
                                    db,
                                    user_uuid,
                                    start_time=start_dt,
                                    end_time=end_dt,
                                    is_first_sync=is_first_sync,
                                )
                                provider_result.params["data_247"] = {"success": True, "saved": True, **results_247}
                                for _task, _count in results_247.items():
                                    # Some providers put flags in the same dict as counts.
                                    if _task in _NON_COUNT_RESULT_KEYS:
                                        continue
                                    pull_inserted += getattr(_count, "inserted", 0)
                                    pull_updated += getattr(_count, "updated", 0)
                                    # Pull reports per fetch task, not per series type: one
                                    # task can write several types and returns a single count.
                                    data_type_outcomes.append(
                                        DataTypeOutcome(
                                            data_type=_task,
                                            kind=DataTypeKind.TASK,
                                            native_type=_task,
                                            status=SyncStatus.SUCCESS
                                            if getattr(_count, "inserted", _count) or getattr(_count, "updated", 0)
                                            else SyncStatus.SKIPPED,
                                            items_inserted=getattr(_count, "inserted", 0),
                                            items_updated=getattr(_count, "updated", 0),
                                            # A plain int only says how many rows the provider
                                            # saved, with no insert/update split to record.
                                            reported_records=None if hasattr(_count, "inserted") else int(_count),
                                            # Span of the rows written, not the window asked
                                            # for. Absent when the task wrote nothing.
                                            covered_start=getattr(_count, "covered_start", None),
                                            covered_end=getattr(_count, "covered_end", None),
                                        )
                                    )
                            else:
                                results_247 = strategy.data_247.load_all_247_data(
                                    db,
                                    user_uuid,
                                    start_time=start_dt,
                                    end_time=end_dt,
                                )
                                provider_result.params["data_247"] = {"success": True, "saved": False, **results_247}
                            log_structured(
                                logger,
                                "info",
                                f"247 data synced for {provider_name}: {results_247}",
                                provider=provider_name,
                                task="sync_vendor_data",
                                user_id=user_id,
                            )
                        except Exception as e:
                            log_structured(
                                logger,
                                "warning",
                                f"247 data sync failed for {provider_name}: {e}",
                                provider=provider_name,
                                task="sync_vendor_data",
                                user_id=user_id,
                            )
                            log_and_capture_error(
                                e,
                                logger,
                                f"247 data sync failed for {provider_name}: {e}",
                                extra={
                                    "user_id": user_id,
                                    "provider": provider_name,
                                    "task": "sync_vendor_data",
                                    "trace_id": trace_id,
                                },
                            )
                            provider_result.params["data_247"] = {"success": False, "error": str(e)}
                            data_type_outcomes.append(
                                DataTypeOutcome(
                                    data_type="data_247",
                                    kind=DataTypeKind.TASK,
                                    native_type="data_247",
                                    status=SyncStatus.FAILED,
                                    error=str(e),
                                )
                            )

                    # Only advance the live-sync cursor when nothing failed. Bumping it after a
                    # failed sub-sync would silently skip the un-synced window on the next run.
                    provider_failed = any(
                        isinstance(r, dict) and r.get("success") is False for r in provider_result.params.values()
                    )
                    if not is_historical and not provider_failed:
                        user_connection_repo.update_last_synced_at(db, connection)

                    if shared_token and connection.provider_user_id:
                        release_primary(
                            provider_name, connection.provider_user_id, user_uuid, shared_token, scope="pull"
                        )
                        # Fan-out: trigger sync for every other OW profile sharing this
                        # provider account so they receive the same data.
                        linked_connections = user_connection_repo.get_all_by_provider_user_id(
                            db, provider_name, connection.provider_user_id
                        )
                        for linked_conn in linked_connections:
                            if linked_conn.user_id == user_uuid:
                                continue
                            log_structured(
                                logger,
                                "info",
                                f"Fanning out {provider_name} sync to linked profile",
                                provider=provider_name,
                                task="sync_vendor_data",
                                user_id=user_id,
                                linked_user_id=str(linked_conn.user_id),
                            )
                            sync_vendor_data.apply_async(
                                kwargs={
                                    "user_id": str(linked_conn.user_id),
                                    "start_date": start_date,
                                    "end_date": end_date,
                                    "providers": [provider_name],
                                    "is_historical": is_historical,
                                    "_skip_linked_fan_out": True,
                                    "_linked_primary_user_id": user_id,
                                }
                            )

                    result.providers_synced[provider_name] = provider_result
                    log_structured(
                        logger,
                        "info",
                        f"Successfully synced {provider_name} for user {user_id}",
                        provider=provider_name,
                        task="sync_vendor_data",
                        user_id=user_id,
                        effective_start=effective_start,
                        lookback=format_duration(settings.pull_sync_lookback) if settings.pull_sync_lookback else None,
                    )

                    final_status = run_status_from(data_type_outcomes)

                    if final_status == SyncStatus.FAILED:
                        _emit_sync_status(
                            emit_sync_failed,
                            user_uuid,
                            provider_name,
                            sync_source,
                            scope=sync_scope,
                            run_id=run_id,
                            error="All sync sub-tasks failed",
                            message=f"Sync from {provider_name} failed",
                            primary_user_id=primary_uuid,
                            metadata={"is_historical": is_historical, "params": provider_result.params},
                        )
                    else:
                        # inserted/updated are run-level totals across all timeseries
                        # types: a single sync (historical included) can have both —
                        # e.g. new days inserted while overlapping days are refreshed.
                        completed_metadata: dict[str, Any] = {
                            "is_historical": is_historical,
                            "params": provider_result.params,
                        }
                        # SKIPPED means every task found nothing to fetch, which is the
                        # normal outcome of a live sync and not an error.
                        match final_status:
                            case SyncStatus.SUCCESS:
                                completed_message = f"Sync from {provider_name} completed"
                            case SyncStatus.SKIPPED:
                                completed_message = f"Sync from {provider_name} completed, nothing new"
                            case _:
                                completed_message = f"Sync from {provider_name} completed with errors"
                        if pull_inserted or pull_updated:
                            completed_metadata["inserted"] = pull_inserted
                            completed_metadata["updated"] = pull_updated
                            completed_message += f" · {pull_inserted} new, {pull_updated} updated"
                        if applied_lookback is not None:
                            lookback_label = format_duration(applied_lookback)
                            completed_metadata["lookback"] = lookback_label
                            completed_message += f" · lookback {lookback_label}"
                        _emit_sync_status(
                            emit_sync_completed,
                            user_uuid,
                            provider_name,
                            sync_source,
                            scope=sync_scope,
                            run_id=run_id,
                            status=final_status,
                            message=completed_message,
                            items_processed=pull_inserted + pull_updated,
                            primary_user_id=primary_uuid,
                            metadata=completed_metadata,
                            window_start=start_dt,
                            window_end=end_dt,
                        )
                        try_record_data_types(run_id, data_type_outcomes, scope=sync_scope)

                # FORK DELTA: a cancelled run is a reported outcome, not a
                # failure. Ordered before the generic handler because
                # SyncCancelled is an Exception and would otherwise be swallowed
                # by it and reported as an error the user did not cause.
                except SyncCancelledError as e:
                    if shared_token and connection.provider_user_id:
                        release_primary(
                            provider_name, connection.provider_user_id, user_uuid, shared_token, scope="pull"
                        )
                    clear_cancel(run_id)
                    _emit_sync_status(
                        emit_sync_cancelled,
                        user_uuid,
                        provider_name,
                        sync_source,
                        scope=sync_scope,
                        run_id=run_id,
                        message=str(e),
                        metadata={"is_historical": is_historical},
                    )
                    log_structured(
                        logger,
                        "info",
                        f"Sync from {provider_name} cancelled by request",
                        provider=provider_name,
                        task="sync_vendor_data",
                        user_id=user_id,
                        run_id=run_id,
                    )
                    # Recorded as an outcome, not an error: result.errors drives
                    # the task's failure reporting and a user-requested stop is
                    # not a failure of the sync.
                    result.providers_synced[provider_name] = ProviderSyncResult(
                        success=False, params={"cancelled": True}
                    )
                    continue

                except Exception as e:
                    if shared_token and connection.provider_user_id:
                        release_primary(
                            provider_name, connection.provider_user_id, user_uuid, shared_token, scope="pull"
                        )
                    _emit_sync_status(
                        emit_sync_failed,
                        user_uuid,
                        provider_name,
                        sync_source,
                        scope=sync_scope,
                        run_id=run_id,
                        error=str(e),
                        message=f"Sync from {provider_name} failed",
                        metadata={"is_historical": is_historical},
                    )
                    log_and_capture_error(
                        e,
                        logger,
                        f"Error syncing {provider_name} for user {user_id}: {str(e)}",
                        extra={
                            "user_id": user_id,
                            "provider": provider_name,
                            "task": "sync_vendor_data",
                            "trace_id": trace_id,
                        },
                    )
                    result.errors[provider_name] = str(e)
                    continue

            return result.model_dump()

        except Exception as e:
            log_and_capture_error(
                e,
                logger,
                f"Error processing user {user_id}: {str(e)}",
                extra={"user_id": user_id, "task": "sync_vendor_data", "trace_id": trace_id},
            )
            result.errors["general"] = str(e)
            return result.model_dump()
