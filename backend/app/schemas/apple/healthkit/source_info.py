from __future__ import annotations

from pydantic import BaseModel


class OSVersion(BaseModel):
    major_version: int
    minor_version: int
    patch_version: int


class SourceInfo(BaseModel):
    name: str | None = None
    bundle_identifier: str | None = None
    version: str | None = None
    product_type: str | None = None
    operating_system_version: OSVersion | None = None
    device_name: str | None = None
    device_manufacturer: str | None = None
    device_model: str | None = None
    device_hardware_version: str | None = None
    device_software_version: str | None = None
