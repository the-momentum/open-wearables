from enum import Enum, StrEnum

from pydantic import BaseModel


class AgentMode(StrEnum):
    GENERAL = "general"


class BaseAgentQueryRequest(BaseModel):
    message: str


class BaseAgentQueryResponse(BaseModel):
    response: str


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class TaskType(Enum):
    conversation = 1
    refuse = 2
    translate = 3
