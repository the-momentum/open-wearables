from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ApiKeyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    created_by: UUID | None
    created_at: datetime


class ApiKeyCreate(BaseModel):
    id: str
    name: str
    created_by: UUID | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ApiKeyUpdate(BaseModel):
    name: str | None = None
