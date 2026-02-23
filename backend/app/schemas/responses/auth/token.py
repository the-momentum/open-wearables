from pydantic import BaseModel


class TokenResponse(BaseModel):
    """Token response with optional refresh token."""

    access_token: str
    token_type: str = "bearer"
    refresh_token: str | None = None
    expires_in: int | None = None  # seconds


class RefreshTokenRequest(BaseModel):
    """Request to exchange refresh token for new access token."""

    refresh_token: str
