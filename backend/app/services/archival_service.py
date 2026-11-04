"""Service for data lifecycle management (rollup + retention)."""

from __future__ import annotations

import contextlib
import time
from collections import defaultdict
from collections.abc import Callable, Iterator
from datetime import date, timedelta, timezone
from itertools import batched
from uuid import UUID

from celery.exceptions import SoftTimeLimitExceeded

from app.config import settings
from app.database import DbSession
from app.integrations import rollup_queue
from app.models import DataSource
from app.models.archival_setting import ArchivalSetting
from app.repositories.archival_repository import (
    MAX_ROWS_PER_RUN,
    MAX_SECONDS_PER_RUN,
    ArchivalSettingRepository,
    BatchedRun,
    DataPointSeriesArchiveRepository,
)
from app.repositories.data_type_coverage_repository import data_type_coverage_repository
from app.repositories.local_day import OFFSET_REACH, utc_midnight
from app.repositories.repositories import SourceRanking
from app.repositories.series_reconcile_repository import SeriesReconcileRepository
from app.repositories.series_rollup_repository import SeriesRollupRepository
from app.schemas.utils import (
    ArchivalSettingRead,
    ArchivalSettingUpdate,
    ArchivalSettingWithEstimate,
    StorageEstimate,
)
from app.services.aggregate_backfill_service import aggregate_backfill_service
from app.services.priority_service import priority_service
from app.utils.exceptions import InvalidInputError
from app.utils.structured_logging import get_logger

logger = get_logger(__name__)

# Queued (data source, day) pairs taken off the queue at once.
ROLLUP_BATCH_SIZE = 500
# A source's queued days rolled up per commit: one month-long range scan at most.
ROLLUP_DAYS_PER_COMMIT = 31
# A 15-minute rollup run stops after this long, so a busy instance gets later summaries, not more load.
ROLLUP_SECONDS_PER_RUN = 60
# (user, day) pairs a reconcile run takes off its queue at a time.
RECONCILE_BATCH_SIZE = 200
# Stored merged rows a priority change deletes per commit, and the seconds one task run spends on it.
RECONCILE_DROP_BATCH = 5000
RECONCILE_DROP_SECONDS = 90
# Local days a retention batch rolls up and deletes per commit: three days of 1 Hz data is a quarter million rows.
DELETE_DAYS_PER_BATCH = 3
# Data sources looked up at once by retention.
RETENTION_SOURCES_PER_QUERY = 50
_FIRST_ID = UUID(int=0)


