from pydantic import BaseModel


class PhysicalInfoJSON(BaseModel):
    """GET /v3/users/physical-info — the user's current physical settings."""

    weight: float | None = None
    height: float | None = None
    created: str | None = None
    modified: str | None = None
    maximum_heart_rate: int | None = None
    resting_heart_rate: int | None = None
    vo2_max: int | None = None
    weight_source: str | None = None
