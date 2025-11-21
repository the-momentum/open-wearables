from datetime import datetime, timezone
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


# OAuth State (Redis)
class OAuthState(BaseModel):
    """OAuth state stored in Redis during authorization flow."""

    user_id: UUID
    provider: str
    redirect_uri: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# UserConnection schemas
class UserConnectionBase(BaseModel):
    """Base schema for UserConnection."""

    user_id: UUID
    provider: str
    provider_user_id: str | None = None
    provider_username: str | None = None
    scope: str | None = None


class UserConnectionCreate(UserConnectionBase):
    """Schema for creating a new UserConnection."""

    id: UUID = Field(default_factory=uuid4)
    access_token: str
    refresh_token: str | None = None
    token_expires_at: datetime
    status: str = "active"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class UserConnectionUpdate(BaseModel):
    """Schema for updating UserConnection."""

    access_token: str | None = None
    refresh_token: str | None = None
    token_expires_at: datetime | None = None
    provider_user_id: str | None = None
    provider_username: str | None = None
    scope: str | None = None
    status: str | None = None
    last_synced_at: datetime | None = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class UserConnectionRead(UserConnectionBase):
    """Schema for reading UserConnection (without sensitive tokens)."""

    id: UUID
    status: str
    last_synced_at: datetime | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# OAuth Token Response
class OAuthTokenResponse(BaseModel):
    """OAuth token response from provider."""

    access_token: str
    token_type: str
    refresh_token: str | None = None
    expires_in: int
    scope: str | None = None
    x_user_id: int | None = None  # Polar-specific: user ID in Polar ecosystem


# Provider config
class ProviderConfig(BaseModel):
    """Configuration for an OAuth provider."""

    name: str
    client_id: str
    client_secret: str
    redirect_uri: str
    authorize_url: str
    token_url: str
    api_base_url: str
    default_scope: str
    subscription_key: str | None = None  # Suunto-specific


# Authorization URL response
class AuthorizationURLResponse(BaseModel):
    """Response containing authorization URL for user redirect."""

    authorization_url: str
    state: str
