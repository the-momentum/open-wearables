"""Constants and configuration for seed data generation."""

import logging
from dataclasses import dataclass, field
from enum import Enum
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


class Cadence(str, Enum):
    INTRADAY = "intraday"
    DAILY = "daily"
    DAILY_MORNING = "daily_morning"
    WEEKLY = "weekly"
    WORKOUT_BOUND = "workout_bound"
    PAIRED = "paired"


@dataclass(frozen=True)
class SeriesTypeGenSpec:
    """Generation parameters for a single series type loaded from YAML."""

    cadence: Cadence
    min_value: float = 0.0
    max_value: float = 0.0
    interval_seconds: int | None = None
    workout_types: frozenset[WorkoutType] = field(default_factory=frozenset)


@dataclass(frozen=True)
class PairedGenSpec:
    """Paired-emission spec - emits multiple series types at the same timestamp."""

    cadence: Cadence  # how often to emit (DAILY, WEEKLY, ...)
    members: dict[SeriesType, tuple[float, float]]  # series_type -> (min, max)


def _load_series_type_config() -> tuple[dict[SeriesType, SeriesTypeGenSpec], list[PairedGenSpec]]:
    """Load and validate the YAML series-type config.

    Returns (specs, paired_specs):
    - specs: mapping from each SeriesType to its generation parameters
    - paired_specs: list of paired emissions (e.g. blood pressure)
    """
    config_path = Path(__file__).parent.parent.parent.parent / "scripts" / "init" / "series_type_config.yaml"
    if not config_path.exists():
        config_path = Path("scripts/init/series_type_config.yaml")

    specs: dict[SeriesType, SeriesTypeGenSpec] = {}
    paired_specs: list[PairedGenSpec] = []

    try:
        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
    except FileNotFoundError:
        log_structured(
            logger,
            "warning",
            "series_type_config.yaml not found - time series generation will be skipped",
            provider="seed_data_service",
            task="load_config",
        )
        return specs, paired_specs

    for name, vals in config.get("series_types", {}).items():
        try:
            cadence = Cadence(vals["cadence"])
        except (KeyError, ValueError):
            log_structured(
                logger,
                "warning",
                f"Skipping '{name}' - missing or invalid cadence",
                provider="seed_data_service",
                task="load_config",
            )
            continue

        if cadence is Cadence.PAIRED:
            paired = _parse_paired(name, vals)
            if paired is not None:
                paired_specs.append(paired)
            continue

        try:
            st = SeriesType(name)
        except ValueError:
            continue

        workout_types: frozenset[WorkoutType] = frozenset()
        if cadence is Cadence.WORKOUT_BOUND:
            workout_types = _parse_workout_types(vals.get("workout_types", []))

        specs[st] = SeriesTypeGenSpec(
            cadence=cadence,
            min_value=float(vals.get("min_value", 0.0)),
            max_value=float(vals.get("max_value", 0.0)),
            interval_seconds=int(vals["interval_seconds"]) if "interval_seconds" in vals else None,
            workout_types=workout_types,
        )

    return specs, paired_specs


def _parse_paired(name: str, vals: dict) -> PairedGenSpec | None:
    try:
        members_raw = vals["members"]
        members: dict[SeriesType, tuple[float, float]] = {}
        for member_name, member_vals in members_raw.items():
            st = SeriesType(member_name)
            members[st] = (float(member_vals["min_value"]), float(member_vals["max_value"]))
        if not members:
            return None
        frequency = Cadence(vals.get("frequency", "daily"))
        return PairedGenSpec(cadence=frequency, members=members)
    except (KeyError, ValueError):
        log_structured(
            logger,
            "warning",
            f"Skipping paired entry '{name}' - malformed members or frequency",
            provider="seed_data_service",
            task="load_config",
        )
        return None


def _parse_workout_types(raw: list[str]) -> frozenset[WorkoutType]:
    result: set[WorkoutType] = set()
    for wt in raw:
        try:
            result.add(WorkoutType(wt))
        except ValueError:
            log_structured(
                logger,
                "warning",
                f"Unknown workout type '{wt}' in series_type_config.yaml",
                provider="seed_data_service",
                task="load_config",
            )
    return frozenset(result)


SERIES_TYPE_SPECS, PAIRED_SERIES_SPECS = _load_series_type_config()
