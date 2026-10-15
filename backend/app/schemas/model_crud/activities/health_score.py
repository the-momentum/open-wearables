from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.enums import HealthScoreCategory, ProviderName
from app.utils.dates import ZoneOffset
from app.utils.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE


class ScoreComponent(BaseModel):
    """A single constituent of a health score (e.g. deep sleep percentage)."""

    value: float | int | None = Field(
        None,
        description="Numeric score value. Range varies by provider and category — see HEALTH_SCORE_RANGES for scale.",
    )
    qualifier: str | None = Field(None, description="Textual rating from the provider, e.g. GOOD or EXCELLENT")


class HealthScoreBase(BaseModel):
    category: HealthScoreCategory
    value: float | int | None = Field(
        None,
        description="Overall numeric score. Range varies by provider and category — see HEALTH_SCORE_RANGES for scale.",
    )
    qualifier: str | None = Field(None, description="Textual rating from the provider, e.g. GOOD or EXCELLENT")
    recorded_at: datetime
    zone_offset: ZoneOffset = None
    components: dict[str, ScoreComponent] | None = None


class HealthScoreCreate(HealthScoreBase):
    id: UUID
    user_id: UUID
    data_source_id: UUID | None = None
    provider: ProviderName
    event_record_id: UUID | None = None


class HealthScoreUpdate(HealthScoreBase): ...


class HealthScoreQueryParams(BaseModel):
    start_datetime: datetime | None = None
    end_datetime: datetime | None = None
    category: HealthScoreCategory | None = None
    provider: ProviderName | None = None
    data_source_id: UUID | None = None
    limit: int = Field(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE)
    offset: int = Field(0, ge=0)

    @model_validator(mode="after")
    def validate_date_range(self) -> "HealthScoreQueryParams":
        if self.start_datetime and self.end_datetime and self.start_datetime >= self.end_datetime:
            raise ValueError("start_datetime must be before end_datetime")
        return self


class HealthScoreResponse(HealthScoreBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    data_source_id: UUID | None
    provider: ProviderName | None
    event_record_id: UUID | None = Field(
        None, description="The sleep session or workout this score describes. Null for whole-day scores."
    )
