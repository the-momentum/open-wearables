from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

from app.schemas.enums import ProviderName
from app.utils.dates import ZoneOffset


class ScoreComponent(BaseModel):
    """A single constituent of a health score (e.g. deep sleep percentage)."""

    value: Decimal | None = None
    qualifier: str | None = None


class HealthScoreBase(BaseModel):
    category: str
    value: Decimal | None = None
    qualifier: str | None = None
    recorded_at: datetime
    zone_offset: ZoneOffset = None
    constituents: dict[str, ScoreComponent] | None = None


class HealthScoreCreate(HealthScoreBase):
    id: UUID
    data_source_id: UUID | None = None
    provider: ProviderName | None = None


class HealthScoreUpdate(HealthScoreBase): ...


class HealthScoreResponse(HealthScoreBase):
    id: UUID
    data_source_id: UUID | None
    provider: ProviderName | None
