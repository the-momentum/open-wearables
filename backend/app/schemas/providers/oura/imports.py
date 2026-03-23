"""Pydantic models for Oura Ring API v2 responses."""

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Workouts
# ---------------------------------------------------------------------------


class OuraWorkoutJSON(BaseModel):
    """Single workout from Oura API v2 /usercollection/workout."""

    id: str
    activity: str | None = None
    calories: float | None = None
    day: str | None = None  # YYYY-MM-DD
    distance: float | None = None  # meters
    end_datetime: str | None = None  # ISO 8601
    intensity: str | None = None  # easy / moderate / hard
    label: str | None = None
    source: str | None = None
    start_datetime: str | None = None  # ISO 8601


class OuraWorkoutCollectionJSON(BaseModel):
    """Paginated workout collection response."""

    data: list[OuraWorkoutJSON] = []
    next_token: str | None = None


# ---------------------------------------------------------------------------
# Sleep
# ---------------------------------------------------------------------------


class OuraSleepJSON(BaseModel):
    """Single sleep record from Oura API v2 /usercollection/sleep."""

    id: str
    average_breath: float | None = None
    average_heart_rate: float | None = None
    average_hrv: int | None = None
    awake_time: int | None = None  # seconds
    bedtime_end: str | None = None  # ISO 8601
    bedtime_start: str | None = None  # ISO 8601
    day: str | None = None  # YYYY-MM-DD
    deep_sleep_duration: int | None = None  # seconds
    efficiency: int | None = None  # 0-100
    latency: int | None = None  # seconds
    light_sleep_duration: int | None = None  # seconds
    low_battery_alert: bool = False
    lowest_heart_rate: int | None = None
    period: int | None = None  # 0=main, 1=rest period
    readiness_score_delta: float | None = None
    rem_sleep_duration: int | None = None  # seconds
    restless_periods: int | None = None
    sleep_score_delta: float | None = None
    time_in_bed: int | None = None  # seconds
    total_sleep_duration: int | None = None  # seconds
    type: str | None = None  # deleted / sleep / long_sleep / rest


class OuraSleepCollectionJSON(BaseModel):
    """Paginated sleep collection response."""

    data: list[OuraSleepJSON] = []
    next_token: str | None = None


# ---------------------------------------------------------------------------
# Daily Readiness
# ---------------------------------------------------------------------------


class OuraDailyReadinessJSON(BaseModel):
    """Single daily readiness record from Oura API v2 /usercollection/daily_readiness."""

    id: str
    day: str | None = None  # YYYY-MM-DD
    score: int | None = None  # 0-100
    temperature_deviation: float | None = None
    temperature_trend_deviation: float | None = None
    timestamp: str | None = None  # ISO 8601
    contributors: dict | None = None


class OuraReadinessCollectionJSON(BaseModel):
    """Paginated readiness collection response."""

    data: list[OuraDailyReadinessJSON] = []
    next_token: str | None = None


# ---------------------------------------------------------------------------
# Daily Activity
# ---------------------------------------------------------------------------


class OuraDailyActivityJSON(BaseModel):
    """Single daily activity record from Oura API v2 /usercollection/daily_activity."""

    id: str
    day: str | None = None
    score: int | None = None
    active_calories: int | None = None
    average_met_minutes: float | None = None
    equivalent_walking_distance: int | None = None  # meters
    high_activity_met_minutes: int | None = None
    high_activity_time: int | None = None  # seconds
    low_activity_met_minutes: int | None = None
    low_activity_time: int | None = None  # seconds
    medium_activity_met_minutes: int | None = None
    medium_activity_time: int | None = None  # seconds
    meters_to_target: int | None = None
    non_wear_time: int | None = None  # seconds
    resting_time: int | None = None  # seconds
    sedentary_met_minutes: int | None = None
    sedentary_time: int | None = None  # seconds
    steps: int | None = None
    target_calories: int | None = None
    target_meters: int | None = None
    total_calories: int | None = None
    timestamp: str | None = None


class OuraActivityCollectionJSON(BaseModel):
    """Paginated activity collection response."""

    data: list[OuraDailyActivityJSON] = []
    next_token: str | None = None


# ---------------------------------------------------------------------------
# Heart Rate
# ---------------------------------------------------------------------------


class OuraHeartRateJSON(BaseModel):
    """Single heart rate sample from Oura API v2 /usercollection/heartrate."""

    bpm: int
    source: str | None = None  # awake / rest / sleep / session / live
    timestamp: str  # ISO 8601


class OuraHeartRateCollectionJSON(BaseModel):
    """Paginated heart rate collection response."""

    data: list[OuraHeartRateJSON] = []
    next_token: str | None = None


# ---------------------------------------------------------------------------
# Daily SpO2
# ---------------------------------------------------------------------------


class OuraSpO2ReadingJSON(BaseModel):
    """SpO2 reading within a daily record."""

    percentage: float
    timestamp: str  # ISO 8601


class OuraDailySpo2JSON(BaseModel):
    """Single daily SpO2 record from Oura API v2 /usercollection/daily_spo2."""

    id: str
    day: str | None = None
    spo2_percentage: dict | None = None  # {"average": 98.5}


class OuraSpo2CollectionJSON(BaseModel):
    """Paginated SpO2 collection response."""

    data: list[OuraDailySpo2JSON] = []
    next_token: str | None = None


# ---------------------------------------------------------------------------
# Personal Info
# ---------------------------------------------------------------------------


class OuraPersonalInfoJSON(BaseModel):
    """User personal info from Oura API v2 /usercollection/personal_info."""

    id: str | None = None
    age: int | None = None
    weight: float | None = None  # kg
    height: float | None = None  # meters
    biological_sex: str | None = None
    email: str | None = None


# ---------------------------------------------------------------------------
# Webhook Notification
# ---------------------------------------------------------------------------


class OuraWebhookNotification(BaseModel):
    """Webhook notification payload from Oura."""

    event_type: str  # create / update / delete
    data_type: str  # e.g. tag, workout, sleep, daily_activity, daily_readiness, daily_spo2
    user_id: str  # Oura user ID
    event_timestamp: str | None = None  # ISO 8601
    data_timestamp: str | None = None  # ISO 8601 (date of data)
