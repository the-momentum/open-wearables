from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class OAuthHandoffPurpose(StrEnum):
    """The website action that initiated a Strava identity handoff."""

    LOGIN = "login"
    REGISTER = "register"
    LINK_IDENTITY = "link_identity"


class OAuthHandoffBootstrapRequest(BaseModel):
    state: str = Field(min_length=20, max_length=256)
    return_uri: str = Field(min_length=12, max_length=512)
    purpose: OAuthHandoffPurpose
    scopes: list[str] = Field(default_factory=list, max_length=8)


class OAuthHandoffBootstrapResponse(BaseModel):
    authorization_url: str


class OAuthHandoffInspectRequest(BaseModel):
    handoff_code: str = Field(min_length=32, max_length=256)


class OAuthHandoffInspectResponse(BaseModel):
    provider_subject: str
    scope: str
    first_name: str = ""
    last_name: str = ""
    provider_username: str | None = None
    purpose: OAuthHandoffPurpose
    activity_sync_authorized: bool
    claim_code: str | None = None


class OAuthHandoffClaimRequest(BaseModel):
    handoff_code: str = Field(min_length=32, max_length=256)
    user_id: UUID


class OAuthHandoffClaimResponse(BaseModel):
    claimed: bool
    provider_subject: str
    scope: str
