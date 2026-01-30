from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class AuthenticationMethod(str, Enum):
    """Method used for client authentication."""

    BASIC_AUTH = "basic_auth"
    BODY = "body"


class ProviderName(str, Enum):
    """Supported data providers."""

    APPLE = "apple"
    GARMIN = "garmin"
    POLAR = "polar"
    SUUNTO = "suunto"
    WHOOP = "whoop"
    UNKNOWN = "unknown"


class ConnectionStatus(str, Enum):
    """Status of a user connection to a provider."""

    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"


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
class ProviderEndpoints(BaseModel):
    """Static endpoints for an OAuth provider."""

    authorize_url: str
    token_url: str


class ProviderCredentials(BaseModel):
    """User-configurable credentials for an OAuth provider."""

    client_id: str
    client_secret: str
    redirect_uri: str
    default_scope: str
    subscription_key: str | None = None  # Suunto-specific


# Authorization URL response
class AuthorizationURLResponse(BaseModel):
    """Response containing authorization URL for user redirect."""

    authorization_url: str
    state: str


class Token(BaseModel):
    """JWT access token response."""

    access_token: str
    token_type: str
