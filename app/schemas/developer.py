from datetime import datetime, timezone
from uuid import UUID

from fastapi_users.schemas import BaseUser, BaseUserCreate, BaseUserUpdate
from pydantic import Field


class DeveloperRead(BaseUser[UUID]):
    pass


class DeveloperCreate(BaseUserCreate):
    created_at: datetime | None = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime | None = Field(default_factory=lambda: datetime.now(timezone.utc))


class DeveloperUpdate(BaseUserUpdate):
    updated_at: datetime | None = Field(default_factory=lambda: datetime.now(timezone.utc))
