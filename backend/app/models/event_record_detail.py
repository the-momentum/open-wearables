from datetime import datetime
from typing import ClassVar, Literal

from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import BaseDbModel
from app.mappings import FKEventRecord

DetailType = Literal["workout", "sleep", "menstrual_cycle"]


class EventRecordDetail(BaseDbModel):
    """Abstract base for per-event detail models.

    Each concrete subclass sets ``detail_type`` to its own discriminator. It is a
    ClassVar, not a mapped column: the table (and Python class) already encodes the
    type, so the value is derived in code rather than stored redundantly per row.
    The DETAIL_MODELS registry in app.models is built from these values.
    """

    __abstract__ = True

    detail_type: ClassVar[DetailType]

    record_id: Mapped[FKEventRecord]
    # Repeated as __abstract__ models don't inherit columns from their base classes
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
