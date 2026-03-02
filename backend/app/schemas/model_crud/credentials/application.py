from datetime import datetime, timezone
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class ApplicationCreate(BaseModel):
    """Schema for creating a new Application (external input)."""

    name: str = Field(..., max_length=100)


class ApplicationCreateInternal(ApplicationCreate):
    """Schema for creating Application internally with generated fields."""

    id: UUID = Field(default_factory=uuid4)
    app_id: str
    app_secret_hash: str
    developer_id: UUID
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ApplicationRead(BaseModel):
    """Schema for reading Application (without secret)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    app_id: str
    name: str
    created_at: datetime


class ApplicationReadWithSecret(ApplicationRead):
    """Schema returned only on creation - contains plain app_secret."""

    app_secret: str  # Only shown once at creation


class ApplicationUpdate(BaseModel):
    """Schema for updating Application."""

    name: str | None = None
