from pydantic import Field

from .event_record_detail import EventRecordDetailCreate


class ReproductiveHealthDetailCreate(EventRecordDetailCreate):
    value: str | None = Field(default=None, max_length=32)
    cycle_start: bool | None = None
    protection_used: bool | None = None
    cervical_mucus_sensation: str | None = Field(default=None, max_length=32)
