from pydantic import BaseModel


class HRZone(BaseModel):
    zone: int
    seconds: float
    max_bpm: int | None = None


class HRZones(BaseModel):
    zones: list[HRZone]
    max_hr: int | None = None
    threshold_hr: int | None = None


class PowerZone(BaseModel):
    zone: int
    seconds: float
    max_watts: int | None = None


class PowerZones(BaseModel):
    zones: list[PowerZone]
    ftp_watts: int | None = None
