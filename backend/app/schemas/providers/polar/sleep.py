from pydantic import BaseModel


class SleepJSON(BaseModel):
    polar_user: str | None = None
    date: str | None = None
    sleep_start_time: str | None = None
    sleep_end_time: str | None = None
    device_id: str | None = None
    continuity: float | None = None
    continuity_class: int | None = None
    light_sleep: int | None = None
    deep_sleep: int | None = None
    rem_sleep: int | None = None
    unrecognized_sleep_stage: int | None = None
    sleep_score: int | None = None
    total_interruption_duration: int | None = None
    sleep_charge: int | None = None
    sleep_goal: int | None = None
    sleep_rating: int | None = None
    short_interruption_duration: int | None = None
    long_interruption_duration: int | None = None
    sleep_cycles: int | None = None
    group_duration_score: float | None = None
    group_solidity_score: float | None = None
    group_regeneration_score: float | None = None
    hypnogram: dict[str, int] | None = None
    heart_rate_samples: dict[str, int] | None = None


class SleepResponseJSON(BaseModel):
    nights: list[SleepJSON] | None = None
