from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.token import TokenResponse


class UserInvitationCodeCreate(BaseModel):
    """Internal schema with all fields for repository creation."""

    id: UUID
    code: str
    user_id: UUID
    created_by_id: UUID
    expires_at: datetime
    redeemed_at: None = None
    revoked_at: None = None
    created_at: datetime


class UserInvitationCodeRead(BaseModel):
    """Response schema after generating an invitation code."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    user_id: UUID
    expires_at: datetime
    created_at: datetime


class UserInvitationCodeRedeem(BaseModel):
    """API input for redeeming an invitation code."""

    code: str = Field(..., min_length=8, max_length=8, pattern=r"^[A-Z2-9]{8}$")


class InvitationCodeRedeemResponse(TokenResponse):
    """Redeem response with user_id included."""

    user_id: UUID
