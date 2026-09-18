from .event_record_detail import EventRecordDetailCreate


class MealDetailCreate(EventRecordDetailCreate):
    title: str | None = None
    meal_type: str | None = None
