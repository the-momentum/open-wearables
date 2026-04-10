"""Schemas for seed data generation via the dashboard."""

from datetime import date

from pydantic import BaseModel, Field

from app.schemas.enums import ProviderName, WorkoutType


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
    time_series_chance_pct: int = Field(30, ge=0, le=100)
    date_range_months: int = Field(6, ge=1, le=24)
    date_from: date | None = Field(None, description="Explicit start date. Overrides date_range_months.")
    date_to: date | None = Field(None, description="Explicit end date. Overrides date_range_months.")


class SleepConfig(BaseModel):
    """Parameters controlling sleep generation."""

    count: int = Field(20, ge=0, le=365)
    duration_min_minutes: int = Field(300, ge=60, le=720)
    duration_max_minutes: int = Field(600, ge=60, le=720)
    nap_chance_pct: int = Field(10, ge=0, le=100)
    weekend_catchup: bool = Field(False, description="If True, weekday sleep is shorter and weekend sleep is longer.")
    date_range_months: int = Field(6, ge=1, le=24)
    date_from: date | None = Field(None, description="Explicit start date. Overrides date_range_months.")
    date_to: date | None = Field(None, description="Explicit end date. Overrides date_range_months.")


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


class SeedDataRequest(BaseModel):
    """API request to generate seed data."""

    num_users: int = Field(1, ge=1, le=10)
    profile: SeedProfileConfig = SeedProfileConfig()


class SeedDataResponse(BaseModel):
    """API response after dispatching seed task."""

    task_id: str
    status: str


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
                time_series_chance_pct=50,
            ),
            sleep_config=SleepConfig(count=30),
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
                time_series_chance_pct=40,
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
            workout_config=WorkoutConfig(count=10, time_series_chance_pct=20),
            sleep_config=SleepConfig(
                count=60,
                duration_min_minutes=240,
                duration_max_minutes=360,
                nap_chance_pct=5,
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
            workout_config=WorkoutConfig(count=10, time_series_chance_pct=15),
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
            workout_config=WorkoutConfig(count=5, time_series_chance_pct=15),
            sleep_config=SleepConfig(
                count=90,
                duration_min_minutes=180,
                duration_max_minutes=660,
                nap_chance_pct=20,
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
            sleep_config=SleepConfig(count=40),
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
        "description": "Large, rich dataset - 150 workouts, 60 sleeps, 5 providers, 80% time series.",
        "profile": SeedProfileConfig(
            preset="comprehensive",
            generate_workouts=True,
            generate_sleep=True,
            generate_time_series=True,
            num_connections=5,
            workout_config=WorkoutConfig(
                count=150,
                time_series_chance_pct=80,
                duration_min_minutes=10,
                duration_max_minutes=240,
            ),
            sleep_config=SleepConfig(count=60),
        ),
    },
}
