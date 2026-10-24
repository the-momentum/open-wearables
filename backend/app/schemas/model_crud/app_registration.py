from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


class AppRegistrationStatus(StrEnum):
    PENDING_VERIFICATION = "pending_verification"
    ACTIVE = "active"
    # The license server no longer knows the instance; register again.
    REMOVED = "removed"


class AppRegistrationCreate(BaseModel):
    """Register this instance for the Open Wearables Connect app (Settings > Mobile app)."""

    admin_email: EmailStr = Field(description="Gets the verification link and service messages about the app")
    accept_terms: bool = Field(description="Acceptance of the free plan terms and privacy notice; must be true")
    marketing_consent: bool = Field(False, description="Optional consent to product and offer emails")

    @field_validator("accept_terms")
    @classmethod
    def _terms_required(cls, value: bool) -> bool:
        if not value:
            raise ValueError("The free plan terms must be accepted to register")
        return value


class AppRegistrationRead(BaseModel):
    """Registration state. registered=false means the instance has not been registered."""

    registered: bool
    instance_id: UUID | None = None
    status: AppRegistrationStatus | None = None
    admin_email: str | None = None
    marketing_consent: bool | None = None
    terms_version: str | None = None
    email_verified_at: datetime | None = None
    registered_at: datetime | None = None


class AppEntitlement(BaseModel):
    """App seat usage from the license server, for "3 of 5 app seats used"."""

    status: str
    plan: str
    seat_limit: int | None = Field(description="null means no limit")
    seats_used: int
    rejected_claims_7d: int = Field(description="Claims refused in the last 7 days, e.g. over the limit")


class SeatRequestResponse(BaseModel):
    seat_request: str = Field(description="Instance-signed JWT, valid 5 minutes, single use; send it to claim")
