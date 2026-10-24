from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.auth import TokenResponse


def normalize_invitation_code(code: str) -> str:
    """The stored form of a code typed by hand: no spaces or hyphen, upper case."""
    return "".join(code.split()).replace("-", "").upper()


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


class UserInvitationCodeGenerated(UserInvitationCodeRead):
    """Generate response: the code plus ready-to-share forms of it."""

    invite_url: str = Field(
        description="Link that opens the Open Wearables Connect app with this server and code. "
        "Show it as a link or QR code; the parameters are in the fragment, so they never reach a web server."
    )
    qr_svg: str = Field(description="The invite_url as a QR code, an SVG document")


class UserInvitationCodeRedeem(BaseModel):
    """API input carrying an invitation code, for redeem and validate."""

    code: str = Field(
        ...,
        min_length=8,
        max_length=8,
        pattern=r"^[A-Z2-9]{8}$",
        description="The code as issued (K7M4Q9XP) or as displayed (K7M4-Q9XP), in any letter case",
    )

    @field_validator("code", mode="before")
    @classmethod
    def _normalize(cls, value: object) -> object:
        # People copy codes by hand from an email or a screen.
        return normalize_invitation_code(value) if isinstance(value, str) else value


class InvitationCodeValidateResponse(BaseModel):
    """A code that can still be redeemed. Validating does not use it up."""

    expires_at: datetime
    seat_request: str | None = Field(
        None,
        description="Instance-signed token the Open Wearables Connect app sends to the license server to claim "
        "a seat before redeeming; valid 5 minutes, single use. null while the app is not enabled on this instance",
    )


class InvitationCodeRedeemResponse(TokenResponse):
    """Redeem response with user_id included."""

    user_id: UUID
