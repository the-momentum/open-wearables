from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.enums import ProviderName


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
    name: str | None = Field(None, description="Display name (e.g., 'Apple Health', 'Garmin').")
    icon_url: str | None = Field(
        None,
        description=(
            "Relative URL to provider icon (e.g., '/static/provider-icons/garmin.svg')."
            " Resolve against the API base URL."
        ),
    )

    model_config = {"from_attributes": True}


class ProviderPriorityListResponse(BaseModel):
    items: list[ProviderPriorityResponse]


class ProviderPriorityBulkUpdate(BaseModel):
    priorities: list[ProviderPriorityBase]
