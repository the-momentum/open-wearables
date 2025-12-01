from uuid import UUID, uuid4
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class DeveloperRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    created_at: datetime
    updated_at: datetime


class DeveloperCreate(BaseModel):
    password: str = Field(..., min_length=8)
    email: EmailStr


class DeveloperCreateInternal(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    email: EmailStr
    hashed_password: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DeveloperUpdate(BaseModel):
    password: str | None = Field(None, min_length=8)
    email: EmailStr | None = None


class DeveloperUpdateInternal(BaseModel):
    email: EmailStr | None = None
    hashed_password: str | None = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
