from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.enums import HealthScoreCategory, ProviderName
from app.utils.dates import ZoneOffset


class ScoreComponent(BaseModel):
    """A single constituent of a health score (e.g. deep sleep percentage)."""

    value: Decimal | None = Field(
        None,
        description="Numeric score value. Range varies by provider and category — see HEALTH_SCORE_RANGES for scale.",
    )
    qualifier: str | None = Field(None, description="Textual rating from the provider, e.g. GOOD or EXCELLENT")


class HealthScoreBase(BaseModel):
    category: HealthScoreCategory
    value: Decimal | None = Field(
        None,
        description="Overall numeric score. Range varies by provider and category — see HEALTH_SCORE_RANGES for scale.",
    )
    qualifier: str | None = Field(None, description="Textual rating from the provider, e.g. GOOD or EXCELLENT")
    recorded_at: datetime
    zone_offset: ZoneOffset = None
    components: dict[str, ScoreComponent] | None = None


class HealthScoreCreate(HealthScoreBase):
    id: UUID
    data_source_id: UUID | None = None
    provider: ProviderName | None = None


class HealthScoreUpdate(HealthScoreBase): ...


class HealthScoreResponse(HealthScoreBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    data_source_id: UUID | None
    provider: ProviderName | None
