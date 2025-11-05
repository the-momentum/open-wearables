from datetime import datetime, timezone
from uuid import UUID

from fastapi_users.schemas import BaseUser, BaseUserCreate, BaseUserUpdate
from pydantic import Field


class UserRead(BaseUser[UUID]):
    pass


class UserCreate(BaseUserCreate):
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class UserUpdate(BaseUserUpdate):
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
