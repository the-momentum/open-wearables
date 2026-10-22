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
        summary = {"rolled_up_days": 0, "deleted_live_rows": 0}

        if setting.rollup_enabled:
            summary["rolled_up_days"] = self._roll_up_queued_days(db, cutoff)
        else:
            rollup_queue.clear_dirty_days()

        if cutoff is not None:
            before_delete = self._roll_up_before(cutoff) if setting.rollup_enabled else None
            deleted, complete = self.archive_repo.delete_live_before(db, cutoff, before_delete)
            summary["deleted_live_rows"] = deleted
            log_structured(
                self.logger,
                "info",
                f"Retention: deleted {deleted} live rows before {cutoff}",
                delete_after_days=setting.delete_after_days,
                deleted_live_rows=deleted,
            )
            # Coverage is trimmed only once nothing older than the cutoff is left.
            if complete:
                data_type_coverage_repository.trim_series_before(db, cutoff)

        return summary

    def _roll_up_queued_days(self, db: DbSession, cutoff: date | None) -> int:
        """Roll up queued days in batches until the queue is empty or the run's time is up."""
        rolled_up = 0
        started = time.monotonic()
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
                    self.rollup_repo.roll_up(db, source_id, days)
                db.commit()
            except Exception:
                db.rollback()
                rollup_queue.requeue_dirty_days(batch)
                raise
            rolled_up += sum(len(days) for days in days_by_source.values())
        log_structured(self.logger, "info", f"Rollup: {rolled_up} days", rolled_up_days=rolled_up)
        return rolled_up

    def _roll_up_before(self, cutoff: date) -> Callable[[DbSession, UUID], None]:
        def roll_up(db: DbSession, source_id: UUID) -> None:
            self.rollup_repo.roll_up(db, source_id, self.rollup_repo.days_before(db, source_id, cutoff))

        return roll_up

    # ── Private helpers ───────────────────────────────────────────

    def _get_storage(self, db: DbSession, setting: ArchivalSetting) -> StorageEstimate:
        raw = self.archive_repo.get_storage_estimate(db)

        raw["growth_class"] = "bounded" if setting.delete_after_days is not None else "linear"
        return StorageEstimate(**raw)


archival_service = ArchivalService(log=getLogger(__name__))
