from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.schemas.agent import AgentMode
from app.schemas.language import Language


class ConversationRequest(BaseModel):
    conversation_id: UUID | None = None
    language: Language | None = None
    agent_mode: AgentMode | None = None


class ConversationCreateResponse(BaseModel):
    conversation_id: UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationDeactivateResponse(BaseModel):
    conversation_id: UUID

    model_config = {"from_attributes": True}
