from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class DeviceSoftwareCreate(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    version: str = Field(description="Software version string")
    device_id: UUID | None = None


class DeviceSoftwareUpdate(BaseModel):
    pass


class DeviceCreate(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    serial_number: str = Field(description="Device serial number")
    provider_name: str = Field(description="Provider name (suunto, garmin, etc)")
    name: str = Field(description="Device name/model")


class DeviceUpdate(BaseModel):
    name: str | None = None
