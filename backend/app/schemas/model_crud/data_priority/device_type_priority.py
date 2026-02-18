from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.device_type import DeviceType


class DeviceTypePriorityBase(BaseModel):
    device_type: DeviceType
    priority: int = Field(..., ge=1, le=100)


class DeviceTypePriorityCreate(DeviceTypePriorityBase):
    pass


class DeviceTypePriorityUpdate(BaseModel):
    priority: int = Field(..., ge=1, le=100)


class DeviceTypePriorityResponse(DeviceTypePriorityBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DeviceTypePriorityListResponse(BaseModel):
    items: list[DeviceTypePriorityResponse]


class DeviceTypePriorityBulkUpdate(BaseModel):
    priorities: list[DeviceTypePriorityBase]
