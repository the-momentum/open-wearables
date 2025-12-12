from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserQueryParams(BaseModel):
    """Query parameters for filtering and searching users.

    Args:
        page: The page number (1-based).
        limit: The number of results per page.
        sort_by: The field to sort by.
        sort_order: The sort order.
        search: The search term.
        email: Filter by exact email match.
        external_user_id: Filter by external user ID.
    """

    page: int = Field(1, ge=1, description="Page number (1-based)")
    limit: int = Field(20, ge=1, le=100, description="Number of results per page")

    sort_by: Literal["created_at", "email", "first_name", "last_name"] | None = Field(
        "created_at",
        description="Field to sort by",
    )
    sort_order: Literal["asc", "desc"] = Field("desc", description="Sort order")

    search: str | None = Field(
        None,
        description="Search across first_name, last_name, and email (partial match)",
    )

    email: EmailStr | None = Field(None, description="Filter by exact email")
    external_user_id: str | None = Field(None, description="Filter by external user ID")


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    first_name: str | None = None
    last_name: str | None = None
    email: EmailStr | None = None
    external_user_id: str | None = None


class UserCreate(BaseModel):
    first_name: str | None = Field(None, max_length=100)
    last_name: str | None = Field(None, max_length=100)
    email: EmailStr | None = None
    external_user_id: str | None = None


class UserCreateInternal(UserCreate):
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class UserUpdate(BaseModel):
    first_name: str | None = Field(None, max_length=100)
    last_name: str | None = Field(None, max_length=100)
    email: EmailStr | None = None
    external_user_id: str | None = None


class UserUpdateInternal(UserUpdate):
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
