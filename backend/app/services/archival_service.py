"""Service for data lifecycle management (rollup + retention)."""

from __future__ import annotations

import time
from collections import defaultdict
from collections.abc import Callable
from datetime import date, timedelta
from logging import Logger, getLogger
from uuid import UUID

from app.database import DbSession
from app.integrations import rollup_queue
from app.models.archival_setting import ArchivalSetting
from app.repositories.archival_repository import (
    MAX_SECONDS_PER_RUN,
    ArchivalSettingRepository,
    DataPointSeriesArchiveRepository,
)
from app.repositories.data_type_coverage_repository import data_type_coverage_repository
from app.repositories.series_rollup_repository import SeriesRollupRepository
from app.schemas.utils import (
    ArchivalSettingRead,
    ArchivalSettingUpdate,
    ArchivalSettingWithEstimate,
    StorageEstimate,
)
from app.utils.exceptions import handle_exceptions
from app.utils.structured_logging import log_structured

# Queued (data source, day) pairs taken per commit.
ROLLUP_BATCH_SIZE = 500


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
            before_delete = self._roll_up_before(cutoff, frozen_before) if setting.rollup_enabled else None
            deleted, complete = self.archive_repo.delete_live_before(db, cutoff, before_delete)
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
        if recovered := rollup_queue.recover_dirty_days():
            log_structured(self.logger, "warning", f"Rollup: {recovered} days left by a run that died, queued again")
        while time.monotonic() - started < MAX_SECONDS_PER_RUN:
            batch = rollup_queue.pop_dirty_days(ROLLUP_BATCH_SIZE)
            if not batch:
                break
            days_by_source: dict[UUID, list[date]] = defaultdict(list)
            for source_id, day in batch:
                # Retention deletes these days whole; a late sample would roll up only part of one.
                if cutoff is None or day >= cutoff:
                    days_by_source[source_id].append(day)
            try:
                for source_id, days in days_by_source.items():
                    self.rollup_repo.roll_up(db, source_id, days, frozen_before)
                db.commit()
                rolled_up += sum(len(days) for days in days_by_source.values())
            except Exception:
                db.rollback()
                rolled_up += self._roll_up_one_by_one(db, days_by_source, frozen_before, batch)
            rollup_queue.finish_dirty_days(batch)
        log_structured(self.logger, "info", f"Rollup: {rolled_up} days", rolled_up_days=rolled_up)
        return rolled_up

    def _roll_up_one_by_one(
        self,
        db: DbSession,
        days_by_source: dict[UUID, list[date]],
        frozen_before: date | None,
        batch: list[tuple[UUID, date]],
    ) -> int:
        """A batch that failed as a whole is retried per source, so one bad source cannot hold the queue.

        Its days are dropped with an error (the next write to them queues them again); when every source
        fails the cause is not the data, the batch goes back on the queue and the error propagates.
        """
        rolled_up, failed = 0, []
        for source_id, days in days_by_source.items():
            try:
                self.rollup_repo.roll_up(db, source_id, days, frozen_before)
                db.commit()
                rolled_up += len(days)
            except Exception as exc:
                db.rollback()
                failed.append((source_id, days, exc))
        if failed and len(failed) == len(days_by_source):
            rollup_queue.requeue_dirty_days(batch)
            raise failed[0][2]
        for source_id, days, exc in failed:
            log_structured(
                self.logger,
                "error",
                f"Rollup: skipped {len(days)} days of data source {source_id}: {exc!r}",
                data_source_id=str(source_id),
                days=[day.isoformat() for day in days],
            )
        return rolled_up

    def _roll_up_before(self, cutoff: date, frozen_before: date | None) -> Callable[[DbSession, UUID], None]:
        def roll_up(db: DbSession, source_id: UUID) -> None:
            days = self.rollup_repo.days_before(db, source_id, cutoff)
            self.rollup_repo.roll_up(db, source_id, days, frozen_before)

        return roll_up

    # ── Private helpers ───────────────────────────────────────────

    def _get_storage(self, db: DbSession, setting: ArchivalSetting) -> StorageEstimate:
        raw = self.archive_repo.get_storage_estimate(db)

        raw["growth_class"] = "bounded" if setting.delete_after_days is not None else "linear"
        return StorageEstimate(**raw)


archival_service = ArchivalService(log=getLogger(__name__))
