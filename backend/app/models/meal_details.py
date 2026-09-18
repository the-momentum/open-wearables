from typing import ClassVar

from sqlalchemy.orm import Mapped

from app.mappings import FKEventRecord, str_32, str_255

from .event_record_detail import DetailType, EventRecordDetail


class MealDetails(EventRecordDetail):
    """Per-meal metadata from HealthKit or Google Health.

    Nutrient values themselves (protein, carbs, vitamins, ...) are not stored here -
    they live in DataPointSeries as regular per-nutrient samples, linked back to this
    record via DataPointSeries.event_record_id.
    """

    __tablename__ = "meal_details"

    detail_type: ClassVar[DetailType] = "meal"
    record_id: Mapped[FKEventRecord]
    title: Mapped[str_255 | None]
    meal_type: Mapped[str_32 | None]
