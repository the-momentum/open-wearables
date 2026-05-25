from pydantic import BaseModel, Field


class CardioLoadLevelJSON(BaseModel):
    very_low: float | None = None
    low: float | None = None
    medium: float | None = None
    high: float | None = None
    very_high: float | None = Field(None, alias="very-high")


class CardioLoadJSON(BaseModel):
    date: str | None = None
    cardio_load_status: str | None = None
    cardio_load: float | None = None
    strain: float | None = None
    tolerance: float | None = None
    cardio_load_ratio: float | None = None
    cardio_load_level: CardioLoadLevelJSON | None = None
