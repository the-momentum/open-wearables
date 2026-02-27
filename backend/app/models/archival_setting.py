from sqlalchemy import CheckConstraint
from sqlalchemy.orm import Mapped

from app.database import BaseDbModel
from app.mappings import PrimaryKey


class ArchivalSetting(BaseDbModel):
    """Global data lifecycle settings for time-series archival and retention.

    Singleton table — exactly one row with id=1 enforced by a CHECK constraint.

    - archive_after_days: Days before live samples are aggregated into daily archive.
      NULL means archival is disabled.
    - delete_after_days: Days before archived data is permanently removed.
      NULL means data is kept indefinitely.
    """

    __tablename__ = "archival_settings"
    __table_args__ = (CheckConstraint("id = 1", name="ck_archival_settings_singleton"),)

    id: Mapped[PrimaryKey[int]]
    archive_after_days: Mapped[int | None]
    delete_after_days: Mapped[int | None]
