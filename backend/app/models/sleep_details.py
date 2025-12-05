from app.mappings import FKEventRecordDetail, numeric_10_3
from sqlalchemy.orm import Mapped
from .event_record_detail import EventRecordDetail


class SleepDetails(EventRecordDetail):
    """Per-sleep aggregates and metrics."""

    __tablename__ = "sleep_details"
    __mapper_args__ = {"polymorphic_identity": "sleep"}

    record_id: Mapped[FKEventRecordDetail]

    sleep_total_duration_minutes: Mapped[numeric_10_3 | None]
    sleep_time_in_bed_minutes: Mapped[numeric_10_3 | None]
    sleep_efficiency_score: Mapped[numeric_10_3 | None]
    sleep_deep_minutes: Mapped[numeric_10_3 | None]
    sleep_rem_minutes: Mapped[numeric_10_3 | None]
    sleep_light_minutes: Mapped[numeric_10_3 | None]
    sleep_awake_minutes: Mapped[numeric_10_3 | None]

