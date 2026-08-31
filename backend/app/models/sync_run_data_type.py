from datetime import datetime

from sqlalchemy import Index
from sqlalchemy.orm import Mapped

from app.database import BaseDbModel
from app.mappings import FKSyncRun, PrimaryKey, int_zero, str_32, str_64, str_100
from app.schemas.enums import SeriesType
from app.schemas.sync_status import SyncStatus


class SyncRunDataType(BaseDbModel):
    """Outcome of a single data type within one sync run.

    data_type is the canonical SeriesType slug where the provider's key maps to one,
    otherwise the provider's own string, so an unmapped key is still recorded rather than
    rejected. An unmapped key showing up is the signal that a mapping is missing.

    reported_records is what the provider or device claimed it sent, which is not the same
    as what we wrote. The gap between it and items_inserted + items_updated is the
    completeness signal.
    """

    __tablename__ = "sync_run_data_type"
    __table_args__ = (Index("ix_sync_run_data_type_type_status", "data_type", "status"),)

    run_id: Mapped[FKSyncRun]
    data_type: Mapped[PrimaryKey[str_64]]
    # series | score | profile | event -- not every provider key is a series
    # (Oura's daily_sleep is a score, personal_info is profile data).
    kind: Mapped[str_32]

    status: Mapped[SyncStatus]
    native_type: Mapped[str_100 | None]

    reported_records: Mapped[int | None]
    items_inserted: Mapped[int_zero]
    items_updated: Mapped[int_zero]

    covered_start: Mapped[datetime | None]
    covered_end: Mapped[datetime | None]

    started_at: Mapped[datetime | None]
    ended_at: Mapped[datetime | None]
    # The SDK measures this from the start of the whole run, so every type in a run
    # reports the same value. Unusable until that is fixed SDK-side.
    duration_ms: Mapped[int | None]

    error_code: Mapped[str_64 | None]
    error: Mapped[str | None]
    attempt: Mapped[int_zero]

    updated_at: Mapped[datetime]

    @property
    def series_type(self) -> SeriesType | None:
        """The canonical series type, or None when the provider's key has no mapping."""
        try:
            return SeriesType(self.data_type)
        except ValueError:
            return None
