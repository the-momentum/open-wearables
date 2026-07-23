from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import BaseDbModel
from app.mappings import FKEventRecord


class EventRecordDetail(BaseDbModel):
    """Abstract polymorphic base for per-event detail models."""

    __abstract__ = True

    record_id: Mapped[FKEventRecord]
    # Repeated as __abstract__ models don't inherit columns from their base classes
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
