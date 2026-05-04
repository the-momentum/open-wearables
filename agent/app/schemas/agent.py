from enum import StrEnum

from pydantic import BaseModel


class AgentMode(StrEnum):
    GENERAL = "general"


class ConversationStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    CLOSED = "closed"


class BaseAgentQueryRequest(BaseModel):
    message: str


class BaseAgentQueryResponse(BaseModel):
    response: str


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
