from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.mappings import FKEventRecordDetail, numeric_10_3

from .event_record_detail import EventRecordDetail


class MealDetails(EventRecordDetail):
    """Per-meal details."""

    __tablename__ = "meal_details"
    __mapper_args__ = {"polymorphic_identity": "meal"}

    record_id: Mapped[FKEventRecordDetail]

    meal_type: Mapped[str | None] = mapped_column(String(32))
    calories_kcal: Mapped[numeric_10_3 | None]
    protein_g: Mapped[numeric_10_3 | None]
    carbohydrates_g: Mapped[numeric_10_3 | None]
    fat_g: Mapped[numeric_10_3 | None]
    fiber_g: Mapped[numeric_10_3 | None]
    water_ml: Mapped[numeric_10_3 | None]
