from sqlalchemy.orm import Mapped

from app.database import BaseDbModel
from app.mappings import FKEventRecord, str_32


class EventRecordDetail(BaseDbModel):
    """Abstract polymorphic base for per-event detail models."""

    __abstract__ = True

    record_id: Mapped[FKEventRecord]
    detail_type: Mapped[str_32]
