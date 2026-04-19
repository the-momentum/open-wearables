"""Schemas for seed data generation via the dashboard."""

from datetime import date

from pydantic import BaseModel, Field, model_validator

from app.schemas.enums import ProviderName, SeriesType, WorkoutType


class WorkoutConfig(BaseModel):
    """Parameters controlling workout generation."""

    count: int = Field(80, ge=0, le=500)
    workout_types: list[WorkoutType] | None = Field(
        None, description="Specific workout types to generate. None = random from all."
    )
    duration_min_minutes: int = Field(15, ge=5, le=600)
    duration_max_minutes: int = Field(180, ge=5, le=600)
    hr_min_range: tuple[int, int] = (90, 120)
    hr_max_range: tuple[int, int] = (140, 180)
    steps_range: tuple[int, int] = (500, 20_000)
    date_range_months: int = Field(6, ge=1, le=24)
    date_from: date | None = Field(None, description="Explicit start date. Overrides date_range_months.")
    date_to: date | None = Field(None, description="Explicit end date. Overrides date_range_months.")

    @model_validator(mode="after")
    def _validate_ranges(self) -> "WorkoutConfig":
        if self.duration_min_minutes > self.duration_max_minutes:
            msg = (
                f"duration_min_minutes ({self.duration_min_minutes}) "
                f"must be <= duration_max_minutes ({self.duration_max_minutes})"
            )
            raise ValueError(msg)
        if self.date_from and self.date_to and self.date_from > self.date_to:
            msg = f"date_from ({self.date_from}) must be <= date_to ({self.date_to})"
            raise ValueError(msg)
        return self


class SleepStageDistribution(BaseModel):
    """Percentage ranges for each sleep stage. Light = remainder (100% - others)."""

    deep_pct_range: tuple[int, int] = (15, 25)
    rem_pct_range: tuple[int, int] = (20, 25)
    awake_pct_range: tuple[int, int] = (2, 8)

    @model_validator(mode="after")
    def _validate_ranges(self) -> "SleepStageDistribution":
        for name in ("deep_pct_range", "rem_pct_range", "awake_pct_range"):
            lo, hi = getattr(self, name)
            if not (0 <= lo <= hi <= 100):
                msg = f"{name}: need 0 <= min ({lo}) <= max ({hi}) <= 100"
                raise ValueError(msg)
        max_sum = self.deep_pct_range[1] + self.rem_pct_range[1] + self.awake_pct_range[1]
        if max_sum > 95:
            msg = f"Sum of max percentages ({max_sum}%) exceeds 95% - not enough room for light sleep"
            raise ValueError(msg)
        return self


SLEEP_STAGE_PROFILES: dict[str, dict] = {
    "optimal": {
        "label": "Optimal Sleeper",
        "description": "Balanced stages - good sleep scores",
        "distribution": SleepStageDistribution(
            deep_pct_range=(18, 25),
            rem_pct_range=(20, 25),
            awake_pct_range=(2, 5),
        ),
    },
    "deep_deficit": {
        "label": "Deep Sleep Deficit",
        "description": "Low deep sleep - poor physical recovery",
        "distribution": SleepStageDistribution(
            deep_pct_range=(5, 10),
            rem_pct_range=(20, 25),
            awake_pct_range=(5, 10),
        ),
    },
    "rem_deprived": {
        "label": "REM Deprived",
        "description": "Low REM sleep - poor cognitive recovery",
        "distribution": SleepStageDistribution(
            deep_pct_range=(15, 22),
            rem_pct_range=(8, 13),
            awake_pct_range=(5, 10),
        ),
    },
    "restless": {
        "label": "Restless Sleeper",
        "description": "Excessive wake time - fragmented sleep",
        "distribution": SleepStageDistribution(
            deep_pct_range=(10, 15),
            rem_pct_range=(15, 20),
            awake_pct_range=(15, 25),
        ),
    },
    "athlete_recovery": {
        "label": "Athlete Recovery",
        "description": "Heavy deep sleep - optimal physical recovery",
        "distribution": SleepStageDistribution(
            deep_pct_range=(25, 35),
            rem_pct_range=(20, 25),
            awake_pct_range=(2, 5),
        ),
    },
}


