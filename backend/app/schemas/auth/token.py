from enum import StrEnum

from pydantic import BaseModel


class TokenType(StrEnum):
    """Type of refresh token."""

    SDK = "sdk"
    DEVELOPER = "developer"


class PasswordChangePrompt(StrEnum):
    """How the portal should ask a developer who signed in with the default password to change it."""

    REQUIRED = "required"
    RECOMMENDED = "recommended"


class TokenResponse(BaseModel):
    """Token response with optional refresh token."""

    access_token: str
    token_type: str = "bearer"
    refresh_token: str | None = None
    expires_in: int | None = None  # seconds
    # Set only by login, the one place that sees the password in plain text.
    password_change: PasswordChangePrompt | None = None


class RefreshTokenRequest(BaseModel):
    """Request to exchange refresh token for new access token."""

    refresh_token: str
