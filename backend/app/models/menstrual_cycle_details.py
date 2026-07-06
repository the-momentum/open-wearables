from datetime import datetime

from sqlalchemy.orm import Mapped

from app.mappings import FKEventRecordDetail, json_binary, str_32

from .event_record_detail import EventRecordDetail


class MenstrualCycleDetails(EventRecordDetail):
    """Per-cycle aggregates from Garmin MCT and other providers."""

    __tablename__ = "menstrual_cycle_details"
    __mapper_args__ = {"polymorphic_identity": "menstrual_cycle"}

    record_id: Mapped[FKEventRecordDetail]

    day_in_cycle: Mapped[int | None]
    current_phase: Mapped[int | None]
    current_phase_type: Mapped[str_32 | None]
    length_of_current_phase: Mapped[int | None]
    days_until_next_phase: Mapped[int | None]
    predicted_cycle_length: Mapped[int | None]
    is_predicted_cycle: Mapped[bool | None]
    cycle_length: Mapped[int | None]
    last_updated_at: Mapped[datetime | None]
    has_specified_cycle_length: Mapped[bool | None]
    has_specified_period_length: Mapped[bool | None]

    # Non-pregnant phase only
    period_length: Mapped[int | None]
    fertile_window_start: Mapped[int | None]
    length_of_fertile_window: Mapped[int | None]

    # Populated when currentPhase is pregnancy
    pregnancy_snapshot: Mapped[json_binary | None]
