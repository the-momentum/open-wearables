from datetime import datetime, timezone
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class McpClientTouch(BaseModel):
    """Schema the MCP server posts on client registration and on each successful login."""

    client_id: str = Field(..., max_length=255)
    client_name: str | None = Field(default=None, max_length=255)


class McpClientCreateInternal(BaseModel):
    """Schema for creating an McpClient internally with generated fields."""

    id: UUID = Field(default_factory=uuid4)
    client_id: str
    client_name: str | None = None
    api_key_id: UUID
    last_seen_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class McpClientRead(BaseModel):
    """Schema for reading an McpClient."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    client_id: str
    client_name: str | None
    last_seen_at: datetime
    created_at: datetime


class McpClientUpdate(BaseModel):
    """Schema for updating an McpClient."""

    client_name: str | None = None
    last_seen_at: datetime | None = None
