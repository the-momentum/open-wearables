from datetime import datetime
from typing import Any

from .event_record_detail import EventRecordDetailCreate


class MenstrualCycleDetailCreate(EventRecordDetailCreate):
    day_in_cycle: int | None = None
    current_phase: int | None = None
    current_phase_type: str | None = None
    length_of_current_phase: int | None = None
    days_until_next_phase: int | None = None
    predicted_cycle_length: int | None = None
    is_predicted_cycle: bool | None = None
    cycle_length: int | None = None
    last_updated_at: datetime | None = None
    has_specified_cycle_length: bool | None = None
    has_specified_period_length: bool | None = None
    period_length: int | None = None
    fertile_window_start: int | None = None
    length_of_fertile_window: int | None = None
    pregnancy_snapshot: list[dict[str, Any]] | None = None
