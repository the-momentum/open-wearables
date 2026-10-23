from datetime import date

from sqlalchemy import CheckConstraint
from sqlalchemy.orm import Mapped

from app.database import BaseDbModel
from app.mappings import PrimaryKey, bool_false


class ArchivalSetting(BaseDbModel):
    """Global data lifecycle settings, a singleton row (id=1 enforced by a CHECK constraint).

    - rollup_enabled: every 15 minutes, roll changed days of samples up into open_wearables day and session
      aggregates. Off by default.
    - delete_after_days: days before samples are deleted, rolled up first when rollup is on. NULL keeps them.
    - deleted_before: the local day before which retention has deleted samples; the rollup never recomputes
      those days or the sessions started on them, it only adds rows they lack.
    """

    __tablename__ = "archival_settings"
    __table_args__ = (CheckConstraint("id = 1", name="ck_archival_settings_singleton"),)

    id: Mapped[PrimaryKey[int]]
    rollup_enabled: Mapped[bool_false]
    delete_after_days: Mapped[int | None]
    deleted_before: Mapped[date | None]
