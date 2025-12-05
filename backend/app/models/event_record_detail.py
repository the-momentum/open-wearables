from sqlalchemy.orm import Mapped

from app.database import BaseDbModel
from app.mappings import FKEventRecord, str_64


class EventRecordDetail(BaseDbModel):
    """Base polymorphic detail model used by specific aggregates (workout, sleep, etc.)."""

    __tablename__ = "event_record_detail"

    record_id: Mapped[FKEventRecord]
    detail_type: Mapped[str_64]

    __mapper_args__ = {
        "polymorphic_on": "detail_type",
        "polymorphic_identity": "base",
    }

