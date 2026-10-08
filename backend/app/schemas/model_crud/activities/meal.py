from pydantic import Field, field_serializer

from app.schemas.enums import SeriesType

from .event_record_detail import EventRecordDetailCreate


class MealDetailCreate(EventRecordDetailCreate):
    title: str | None = Field(default=None, max_length=255)
    meal_type: str | None = Field(default=None, max_length=32)
    nutrients: dict[SeriesType, float] = Field(default_factory=dict)

    @field_serializer("nutrients")
    def _serialize_nutrients(self, nutrients: dict[SeriesType, float]) -> dict[str, float]:
        return {series_type.value: value for series_type, value in nutrients.items()}