class ArchivalService:
    """Orchestrates archival settings CRUD, storage estimates, and the daily archival job."""

    def __init__(self):
        self.settings_repo = ArchivalSettingRepository()
        self.archive_repo = DataPointSeriesArchiveRepository()
        self.rollup_repo = SeriesRollupRepository()
        self.reconcile_repo = SeriesReconcileRepository()

    # ── Settings CRUD ─────────────────────────────────────────────

    def get_settings(self, db: DbSession) -> ArchivalSettingWithEstimate:
        """Return current archival configuration together with table-size estimates."""
        return self._settings_with_estimate(db, self.settings_repo.get(db))

    def update_settings(self, db: DbSession, update: ArchivalSettingUpdate) -> ArchivalSettingWithEstimate:
        """Persist new archival settings and return updated estimates; switching the history's rollup on starts
        the backfill that runs it, not waiting for the next restart or beat."""
        # Imported here: the task package imports this module.
        from app.integrations.celery.tasks.aggregate_backfill_task import run_aggregate_backfill

        new = update.applied_to(ArchivalSettingRead.model_validate(self.settings_repo.get(db)))
        if new.history_rollup_enabled and not new.rollup_enabled:
            raise InvalidInputError(
                "history_rollup_enabled needs rollup_enabled: the days after it would not be rolled up"
            )
        setting = self.settings_repo.update(db, new.rollup_enabled, new.history_rollup_enabled, new.delete_after_days)
        if setting.history_rollup_enabled and not aggregate_backfill_service.is_done(db):
            run_aggregate_backfill.delay()
        return self._settings_with_estimate(db, setting)

    def _settings_with_estimate(self, db: DbSession, setting: ArchivalSetting) -> ArchivalSettingWithEstimate:
        return ArchivalSettingWithEstimate(
            settings=ArchivalSettingRead.model_validate(setting),
            storage=self._get_storage(db, setting),
            history_rollup=aggregate_backfill_service.history_rollup_status(db),
        )

    # ── Daily job (called by Celery) ──────────────────────────────

    def roll_up_queued_days(
        self, db: DbSession, budget_seconds: float = ROLLUP_SECONDS_PER_RUN, reconcile: bool = True
    ) -> int:
        """Roll up the days queued since the last run, within ``budget_seconds``; the rest waits for the next run.

        Rollup on: every queued (data source, local day) gets its open_wearables day and session rows
        recomputed. Off: the queue is dropped. Runs every 15 minutes and before retention.

        With ``reconcile`` and reconcile on, a second phase then merges queued (user, day) pairs within its own
        RECONCILE_SECONDS_PER_RUN: the run takes at most both budgets, never one eating into the other.
        """
        setting = self.settings_repo.get(db)
        if not setting.rollup_enabled:
            rollup_queue.clear_dirty_days()
            return 0
        return self._roll_up_queued_days(db, self._cutoff(setting), setting.deleted_before, budget_seconds, reconcile)

    def run_daily_archival(self, db: DbSession) -> dict:
        """Roll up what is still queued, then apply retention.

        Retention: samples of local days older than delete_after_days are deleted, rolled up first when
        rollup is on, so their days and sessions stay in the aggregate tables.

        Returns a summary dict for logging/monitoring.
        """
        setting = self.settings_repo.get(db)
        cutoff = self._cutoff(setting)
        frozen_before = setting.deleted_before
        summary = {"rolled_up_days": 0, "deleted_live_rows": 0, "deleted_archive_rows": 0}
        try:
            summary["rolled_up_days"] = self.roll_up_queued_days(db, MAX_SECONDS_PER_RUN)
        except SoftTimeLimitExceeded:
            raise
        except Exception as exc:
            # Retention rolls up the days it deletes itself: a queue that fails must not hold it back.
            db.rollback()
            logger.error("Rollup: the queued days failed; retention goes on", exc_info=exc)

        # Old samples still hold day and session values the backfill has not copied yet.
        if cutoff is not None and not aggregate_backfill_service.is_done(db):
            logger.info("Retention: waiting for the aggregate backfill")
            cutoff = None

        if cutoff is not None:
            deleted, complete = self._delete_before(db, cutoff, setting.rollup_enabled, frozen_before)
            summary["deleted_live_rows"] = deleted
            logger.info(
                "Retention: deleted live rows",
                delete_after_days=setting.delete_after_days,
                cutoff=cutoff.isoformat(),
                deleted_live_rows=deleted,
            )
            summary["deleted_archive_rows"] = self._delete_archive_before(db, cutoff)
            # Coverage is trimmed, and the days frozen, only once nothing older than the cutoff is left.
            if complete:
                data_type_coverage_repository.trim_series_before(db, cutoff)
                self.settings_repo.mark_deleted_before(db, cutoff)
                with contextlib.suppress(Exception):
                    rollup_queue.clear_sources_deleted_before()

        return summary

    def _delete_archive_before(self, db: DbSession, cutoff: date) -> int:
        """The legacy archive's days before the cutoff, a batch per commit, within the run's row budget."""
        deleted = 0
        while deleted < MAX_ROWS_PER_RUN and (rows := self.archive_repo.delete_archive_before(db, cutoff, 10_000)):
            db.commit()
            deleted += rows
        return deleted

    @staticmethod
    def _cutoff(setting: ArchivalSetting) -> date | None:
        return date.today() - timedelta(days=setting.delete_after_days) if setting.delete_after_days else None

    def _roll_up_queued_days(
        self, db: DbSession, cutoff: date | None, frozen_before: date | None, budget_seconds: float, reconcile: bool
    ) -> int:
        """Roll up queued days in batches until the queue is empty or the budget is spent."""
        rolled_up = 0
        started = time.monotonic()

        def out_of_time() -> bool:
            return time.monotonic() - started >= budget_seconds

        if recovered := rollup_queue.recover_dirty_days():
            logger.warning("Rollup: days left by a run that died, queued again", recovered_days=recovered)
        while not out_of_time():
            batch = rollup_queue.pop_dirty_days(ROLLUP_BATCH_SIZE)
            if not batch:
                break
            rolled_up += self._roll_up_batch(db, batch, cutoff, frozen_before, out_of_time)
        logger.info("Rollup finished", rolled_up_days=rolled_up)
        if reconcile and settings.reconcile_enabled:
            # Its own budget after the rollup's, not what the rollup left: neither can starve the other.
            merged = self._reconcile_queued_days(db, frozen_before, settings.reconcile_seconds_per_run)
            logger.info("Reconcile finished", reconciled_days=merged)
        return rolled_up

    def _roll_up_batch(
        self,
        db: DbSession,
        batch: list[tuple[UUID, date]],
        cutoff: date | None,
        frozen_before: date | None,
        out_of_time: Callable[[], bool],
    ) -> int:
        """A source at a time, a month of its days per commit; the days the run has no time left for go back.
        With reconcile on, the recent days rolled up are queued to be merged across the user's sources.

        A source that fails is logged and its days dropped (the next write to them queues them again); when
        every source fails the cause is not the data, the batch goes back on the queue and the error propagates.
        """
        days_by_source: dict[UUID, list[date]] = defaultdict(list)
        for source_id, day in batch:
            # Retention deletes these days whole; a late sample would roll up only part of one.
            if cutoff is None or day >= cutoff:
                days_by_source[source_id].append(day)
        sources_by_user = self._sources_by_user(db, days_by_source)
        # Older days are merged only when a read asks for them: a history import must not merge years.
        stored_since = date.today() - timedelta(days=settings.reconcile_stored_days)
        to_reconcile: list[tuple[UUID, date]] = []
        rolled_up, failed, left = 0, [], []
        try:
            for user_id, source_ids in sources_by_user.items():
                done_days: set[date] = set()
                for source_id in source_ids:
                    days = days_by_source[source_id]
                    done = 0
                    try:
                        for chunk in batched(sorted(days), ROLLUP_DAYS_PER_COMMIT):
                            if out_of_time():
                                break
                            self.rollup_repo.roll_up(db, source_id, list(chunk), frozen_before)
                            db.commit()
                            done += len(chunk)
                            done_days.update(chunk)
                    except SoftTimeLimitExceeded:
                        raise
                    except Exception as exc:
                        db.rollback()
                        failed.append((source_id, days, exc))
                        continue
                    rolled_up += done
                    left.extend((source_id, day) for day in sorted(days)[done:])
                if settings.reconcile_enabled:
                    to_reconcile.extend((user_id, day) for day in done_days if day >= stored_since)
        except SoftTimeLimitExceeded:
            # Killed next; what is committed stays, the rest is rolled up again by the next run.
            db.rollback()
            rollup_queue.requeue_dirty_days(batch)
            raise
        if failed and len(failed) == len(days_by_source):
            rollup_queue.requeue_dirty_days(batch)
            raise failed[0][2]
        for source_id, days, exc in failed:
            logger.error(
                "Rollup: skipped the days of a data source",
                exc_info=exc,
                data_source_id=str(source_id),
                days=[day.isoformat() for day in days],
            )
        rollup_queue.requeue_dirty_days(left)
        rollup_queue.finish_dirty_days(batch)
        rollup_queue.queue_reconcile_days(to_reconcile)
        return rolled_up

    @staticmethod
    def _sources_by_user(db: DbSession, days_by_source: dict[UUID, list[date]]) -> dict[UUID, list[UUID]]:
        owners = db.query(DataSource.id, DataSource.user_id).filter(DataSource.id.in_(days_by_source)).all()
        sources_by_user: dict[UUID, list[UUID]] = defaultdict(list)
        for source_id, user_id in owners:
            sources_by_user[user_id].append(source_id)
        return sources_by_user

    def drop_reconciled_days(
        self, db: DbSession, budget_seconds: float = RECONCILE_DROP_SECONDS, batch: int = RECONCILE_DROP_BATCH
    ) -> tuple[int, bool]:
        """Delete stored merged rows from the retention cutoff on, a batch per commit; returns (rows, all gone).
        Rows before the cutoff stay: their samples are gone, so they could not be merged again."""
        since = self.settings_repo.deleted_before(db)
        started, dropped = time.monotonic(), 0
        while time.monotonic() - started < budget_seconds:
            deleted = self.reconcile_repo.delete_reconciled_rows(db, since, batch)
            db.commit()
            dropped += deleted
            if deleted < batch:
                return dropped, True
        return dropped, False

    def _reconcile_queued_days(self, db: DbSession, frozen_before: date | None, budget_seconds: float) -> int:
        """Merge and store the queued (user, day) pairs, newest days first, a month of a user's days per commit,
        within ``budget_seconds``; what is left stays queued for the next run. Returns the user days merged.

        A merge that fails is logged and its days are queued again once the run is done, not within it, so the
        run does not retry them over and over; the next run tries them again.
        """
        started = time.monotonic()

        def out_of_time() -> bool:
            return time.monotonic() - started >= budget_seconds

        # Before the first pop: a failing priorities query must not lose pairs already taken off the queue.
        ranking = priority_service.get_source_ranking(db)
        merged = 0
        failed: list[tuple[UUID, date]] = []
        while not out_of_time() and (batch := rollup_queue.pop_reconcile_days(RECONCILE_BATCH_SIZE)):
            days_by_user: dict[UUID, set[date]] = defaultdict(set)
            for user_id, day in batch:
                # Retention has emptied these days: they cannot be merged again, so their rows stay as they are.
                if frozen_before is None or day >= frozen_before:
                    days_by_user[user_id].add(day)
            left: list[tuple[UUID, date]] = []
            try:
                for user_id, days in days_by_user.items():
                    for chunk in batched(sorted(days, reverse=True), ROLLUP_DAYS_PER_COMMIT):
                        if out_of_time():
                            left.extend((user_id, day) for day in chunk)
                            continue
                        try:
                            self.reconcile_repo.reconcile(db, user_id, chunk, ranking)
                            db.commit()
                            merged += len(chunk)
                        except SoftTimeLimitExceeded:
                            raise
                        except Exception as exc:
                            db.rollback()
                            failed.extend((user_id, day) for day in chunk)
                            logger.error(
                                "Reconcile failed merging a user's sources, queued for the next run",
                                exc_info=exc,
                                user_id=str(user_id),
                                days=[day.isoformat() for day in chunk],
                            )
            except SoftTimeLimitExceeded:
                # Killed next; merging again what is already committed is harmless.
                db.rollback()
                rollup_queue.queue_reconcile_days([*batch, *failed])
                raise
            rollup_queue.queue_reconcile_days(left)
        rollup_queue.queue_reconcile_days(failed)
        return merged

    def _delete_before(self, db: DbSession, cutoff: date, rollup: bool, frozen_before: date | None) -> BatchedRun:
        """Delete the samples of local days before ``cutoff``, rolled up first when ``rollup``; a source at a time,
        oldest days first, a few days per commit. Stops at the run's row or time budget; the next run goes on.

        A source that fails is logged and skipped, and the run then is not complete: its days stay unfrozen.
        """
        deleted, failed = 0, 0
        started = time.monotonic()

        def out_of_budget() -> bool:
            return deleted >= MAX_ROWS_PER_RUN or time.monotonic() - started >= MAX_SECONDS_PER_RUN

        ranking = priority_service.get_source_ranking(db) if rollup and settings.reconcile_enabled else None
        before, after = utc_midnight(cutoff) + OFFSET_REACH, _FIRST_ID
        while sources := self.archive_repo.sources_with_samples_before(db, before, after, RETENTION_SOURCES_PER_QUERY):
            for source_id in sources:
                after = source_id
                try:
                    for rows in self._delete_source_before(db, source_id, cutoff, rollup, frozen_before, ranking):
                        deleted += rows
                        if out_of_budget():
                            return BatchedRun(deleted, complete=False)
                except SoftTimeLimitExceeded:
                    db.rollback()
                    raise
                except Exception as exc:
                    db.rollback()
                    failed += 1
                    logger.error("Retention: skipped a data source", exc_info=exc, data_source_id=str(source_id))
                if out_of_budget():
                    return BatchedRun(deleted, complete=False)
        return BatchedRun(deleted, complete=not failed)

    def _delete_source_before(
        self,
        db: DbSession,
        source_id: UUID,
        cutoff: date,
        rollup: bool,
        frozen_before: date | None,
        ranking: SourceRanking | None = None,
    ) -> Iterator[int]:
        """The source's local days before ``cutoff``, oldest first, ``DELETE_DAYS_PER_BATCH`` at a time: rolled up,
        then deleted whole and committed. Yields the rows each batch deleted.

        With ``ranking``, the user's sources are merged on the days first, while every source still has them: the
        first source's batch merges a day, later ones keep that row, as one of its sources is gone by then.
        """
        source = db.get(DataSource, source_id) if ranking is not None else None
        user_id = source.user_id if source is not None else None
        next_day = date.min
        # Days an earlier run deleted before it stopped: a sample arriving late for one of them must not
        # recompute its rows from that sample alone.
        source_frozen = self._source_deleted_before(source_id)
        while (earliest := self.archive_repo.earliest_sample(db, source_id)) is not None:
            # An offset puts a sample's local day at most one day before its UTC date.
            first = max(earliest.astimezone(timezone.utc).date() - timedelta(days=1), next_day)
            days = [day for n in range(DELETE_DAYS_PER_BATCH) if (day := first + timedelta(days=n)) < cutoff]
            if not days:
                return
            if rollup:
                # Every older day of the source is gone by now: a session begun before these days keeps its rows.
                frozen = max(day for day in (frozen_before, source_frozen, days[0]) if day is not None)
                self.rollup_repo.roll_up(db, source_id, days, frozen)
                # Only the days reconcile stores at all: older ones are merged when read, which retention ends.
                recent = [day for day in days if day >= date.today() - timedelta(days=settings.reconcile_stored_days)]
                if ranking is not None and user_id is not None and recent:
                    self.reconcile_repo.reconcile(db, user_id, recent, ranking, keep_existing=True)
            rows = self.archive_repo.delete_days(db, source_id, days)
            db.commit()
            next_day = days[-1] + timedelta(days=1)
            self._mark_source_deleted_before(source_id, next_day)
            source_frozen = max(source_frozen or next_day, next_day)
            yield rows

    def _source_deleted_before(self, source_id: UUID) -> date | None:
        try:
            return rollup_queue.source_deleted_before(source_id)
        except Exception as exc:
            logger.error("Retention: could not read a source's deleted days", exc_info=exc)
            return None

    def _mark_source_deleted_before(self, source_id: UUID, day: date) -> None:
        try:
            rollup_queue.mark_source_deleted_before(source_id, day)
        except Exception as exc:
            logger.error("Retention: could not record a source's deleted days", exc_info=exc)

    # ── Private helpers ───────────────────────────────────────────

    def _get_storage(self, db: DbSession, setting: ArchivalSetting) -> StorageEstimate:
        raw = self.archive_repo.get_storage_estimate(db)

        if setting.delete_after_days is None:
            raw["growth_class"] = "linear"
        else:
            # Deleted samples leave their rolled-up days behind, which keep accumulating.
            raw["growth_class"] = "linear_efficient" if setting.rollup_enabled else "bounded"
        return StorageEstimate(**raw)


archival_service = ArchivalService()
