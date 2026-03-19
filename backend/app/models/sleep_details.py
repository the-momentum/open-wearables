from sqlalchemy import Index
from sqlalchemy.orm import Mapped

from app.mappings import FKEventRecordDetail, json_binary, numeric_5_2

from .event_record_detail import EventRecordDetail


class SleepDetails(EventRecordDetail):
    """Per-sleep aggregates and metrics."""

    __tablename__ = "sleep_details"
    __mapper_args__ = {"polymorphic_identity": "sleep"}
    __table_args__ = (
        Index(
            "ix_sleep_details_stages_gin",
            "sleep_stages",
            postgresql_using="gin",
            postgresql_ops={
                "sleep_stages": "jsonb_path_ops"
            }
        ),
    )

    record_id: Mapped[FKEventRecordDetail]

    sleep_total_duration_minutes: Mapped[int | None]
    sleep_time_in_bed_minutes: Mapped[int | None]
    sleep_efficiency_score: Mapped[numeric_5_2 | None]
    sleep_deep_minutes: Mapped[int | None]
    sleep_rem_minutes: Mapped[int | None]
    sleep_light_minutes: Mapped[int | None]
    sleep_awake_minutes: Mapped[int | None]

    is_nap: Mapped[bool | None]
    sleep_stages: Mapped[json_binary | None]