class SleepConfig(BaseModel):
    """Parameters controlling sleep generation."""

    count: int = Field(20, ge=0, le=365)
    duration_min_minutes: int = Field(300, ge=60, le=720)
    duration_max_minutes: int = Field(600, ge=60, le=720)
    nap_chance_pct: int = Field(10, ge=0, le=100)
    weekend_catchup: bool = Field(
        False,
        description="If True, weekday sleep is shorter and weekend sleep is longer.",
    )
    date_range_months: int = Field(6, ge=1, le=24)
    date_from: date | None = Field(None, description="Explicit start date. Overrides date_range_months.")
    date_to: date | None = Field(None, description="Explicit end date. Overrides date_range_months.")
    stage_profile: str | None = Field(
        None,
        description="Named sleep stage profile. None = use stage_distribution.",
    )
    stage_distribution: SleepStageDistribution = SleepStageDistribution()

    @model_validator(mode="after")
    def _validate_ranges(self) -> "SleepConfig":
        if self.duration_min_minutes > self.duration_max_minutes:
            msg = (
                f"duration_min_minutes ({self.duration_min_minutes}) "
                f"must be <= duration_max_minutes ({self.duration_max_minutes})"
            )
            raise ValueError(msg)
        if self.date_from and self.date_to and self.date_from > self.date_to:
            msg = f"date_from ({self.date_from}) must be <= date_to ({self.date_to})"
            raise ValueError(msg)
        if self.stage_profile is not None and self.stage_profile not in SLEEP_STAGE_PROFILES:
            msg = f"Unknown stage_profile '{self.stage_profile}'. Valid profiles: {', '.join(SLEEP_STAGE_PROFILES)}"
            raise ValueError(msg)
        return self


class TimeSeriesConfig(BaseModel):
    """Parameters controlling continuous time-series generation.

    Continuous time-series are emitted across the full date range independently
    from workouts (e.g. heart rate every 5 min, weight weekly). Workout-bound
    series (running_power, cadence, ...) are still emitted inside workout
    windows and are not controlled by this config.
    """

    enabled_types: list[SeriesType] = Field(
        default_factory=list,
        description=(
            "Specific series types to emit. Empty list = no continuous series "
            "emitted. Workout-bound types are never affected by this list - "
            "they follow the workout generator."
        ),
    )
    include_blood_pressure: bool = Field(
        False,
        description="Emit paired blood_pressure_systolic + blood_pressure_diastolic.",
    )
    date_range_months: int = Field(6, ge=1, le=24)
    date_from: date | None = Field(None, description="Explicit start date. Overrides date_range_months.")
    date_to: date | None = Field(None, description="Explicit end date. Overrides date_range_months.")

    @model_validator(mode="after")
    def _validate_ranges(self) -> "TimeSeriesConfig":
        if self.date_from and self.date_to and self.date_from > self.date_to:
            msg = f"date_from ({self.date_from}) must be <= date_to ({self.date_to})"
            raise ValueError(msg)
        return self


class SeedProfileConfig(BaseModel):
    """Complete seed data generation configuration."""

    preset: str | None = None
    generate_workouts: bool = True
    generate_sleep: bool = True
    generate_time_series: bool = True
    providers: list[ProviderName] | None = Field(None, description="Specific providers. None = random selection.")
    num_connections: int = Field(2, ge=1, le=5)
    workout_config: WorkoutConfig = WorkoutConfig()
    sleep_config: SleepConfig = SleepConfig()
    time_series_config: TimeSeriesConfig = TimeSeriesConfig()


class SeedDataRequest(BaseModel):
    """API request to generate seed data."""

    num_users: int = Field(1, ge=1, le=10)
    profile: SeedProfileConfig = SeedProfileConfig()
    random_seed: int | None = Field(
        None,
        description="Seed for reproducible generation. None = random.",
    )


class SeedDataResponse(BaseModel):
    """API response after dispatching seed task."""

    task_id: str
    status: str
    seed_used: int | None = None


class SeedPresetInfo(BaseModel):
    """Preset metadata returned by the presets endpoint."""

    id: str
    label: str
    description: str
    profile: SeedProfileConfig


# ---------------------------------------------------------------------------
# Preset definitions
# ---------------------------------------------------------------------------

