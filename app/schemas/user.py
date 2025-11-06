from datetime import datetime, timezone
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class UserRead(BaseModel):
    id: UUID
    created_at: datetime


class UserCreate(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class UserUpdate(BaseModel):
    pass
