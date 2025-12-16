from sqlalchemy.orm import Mapped

from app.mappings import FKEventRecordDetail, numeric_5_2, numeric_10_3

from .event_record_detail import EventRecordDetail


class WorkoutDetail(EventRecordDetail):
    """Per-workout aggregates and metrics."""

    __tablename__ = "workout_detail"
    __mapper_args__ = {"polymorphic_identity": "workout"}

    record_id: Mapped[FKEventRecordDetail]

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
    average_watts: Mapped[numeric_10_3 | None]
    elev_high: Mapped[numeric_10_3 | None]
    elev_low: Mapped[numeric_10_3 | None]
