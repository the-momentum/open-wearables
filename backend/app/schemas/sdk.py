from typing import Literal

from pydantic import BaseModel


class SDKTokenRequest(BaseModel):
    """Request schema for exchanging app credentials for user token."""

    app_id: str
    app_secret: str


class SDKAuthContext(BaseModel):
    """Context returned by SDK authentication dependency."""

    auth_type: Literal["sdk_token", "api_key"]
    external_user_id: str | None = None  # From SDK token
    app_id: str | None = None  # From SDK token
    api_key_id: str | None = None  # From API key
