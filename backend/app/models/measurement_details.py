from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.mappings import FKEventRecordDetail

from .event_record_detail import EventRecordDetail


class MeasurementDetails(EventRecordDetail):
    """Per-measurement details."""

    __tablename__ = "measurement_details"
    __mapper_args__ = {"polymorphic_identity": "measurement"}

    record_id: Mapped[FKEventRecordDetail]

    measurement_type: Mapped[str] = mapped_column(String(32))
    values: Mapped[dict] = mapped_column(JSONB)
