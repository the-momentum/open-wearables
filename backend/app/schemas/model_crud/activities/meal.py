from pydantic import Field

from .event_record_detail import EventRecordDetailCreate


class MealDetailCreate(EventRecordDetailCreate):
    """Creation payload for a meal's detail row (title, meal type)."""

    title: str | None = Field(default=None, max_length=255)
    meal_type: str | None = Field(default=None, max_length=32)
