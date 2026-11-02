from typing import ClassVar

from sqlalchemy.orm import Mapped

from app.mappings import FKEventRecord, json_object, str_32, str_255
from app.schemas.enums import EventCategory

from .event_record_detail import DetailType, EventRecordDetail


class MealDetails(EventRecordDetail):
    """Per-meal data; `nutrients` maps series type code to value in that series' unit."""

    __tablename__ = "meal_details"

    detail_type: ClassVar[DetailType] = EventCategory.MEAL
    record_id: Mapped[FKEventRecord]
    title: Mapped[str_255 | None]
    meal_type: Mapped[str_32 | None]
    nutrients: Mapped[json_object]
