from datetime import datetime, timezone
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class DeveloperRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    email: EmailStr | None = None
    created_at: datetime
    updated_at: datetime


class DeveloperCreate(BaseModel):
    username: str = Field(..., max_length=100)
    password: str = Field(..., min_length=8)
    email: EmailStr | None = None


class DeveloperCreateInternal(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    username: str = Field(..., max_length=100)
    hashed_password: str
    email: EmailStr | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DeveloperUpdate(BaseModel):
    username: str | None = Field(None, max_length=100)
    password: str | None = Field(None, min_length=8)
    email: EmailStr | None = None


class DeveloperUpdateInternal(BaseModel):
    username: str | None = None
    email: EmailStr | None = None
    hashed_password: str | None = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
