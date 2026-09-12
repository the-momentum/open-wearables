from datetime import datetime, timezone
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class ApiKeyRead(BaseModel):
    """Schema for reading an API key (never includes the raw key value)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    key_prefix: str
    created_by: UUID | None
    created_at: datetime


class ApiKeyReadWithSecret(ApiKeyRead):
    """Schema returned only on create / rotate - contains the raw key value."""

    key: str  # Only shown once, cannot be retrieved again


class ApiKeyCreate(BaseModel):
    """Internal creator: the raw key is hashed by the service before it gets here."""

    id: UUID = Field(default_factory=uuid4)
    key_hash: str
    key_prefix: str
    name: str
    created_by: UUID | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ApiKeyUpdate(BaseModel):
    name: str | None = None
