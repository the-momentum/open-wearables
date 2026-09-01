from typing import ClassVar

from sqlalchemy import Index
from sqlalchemy.orm import Mapped

from app.mappings import FKEventRecord, json_binary, numeric_5_2, numeric_10_3

from .event_record_detail import DetailType, EventRecordDetail


class WorkoutDetails(EventRecordDetail):
    """Per-workout aggregates and metrics."""

    __tablename__ = "workout_details"
    __table_args__ = (
        Index(
            "ix_workout_details_segments_gin",
            "segments",
            postgresql_using="gin",
            postgresql_ops={"segments": "jsonb_path_ops"},
        ),
        Index(
            "ix_workout_details_hr_zones_gin",
            "hr_zones",
            postgresql_using="gin",
            postgresql_ops={"hr_zones": "jsonb_path_ops"},
        ),
        Index(
            "ix_workout_details_power_zones_gin",
            "power_zones",
            postgresql_using="gin",
            postgresql_ops={"power_zones": "jsonb_path_ops"},
        ),
    )

    detail_type: ClassVar[DetailType] = "workout"

    record_id: Mapped[FKEventRecord]

    heart_rate_min: Mapped[int | None]
    heart_rate_max: Mapped[int | None]
    heart_rate_avg: Mapped[numeric_5_2 | None]
    energy_burned: Mapped[numeric_10_3 | None]
    distance: Mapped[numeric_10_3 | None]
    steps_count: Mapped[int | None]

    max_speed: Mapped[numeric_5_2 | None]
    max_watts: Mapped[numeric_10_3 | None]
    moving_time_seconds: Mapped[int | None]
    total_elevation_gain: Mapped[numeric_10_3 | None]
    average_speed: Mapped[numeric_5_2 | None]
    average_cadence: Mapped[numeric_5_2 | None]
    average_watts: Mapped[numeric_10_3 | None]
    elev_high: Mapped[numeric_10_3 | None]
    elev_low: Mapped[numeric_10_3 | None]

    segments: Mapped[json_binary | None]
    hr_zones: Mapped[json_binary | None]
    power_zones: Mapped[json_binary | None]
