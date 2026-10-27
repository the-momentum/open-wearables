from datetime import datetime
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class LegalAcceptanceCreate(BaseModel):
    """What the app reports when the user ticks "I accept" for the instance's documents."""

    documents_version: int = Field(ge=1, description="legal_documents_version from instance/info that was shown")
    accepted_at: AwareDatetime = Field(description="When the user accepted, on the phone's clock")


class LegalAcceptanceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    documents_version: int
    privacy_policy_url: str | None
    terms_url: str | None
    accepted_at: datetime
    created_at: datetime = Field(description="When the instance received the acceptance")
