from sqlalchemy.orm import Mapped, mapped_column

from app.mappings import FKEventRecordDetail, numeric_5_2

from .event_record_detail import EventRecordDetail


class SleepDetails(EventRecordDetail):
    """Per-sleep aggregates and metrics."""

    __tablename__ = "sleep_details"
    __mapper_args__ = {"polymorphic_identity": "sleep"}

    record_id: Mapped[FKEventRecordDetail]

    sleep_total_duration_minutes: Mapped[int | None]
    sleep_time_in_bed_minutes: Mapped[int | None]
    sleep_efficiency_score: Mapped[numeric_5_2 | None]
    sleep_deep_minutes: Mapped[int | None]
    sleep_rem_minutes: Mapped[int | None]
    sleep_light_minutes: Mapped[int | None]
    sleep_awake_minutes: Mapped[int | None]

    # New fields for Taxonomy v2
    is_nap: Mapped[bool] = mapped_column(default=False)
