from app.schemas.enums import ConnectionStatus
from pydantic import BaseModel, ConfigDict, Field
from uuid import UUID
from datetime import datetime, timezone
from uuid import uuid4


class UserConnectionBase(BaseModel):
    """Base schema for UserConnection."""

    user_id: UUID
    provider: str
    provider_user_id: str | None = None
    provider_username: str | None = None
    scope: str | None = None


class UserConnectionCreate(UserConnectionBase):
    """Schema for creating a new UserConnection."""

    model_config = ConfigDict(populate_by_name=True)

    id: UUID = Field(default_factory=uuid4)
    access_token: str | None = None  # Optional for SDK-based providers (e.g., Apple)
    refresh_token: str | None = None
    token_expires_at: datetime | None = None  # Optional for SDK-based providers
    status: ConnectionStatus = ConnectionStatus.ACTIVE
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class UserConnectionUpdate(BaseModel):
    """Schema for updating UserConnection."""

    model_config = ConfigDict(populate_by_name=True)

    access_token: str | None = None
    refresh_token: str | None = None
    token_expires_at: datetime | None = None
    provider_user_id: str | None = None
    provider_username: str | None = None
    scope: str | None = None
    status: ConnectionStatus | None = None
    last_synced_at: datetime | None = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class UserConnectionRead(UserConnectionBase):
    """Schema for reading UserConnection (without sensitive tokens)."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    status: ConnectionStatus
    last_synced_at: datetime | None
    created_at: datetime
    updated_at: datetime

