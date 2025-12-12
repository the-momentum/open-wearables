from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class InvitationStatus(StrEnum):
    PENDING = "pending"  # Email queued, delivery in progress
    SENT = "sent"  # Email delivered, waiting for acceptance
    FAILED = "failed"  # Email delivery failed after all retries
    ACCEPTED = "accepted"
    EXPIRED = "expired"
    REVOKED = "revoked"


class InvitationCreate(BaseModel):
    """Schema for creating a new invitation."""

    email: EmailStr


class InvitationRead(BaseModel):
    """Schema for reading invitation data."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    status: InvitationStatus
    expires_at: datetime
    created_at: datetime
    invited_by_id: UUID | None = None


class InvitationAccept(BaseModel):
    """Schema for accepting an invitation."""

    token: str
    first_name: str = Field(..., min_length=1, max_length=100, strip_whitespace=True)
    last_name: str = Field(..., min_length=1, max_length=100, strip_whitespace=True)
    password: str = Field(..., min_length=8)

