"""Data models for the Open Wearables SDK."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class User(BaseModel):
    """Represents a user in the Open Wearables system."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    first_name: str | None = None
    last_name: str | None = None
    email: EmailStr | None = None
    external_user_id: str | None = None


class UserCreate(BaseModel):
    """Schema for creating a user."""

    first_name: str | None = Field(None, max_length=100)
    last_name: str | None = Field(None, max_length=100)
    email: EmailStr | None = None
    external_user_id: str | None = None


class UserUpdate(BaseModel):
    """Schema for updating a user."""

    first_name: str | None = Field(None, max_length=100)
    last_name: str | None = Field(None, max_length=100)
    email: EmailStr | None = None
    external_user_id: str | None = None


class WorkoutStatistic(BaseModel):
    """Represents a workout statistic."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    workout_id: UUID | None = None
    type: str
    start_datetime: datetime
    end_datetime: datetime
    min: Decimal | None = None
    max: Decimal | None = None
    avg: Decimal | None = None
    unit: str


class Workout(BaseModel):
    """Represents a workout."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    type: str | None = None
    duration_seconds: Decimal
    source_name: str
    start_datetime: datetime
    end_datetime: datetime
    statistics: list[WorkoutStatistic] = Field(default_factory=list)


class Connection(BaseModel):
    """Represents a user's connection to a fitness provider."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    provider: str
    connected_at: datetime
    is_active: bool = True
