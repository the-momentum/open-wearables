from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class SessionRequest(BaseModel):
    session_id: UUID | None = None
    language: str | None = None
    agent_mode: str | None = None


class SessionCreateResponse(BaseModel):
    session_id: UUID
    conversation_id: UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class SessionDeactivateResponse(BaseModel):
    session_id: UUID
    active: bool = False

    model_config = {"from_attributes": True}
