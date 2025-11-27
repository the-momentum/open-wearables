from datetime import datetime, timezone
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    created_at: datetime
    first_name: str | None = None
    last_name: str | None = None
    email: EmailStr | None = None
    client_user_id: str


class UserCreate(BaseModel):
    first_name: str | None = Field(None, max_length=100)
    last_name: str | None = Field(None, max_length=100)
    email: EmailStr | None = None
    client_user_id: str = Field(..., max_length=255)


class UserCreateInternal(UserCreate):
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class UserUpdate(BaseModel):
    first_name: str | None = Field(None, max_length=100)
    last_name: str | None = Field(None, max_length=100)
    email: EmailStr | None = None
    client_user_id: str | None = Field(None, max_length=255)
