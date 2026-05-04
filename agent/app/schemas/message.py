from uuid import UUID

from pydantic import BaseModel

from app.schemas.agent import MessageRole


class MessageBase(BaseModel):
    conversation_id: UUID
    session_id: UUID | None = None
    role: MessageRole
    content: str


class MessageCreate(MessageBase):
    pass
