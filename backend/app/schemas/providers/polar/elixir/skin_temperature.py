from pydantic import BaseModel


class SkinTemperatureJSON(BaseModel):
    sleep_time_skin_temperature_celsius: float | None = None
    deviation_from_baseline_celsius: float | None = None
    sleep_date: str | None = None
