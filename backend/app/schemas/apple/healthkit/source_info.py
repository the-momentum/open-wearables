from __future__ import annotations

from pydantic import BaseModel


class OSVersion(BaseModel):
    majorVersion: int
    minorVersion: int
    patchVersion: int


class SourceInfo(BaseModel):
    name: str | None = None
    bundleIdentifier: str | None = None
    version: str | None = None
    productType: str | None = None
    operatingSystemVersion: OSVersion | None = None
    deviceName: str | None = None
    deviceManufacturer: str | None = None
    deviceModel: str | None = None
    deviceHardwareVersion: str | None = None
    deviceSoftwareVersion: str | None = None
