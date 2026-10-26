"""Service for data lifecycle management (rollup + retention)."""

from __future__ import annotations

import time
from collections import defaultdict
from collections.abc import Callable, Iterator
from datetime import date, timedelta, timezone
from itertools import batched
from logging import Logger, getLogger
from uuid import UUID

from celery.exceptions import SoftTimeLimitExceeded

from app.database import DbSession
from app.integrations import rollup_queue
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
from app.repositories.series_rollup_repository import SeriesRollupRepository
from app.schemas.utils import (
    ArchivalSettingRead,
    ArchivalSettingUpdate,
    ArchivalSettingWithEstimate,
    StorageEstimate,
)
from app.utils.exceptions import handle_exceptions
from app.utils.sentry_helpers import log_and_capture_error
from app.utils.structured_logging import log_structured

# Queued (data source, day) pairs taken off the queue at once.
ROLLUP_BATCH_SIZE = 500
# A source's queued days rolled up per commit: one month-long range scan at most.
ROLLUP_DAYS_PER_COMMIT = 31
# Local days a retention batch rolls up and deletes per commit: three days of 1 Hz data is a quarter million rows.
DELETE_DAYS_PER_BATCH = 3
# Data sources looked up at once by retention.
RETENTION_SOURCES_PER_QUERY = 50
_FIRST_ID = UUID(int=0)


