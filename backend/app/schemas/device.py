from uuid import UUID

from pydantic import BaseModel, Field


class DeviceSoftwareCreate(BaseModel):
    version: str = Field(description="Software version string")
    device_id: UUID | None = None


class DeviceSoftwareUpdate(BaseModel):
    pass


class DeviceCreate(BaseModel):
    serial_number: str = Field(description="Device serial number")
    provider_name: str = Field(description="Provider name (suunto, garmin, etc)")
    name: str = Field(description="Device name/model")


class DeviceUpdate(BaseModel):
    name: str | None = None
