from pydantic import Field

from .event_record_detail import EventRecordDetailCreate


class MealDetailCreate(EventRecordDetailCreate):
    """Payload for creating or refreshing a meal's `MealDetails` row."""

    title: str | None = Field(default=None, max_length=255)
    meal_type: str | None = Field(default=None, max_length=32)
