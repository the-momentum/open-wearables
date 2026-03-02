from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, Field


# OAuth State (Redis)
class OAuthState(BaseModel):
    """OAuth state stored in Redis during authorization flow."""

    user_id: UUID
    provider: str
    redirect_uri: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# OAuth Token Response
class OAuthTokenResponse(BaseModel):
    """OAuth token response from provider.

    Standard OAuth 2.0 fields are declared explicitly. Provider-specific extras
    (e.g. Polar's ``x_user_id``, Fitbit's ``user_id``) are captured automatically
    in ``model_extra`` thanks to ``extra='allow'``, so the schema stays clean as
    new providers are added.
    """

    model_config = ConfigDict(extra="allow")

    access_token: str
    token_type: str
    refresh_token: str | None = None
    expires_in: int
    scope: str | None = None


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
