from typing import Any
from datetime import datetime, timezone
from uuid import UUID, uuid4

from pydantic import BaseModel, EmailStr, Field


class UserInfo(BaseModel):
    """User information from authentication."""
    
    user_id: UUID
    auth0_id: str
    email: str
    permissions: list[str]
    payload: dict[str, Any]


class UserResponse(BaseModel):    
    user_id: UUID
    auth0_id: str
    email: str
    permissions: list[str]


class UserCreate(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    auth0_id: str
    email: EmailStr
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class UserUpdate(BaseModel):
    email: EmailStr | None = None