SEED_PRESETS: dict[str, dict] = {
    "active_athlete": {
        "label": "Active Athlete",
        "description": "High-volume training across running, cycling, swimming, and strength.",
        "profile": SeedProfileConfig(
            preset="active_athlete",
            generate_workouts=True,
            generate_sleep=True,
            generate_time_series=True,
            workout_config=WorkoutConfig(
                count=120,
                workout_types=[
                    WorkoutType.RUNNING,
                    WorkoutType.CYCLING,
                    WorkoutType.SWIMMING,
                    WorkoutType.STRENGTH_TRAINING,
                ],
                duration_min_minutes=30,
                duration_max_minutes=180,
                hr_min_range=(80, 110),
                hr_max_range=(160, 195),
                steps_range=(2000, 25_000),
            ),
            sleep_config=SleepConfig(count=30, stage_profile="athlete_recovery"),
        ),
    },
    "boxer_footballer": {
        "label": "Boxer + Footballer",
        "description": "Combat and team sport focus - boxing, soccer, running. No sleep data.",
        "profile": SeedProfileConfig(
            preset="boxer_footballer",
            generate_workouts=True,
            generate_sleep=False,
            generate_time_series=True,
            workout_config=WorkoutConfig(
                count=100,
                workout_types=[
                    WorkoutType.BOXING,
                    WorkoutType.SOCCER,
                    WorkoutType.RUNNING,
                    WorkoutType.STRENGTH_TRAINING,
                ],
                duration_min_minutes=30,
                duration_max_minutes=120,
                hr_min_range=(85, 115),
                hr_max_range=(155, 190),
            ),
        ),
    },
    "sleep_deprived": {
        "label": "Short Sleeper",
        "description": "Consistently short sleep (4-6h), minimal workouts.",
        "profile": SeedProfileConfig(
            preset="sleep_deprived",
            generate_workouts=True,
            generate_sleep=True,
            generate_time_series=True,
            workout_config=WorkoutConfig(count=10),
            sleep_config=SleepConfig(
                count=60,
                duration_min_minutes=240,
                duration_max_minutes=360,
                nap_chance_pct=5,
                stage_profile="deep_deficit",
            ),
        ),
    },
    "weekend_catchup": {
        "label": "Weekend Catch-Up",
        "description": "Short weekday sleep (4-6h), long weekend sleep (8-10h).",
        "profile": SeedProfileConfig(
            preset="weekend_catchup",
            generate_workouts=True,
            generate_sleep=True,
            generate_time_series=True,
            workout_config=WorkoutConfig(count=10),
            sleep_config=SleepConfig(
                count=60,
                duration_min_minutes=240,
                duration_max_minutes=360,
                weekend_catchup=True,
            ),
        ),
    },
    "irregular_sleeper": {
        "label": "Irregular Sleeper",
        "description": "Highly variable sleep times and durations - no consistent pattern.",
        "profile": SeedProfileConfig(
            preset="irregular_sleeper",
            generate_workouts=True,
            generate_sleep=True,
            generate_time_series=True,
            workout_config=WorkoutConfig(count=5),
            sleep_config=SleepConfig(
                count=90,
                duration_min_minutes=180,
                duration_max_minutes=660,
                nap_chance_pct=20,
                stage_profile="restless",
            ),
        ),
    },
    "activity_only": {
        "label": "Activity Only",
        "description": "Workouts and time series only - no sleep records.",
        "profile": SeedProfileConfig(
            preset="activity_only",
            generate_workouts=True,
            generate_sleep=False,
            generate_time_series=True,
            workout_config=WorkoutConfig(count=80),
        ),
    },
    "sleep_only": {
        "label": "Sleep Only",
        "description": "Sleep records only - no workout data.",
        "profile": SeedProfileConfig(
            preset="sleep_only",
            generate_workouts=False,
            generate_sleep=True,
            generate_time_series=False,
            sleep_config=SleepConfig(count=40, stage_profile="optimal"),
        ),
    },
    "minimal": {
        "label": "Minimal (Quick)",
        "description": "Small dataset for quick testing - 5 workouts, 5 sleeps, no time series.",
        "profile": SeedProfileConfig(
            preset="minimal",
            generate_workouts=True,
            generate_sleep=True,
            generate_time_series=False,
            workout_config=WorkoutConfig(count=5),
            sleep_config=SleepConfig(count=5),
        ),
    },
    "comprehensive": {
        "label": "Comprehensive",
        "description": "Large, rich dataset - 150 workouts, 60 sleeps, 5 providers, full time series.",
        "profile": SeedProfileConfig(
            preset="comprehensive",
            generate_workouts=True,
            generate_sleep=True,
            generate_time_series=True,
            num_connections=5,
            workout_config=WorkoutConfig(
                count=150,
                duration_min_minutes=10,
                duration_max_minutes=240,
            ),
            sleep_config=SleepConfig(count=60),
        ),
    },
}
