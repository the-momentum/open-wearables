"""Service for data lifecycle management (archival + retention)."""

from __future__ import annotations

from datetime import date, timedelta
from logging import Logger, getLogger

from app.database import DbSession
from app.models import AppSetting
from app.repositories.app_settings_repository import AppSettingRepository
from app.repositories.archival_repository import DataPointSeriesArchiveRepository
from app.schemas.utils import StorageEstimate
from app.utils.exceptions import handle_exceptions
from app.utils.structured_logging import log_structured


class ArchivalService:
    """Storage estimates and the daily archival + retention job (settings live in app_settings)."""

    def __init__(self, log: Logger):
        self.logger = log
        self.settings_repo = AppSettingRepository()
        self.archive_repo = DataPointSeriesArchiveRepository()

    @handle_exceptions
    def get_storage(self, db: DbSession) -> StorageEstimate:
        """Return current table-size estimates and growth projection."""
        return self._get_storage(db, self.settings_repo.get(db))

    # ── Daily job (called by Celery) ──────────────────────────────

    def run_daily_archival(self, db: DbSession) -> dict:
        """Execute archival + retention cleanup.

        Policies are independent:
        - Archival only → aggregate old live rows into archive.
        - Retention only → delete old live rows directly.
        - Both (archive < delete) → archive first, then delete old archive rows.
        - Both (delete <= archive) → archival is ineffective (data deleted
          before reaching archive threshold), behaves as retention-only.

        Returns a summary dict for logging/monitoring.
        """
        setting = self.settings_repo.get(db)
        today = date.today()
        summary: dict = {"archived_rows": 0, "deleted_rows": 0, "deleted_live_rows": 0}

        archive_days = setting.archive_after_days
        delete_days = setting.delete_after_days
        both_active = archive_days is not None and delete_days is not None

        # When both are active and delete threshold is at or below the archive
        # threshold, archival is effectively disabled — data will be deleted
        # before it's old enough to be archived. Treat as retention-only.
        archival_effective = archive_days is not None and (not both_active or delete_days > archive_days)

        # ── Archival step ──
        if archival_effective and archive_days is not None:
            cutoff = today - timedelta(days=archive_days)
            log_structured(
                self.logger,
                "info",
                f"Archival: aggregating live rows before {cutoff}",
                archive_after_days=archive_days,
                cutoff_date=str(cutoff),
            )
            archived = self.archive_repo.archive_data_before(db, cutoff)
            summary["archived_rows"] = archived
            log_structured(
                self.logger,
                "info",
                f"Archival: processed {archived} live rows",
                archived_rows=archived,
            )

        # ── Retention step ──
        if delete_days is not None:
            cutoff = today - timedelta(days=delete_days)

            if archival_effective:
                # Archive is active → delete only from archive table
                log_structured(
                    self.logger,
                    "info",
                    f"Retention: deleting archive rows before {cutoff}",
                    delete_after_days=delete_days,
                    cutoff_date=str(cutoff),
                )
                deleted = self.archive_repo.delete_archive_before(db, cutoff)
                summary["deleted_rows"] = deleted
                log_structured(
                    self.logger,
                    "info",
                    f"Retention: deleted {deleted} archive rows",
                    deleted_rows=deleted,
                )
            else:
                # No (effective) archival → delete directly from live table
                log_structured(
                    self.logger,
                    "info",
                    f"Retention: deleting live rows before {cutoff}",
                    delete_after_days=delete_days,
                    cutoff_date=str(cutoff),
                )
                deleted = self.archive_repo.delete_live_before(db, cutoff)
                summary["deleted_live_rows"] = deleted
                log_structured(
                    self.logger,
                    "info",
                    f"Retention: deleted {deleted} live rows",
                    deleted_live_rows=deleted,
                )
                # Also clean residual archive rows if any exist
                deleted_archive = self.archive_repo.delete_archive_before(db, cutoff)
                if deleted_archive:
                    summary["deleted_rows"] = deleted_archive

        return summary

    # ── Private helpers ───────────────────────────────────────────

    def _get_storage(self, db: DbSession, setting: AppSetting) -> StorageEstimate:
        raw = self.archive_repo.get_storage_estimate(db)

        if setting.delete_after_days is not None:
            growth_class = "bounded"
        elif setting.archive_after_days is not None:
            growth_class = "linear_efficient"
        else:
            growth_class = "linear"

        raw["growth_class"] = growth_class
        return StorageEstimate(**raw)


archival_service = ArchivalService(log=getLogger(__name__))