class ArchivalService:
    """Orchestrates archival settings CRUD, storage estimates, and the daily archival job."""

    def __init__(self, log: Logger):
        self.logger = log
        self.settings_repo = ArchivalSettingRepository()
        self.archive_repo = DataPointSeriesArchiveRepository()
        self.rollup_repo = SeriesRollupRepository()

    # ── Settings CRUD ─────────────────────────────────────────────

    @handle_exceptions
    def get_settings(self, db: DbSession) -> ArchivalSettingWithEstimate:
        """Return current archival configuration together with table-size estimates."""
        setting = self.settings_repo.get(db)
        storage = self._get_storage(db, setting)
        return ArchivalSettingWithEstimate(
            settings=ArchivalSettingRead.model_validate(setting),
            storage=storage,
        )

    @handle_exceptions
    def update_settings(self, db: DbSession, update: ArchivalSettingUpdate) -> ArchivalSettingWithEstimate:
        """Persist new archival settings and return updated estimates."""
        setting = self.settings_repo.update(db, update.rollup_enabled, update.delete_after_days)
        storage = self._get_storage(db, setting)
        return ArchivalSettingWithEstimate(
            settings=ArchivalSettingRead.model_validate(setting),
            storage=storage,
        )

    # ── Daily job (called by Celery) ──────────────────────────────

    def run_daily_archival(self, db: DbSession) -> dict:
        """Roll up the days that changed since the last run, then apply retention.

        - Rollup on: every queued (data source, local day) gets its open_wearables day and session rows
          recomputed. Off: the queue is dropped.
        - Retention: samples of local days older than delete_after_days are deleted, rolled up first when
          rollup is on, so their days and sessions stay in the aggregate tables.

        Returns a summary dict for logging/monitoring.
        """
        setting = self.settings_repo.get(db)
        cutoff = date.today() - timedelta(days=setting.delete_after_days) if setting.delete_after_days else None
        frozen_before = setting.deleted_before
        summary = {"rolled_up_days": 0, "deleted_live_rows": 0}

        if setting.rollup_enabled:
            summary["rolled_up_days"] = self._roll_up_queued_days(db, cutoff, frozen_before)
        else:
            rollup_queue.clear_dirty_days()

        if cutoff is not None:
            deleted, complete = self._delete_before(db, cutoff, setting.rollup_enabled, frozen_before)
            summary["deleted_live_rows"] = deleted
            log_structured(
                self.logger,
                "info",
                f"Retention: deleted {deleted} live rows before {cutoff}",
                delete_after_days=setting.delete_after_days,
                deleted_live_rows=deleted,
            )
            # Coverage is trimmed, and the days frozen, only once nothing older than the cutoff is left.
            if complete:
                data_type_coverage_repository.trim_series_before(db, cutoff)
                self.settings_repo.mark_deleted_before(db, cutoff)

        return summary

    def _roll_up_queued_days(self, db: DbSession, cutoff: date | None, frozen_before: date | None) -> int:
        """Roll up queued days in batches until the queue is empty or the run's time is up."""
        rolled_up = 0
        started = time.monotonic()

        def out_of_time() -> bool:
            return time.monotonic() - started >= MAX_SECONDS_PER_RUN

        if recovered := rollup_queue.recover_dirty_days():
            log_structured(self.logger, "warning", f"Rollup: {recovered} days left by a run that died, queued again")
        while not out_of_time():
            batch = rollup_queue.pop_dirty_days(ROLLUP_BATCH_SIZE)
            if not batch:
                break
            rolled_up += self._roll_up_batch(db, batch, cutoff, frozen_before, out_of_time)
        log_structured(self.logger, "info", f"Rollup: {rolled_up} days", rolled_up_days=rolled_up)
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

        A source that fails is logged and its days dropped (the next write to them queues them again); when
        every source fails the cause is not the data, the batch goes back on the queue and the error propagates.
        """
        days_by_source: dict[UUID, list[date]] = defaultdict(list)
        for source_id, day in batch:
            # Retention deletes these days whole; a late sample would roll up only part of one.
            if cutoff is None or day >= cutoff:
                days_by_source[source_id].append(day)
        rolled_up, failed, left = 0, [], []
        try:
            for source_id, days in days_by_source.items():
                done = 0
                try:
                    for chunk in batched(sorted(days), ROLLUP_DAYS_PER_COMMIT):
                        if out_of_time():
                            break
                        self.rollup_repo.roll_up(db, source_id, list(chunk), frozen_before)
                        db.commit()
                        done += len(chunk)
                except SoftTimeLimitExceeded:
                    raise
                except Exception as exc:
                    db.rollback()
                    failed.append((source_id, days, exc))
                    continue
                rolled_up += done
                left.extend((source_id, day) for day in sorted(days)[done:])
        except SoftTimeLimitExceeded:
            # Killed next; what is committed stays, the rest is rolled up again by the next run.
            db.rollback()
            rollup_queue.requeue_dirty_days(batch)
            raise
        if failed and len(failed) == len(days_by_source):
            rollup_queue.requeue_dirty_days(batch)
            raise failed[0][2]
        for source_id, days, exc in failed:
            log_and_capture_error(
                exc,
                self.logger,
                "Rollup: skipped the days of a data source",
                extra={"data_source_id": str(source_id), "days": [day.isoformat() for day in days]},
            )
        rollup_queue.requeue_dirty_days(left)
        rollup_queue.finish_dirty_days(batch)
        return rolled_up

    def _delete_before(self, db: DbSession, cutoff: date, rollup: bool, frozen_before: date | None) -> BatchedRun:
        """Delete the samples of local days before ``cutoff``, rolled up first when ``rollup``; a source at a time,
        oldest days first, a few days per commit. Stops at the run's row or time budget; the next run goes on.

        A source that fails is logged and skipped, and the run then is not complete: its days stay unfrozen.
        """
        deleted, failed = 0, 0
        started = time.monotonic()

        def out_of_budget() -> bool:
            return deleted >= MAX_ROWS_PER_RUN or time.monotonic() - started >= MAX_SECONDS_PER_RUN

        before, after = utc_midnight(cutoff) + OFFSET_REACH, _FIRST_ID
        while sources := self.archive_repo.sources_with_samples_before(db, before, after, RETENTION_SOURCES_PER_QUERY):
            for source_id in sources:
                after = source_id
                try:
                    for rows in self._delete_source_before(db, source_id, cutoff, rollup, frozen_before):
                        deleted += rows
                        if out_of_budget():
                            return BatchedRun(deleted, complete=False)
                except SoftTimeLimitExceeded:
                    db.rollback()
                    raise
                except Exception as exc:
                    db.rollback()
                    failed += 1
                    log_and_capture_error(
                        exc, self.logger, "Retention: skipped a data source", extra={"data_source_id": str(source_id)}
                    )
                if out_of_budget():
                    return BatchedRun(deleted, complete=False)
        return BatchedRun(deleted, complete=not failed)

    def _delete_source_before(
        self, db: DbSession, source_id: UUID, cutoff: date, rollup: bool, frozen_before: date | None
    ) -> Iterator[int]:
        """The source's local days before ``cutoff``, oldest first, ``DELETE_DAYS_PER_BATCH`` at a time: rolled up,
        then deleted whole and committed. Yields the rows each batch deleted."""
        next_day = date.min
        while (earliest := self.archive_repo.earliest_sample(db, source_id)) is not None:
            # An offset puts a sample's local day at most one day before its UTC date.
            first = max(earliest.astimezone(timezone.utc).date() - timedelta(days=1), next_day)
            days = [day for n in range(DELETE_DAYS_PER_BATCH) if (day := first + timedelta(days=n)) < cutoff]
            if not days:
                return
            if rollup:
                # Every older day of the source is gone by now: a session begun before these days keeps its rows.
                frozen = max(frozen_before, days[0]) if frozen_before else days[0]
                self.rollup_repo.roll_up(db, source_id, days, frozen)
            rows = self.archive_repo.delete_days(db, source_id, days)
            db.commit()
            next_day = days[-1] + timedelta(days=1)
            yield rows

    # ── Private helpers ───────────────────────────────────────────

    def _get_storage(self, db: DbSession, setting: ArchivalSetting) -> StorageEstimate:
        raw = self.archive_repo.get_storage_estimate(db)

        raw["growth_class"] = "bounded" if setting.delete_after_days is not None else "linear"
        return StorageEstimate(**raw)


archival_service = ArchivalService(log=getLogger(__name__))
