"""Constants and configuration for seed data generation."""

import logging
from pathlib import Path

import yaml

from app.schemas.enums import ProviderName, SeriesType, WorkoutType
from app.utils.structured_logging import log_structured

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Provider & demographic constants
# ---------------------------------------------------------------------------

GENDERS = ["female", "male", "nonbinary", "other"]

PROVIDER_CONFIGS: dict[ProviderName, dict] = {
    ProviderName.APPLE: {
        "source_name": "Apple Health",
        "manufacturer": "Apple Inc.",
        "devices": ["Apple Watch Series 6", "Apple Watch Series 7", "Apple Watch Ultra"],
        "os_versions": ["8.0", "9.0", "9.1"],
    },
    ProviderName.GARMIN: {
        "source_name": "Garmin Connect",
        "manufacturer": "Garmin",
        "devices": ["Fenix 7", "Forerunner 965", "Epix Gen 2"],
        "os_versions": ["12.00", "13.22"],
    },
    ProviderName.POLAR: {
        "source_name": "Polar Flow",
        "manufacturer": "Polar",
        "devices": ["Vantage V2", "Grit X Pro"],
        "os_versions": ["4.0.11"],
    },
    ProviderName.SUUNTO: {
        "source_name": "Suunto App",
        "manufacturer": "Suunto",
        "devices": ["Suunto 9 Peak", "Suunto Vertical"],
        "os_versions": ["2.25.18"],
    },
    ProviderName.WHOOP: {
        "source_name": "WHOOP",
        "manufacturer": "WHOOP Inc.",
        "devices": ["WHOOP 5.0", "WHOOP 4.0", "WHOOP 3.0"],
        "os_versions": ["5.0", "4.0", "3.0"],
    },
    ProviderName.OURA: {
        "source_name": "Oura",
        "manufacturer": "Oura Health",
        "devices": ["Oura Ring Gen 3", "Oura Ring Gen 4"],
        "os_versions": ["2.0", "3.0"],
    },
}

SEED_PROVIDERS = list(PROVIDER_CONFIGS.keys())

# Workout types where elevation gain is realistic
OUTDOOR_WORKOUT_TYPES: frozenset[WorkoutType] = frozenset(
    {
        WorkoutType.RUNNING,
        WorkoutType.TRAIL_RUNNING,
        WorkoutType.HIKING,
        WorkoutType.CYCLING,
        WorkoutType.MOUNTAIN_BIKING,
        WorkoutType.MOUNTAINEERING,
        WorkoutType.TRAIL_HIKING,
        WorkoutType.CROSS_COUNTRY_SKIING,
        WorkoutType.BACKCOUNTRY_SKIING,
        WorkoutType.ALPINE_SKIING,
        WorkoutType.DOWNHILL_SKIING,
    }
)

# ---------------------------------------------------------------------------
# Health score component keys (match real provider API formats)
# ---------------------------------------------------------------------------

# Oura contributors dicts
_OURA_SLEEP_COMPONENTS = ["deep_sleep", "efficiency", "latency", "rem_sleep", "restfulness", "timing", "total_sleep"]
_OURA_READINESS_COMPONENTS = [
    "activity_balance",
    "body_temperature",
    "hrv_balance",
    "previous_day_activity",
    "previous_night",
    "recovery_index",
    "resting_heart_rate",
    "sleep_balance",
]
_OURA_ACTIVITY_COMPONENTS = [
    "meet_daily_targets",
    "move_every_hour",
    "recovery_time",
    "stay_active",
    "training_frequency",
    "training_volume",
]

# Garmin qualifiers and component keys
_GARMIN_SLEEP_QUALIFIERS = ["EXCELLENT", "GOOD", "FAIR", "POOR"]
_GARMIN_SLEEP_COMPONENTS = ["deepSleep", "remSleep", "restlessness", "sleepDuration", "sleepInterruption"]
# Normalized form matching real parser: raw_qualifier.replace("_", " ").title()
_GARMIN_STRESS_QUALIFIERS = ["Low Stress", "Medium Stress", "High Stress"]


# ---------------------------------------------------------------------------
# Series type configuration (loaded once from YAML)
# ---------------------------------------------------------------------------


def _load_series_type_config() -> tuple[dict[SeriesType, tuple[float, float]], dict[SeriesType, int]]:
    # __file__ = backend/app/services/seed_data/constants.py → .parent x4 = backend/
    config_path = Path(__file__).parent.parent.parent.parent / "scripts" / "init" / "series_type_config.yaml"
    if not config_path.exists():
        config_path = Path("scripts/init/series_type_config.yaml")
    values_ranges: dict[SeriesType, tuple[float, float]] = {}
    percentages: dict[SeriesType, int] = {}

    try:
        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
        for name, vals in config.get("series_types", {}).items():
            try:
                st = SeriesType(name)
                values_ranges[st] = (float(vals["min_value"]), float(vals["max_value"]))
                percentages[st] = int(vals["percentage"])
            except (ValueError, KeyError):
                continue
    except FileNotFoundError:
        log_structured(
            logger,
            "warning",
            "series_type_config.yaml not found - time series generation will be skipped",
            provider="seed_data_service",
            task="load_config",
        )

    return values_ranges, percentages


SERIES_VALUES_RANGES, SERIES_TYPE_PERCENTAGES = _load_series_type_config()
