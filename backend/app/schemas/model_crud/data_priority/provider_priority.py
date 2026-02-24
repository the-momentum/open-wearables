from datetime import datetime
from uuid import UUID

from app.schemas.oauth import ProviderName
from pydantic import BaseModel, Field


class ProviderPriorityBase(BaseModel):
    provider: ProviderName
    priority: int = Field(..., ge=1, le=100)


class ProviderPriorityCreate(ProviderPriorityBase):
    pass


class ProviderPriorityUpdate(BaseModel):
    priority: int = Field(..., ge=1, le=100)


class ProviderPriorityResponse(ProviderPriorityBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProviderPriorityListResponse(BaseModel):
    items: list[ProviderPriorityResponse]


class ProviderPriorityBulkUpdate(BaseModel):
    priorities: list[ProviderPriorityBase]
