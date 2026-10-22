from sqlalchemy import CheckConstraint
from sqlalchemy.orm import Mapped

from app.database import BaseDbModel
from app.mappings import PrimaryKey, bool_true


class ArchivalSetting(BaseDbModel):
    """Global data lifecycle settings, a singleton row (id=1 enforced by a CHECK constraint).

    - rollup_enabled: every night, roll changed days of samples up into open_wearables day and session aggregates.
    - delete_after_days: days before samples are deleted, rolled up first when rollup is on. NULL keeps them.
    """

    __tablename__ = "archival_settings"
    __table_args__ = (CheckConstraint("id = 1", name="ck_archival_settings_singleton"),)

    id: Mapped[PrimaryKey[int]]
    rollup_enabled: Mapped[bool_true]
    delete_after_days: Mapped[int | None]
