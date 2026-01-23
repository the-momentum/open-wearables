from pydantic import BaseModel, Field


class OSVersion(BaseModel):
    major_version: int = Field(alias="majorVersion")
    minor_version: int = Field(alias="minorVersion")
    patch_version: int = Field(alias="patchVersion")

    class Config:
        populate_by_name = True


class SourceInfo(BaseModel):
    name: str | None = None
    bundle_identifier: str | None = Field(default=None, alias="bundleIdentifier")
    version: str | None = None
    product_type: str | None = Field(default=None, alias="productType")
    operating_system_version: OSVersion | None = Field(default=None, alias="operatingSystemVersion")
    device_name: str | None = Field(default=None, alias="deviceName")
    device_manufacturer: str | None = Field(default=None, alias="deviceManufacturer")
    device_model: str | None = Field(default=None, alias="deviceModel")
    device_hardware_version: str | None = Field(default=None, alias="deviceHardwareVersion")
    device_software_version: str | None = Field(default=None, alias="deviceSoftwareVersion")

    class Config:
        populate_by_name = True
