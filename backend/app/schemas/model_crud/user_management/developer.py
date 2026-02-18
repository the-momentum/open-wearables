from datetime import datetime, timezone
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class DeveloperRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    first_name: str | None = None
    last_name: str | None = None
    email: EmailStr
    created_at: datetime
    updated_at: datetime


class DeveloperCreate(BaseModel):
    first_name: str | None = Field(None, max_length=100)
    last_name: str | None = Field(None, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8)


class DeveloperCreateInternal(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    first_name: str | None = None
    last_name: str | None = None
    email: EmailStr
    hashed_password: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DeveloperUpdate(BaseModel):
    first_name: str | None = Field(None, max_length=100)
    last_name: str | None = Field(None, max_length=100)
    email: EmailStr | None = None
    password: str | None = Field(None, min_length=8)


class DeveloperUpdateInternal(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    email: EmailStr | None = None
    hashed_password: str | None = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
