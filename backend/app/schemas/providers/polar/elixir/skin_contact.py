from pydantic import BaseModel


class SkinContactChangeJSON(BaseModel):
    skin_contact: bool | None = None
    recording_time_delta_milliseconds: int | None = None


class SkinContactPeriodJSON(BaseModel):
    source_device_id: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    modified_time: str | None = None
    skin_contact_changes: list[SkinContactChangeJSON] | None = None
