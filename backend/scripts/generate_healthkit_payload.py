#!/usr/bin/env python3
"""
CLI script to generate realistic HealthKit test payloads.

Usage:
    python scripts/generate_healthkit_payload.py output.json \
        --start-date 2025-01-01 \
        --end-date 2025-01-31 \
        --workouts 50 \
        --records 1000 \
        --sleep 30

    # With seed for reproducibility:
    python scripts/generate_healthkit_payload.py output.json \
        --start-date 2025-01-01 \
        --end-date 2025-01-31 \
        --workouts 100 \
        --records 5000 \
        --sleep 60 \
        --seed 42
"""

import argparse
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.constants.series_types.apple import AppleCategoryType, SDKMetricType, SleepPhase
from app.constants.workout_types.apple_sdk import SDKWorkoutType

# Record types with their HealthKit units and realistic value ranges (min, max)
RECORD_TYPE_CONFIG: dict[SDKMetricType, dict[str, Any]] = {
    # Heart & Cardiovascular
    SDKMetricType.APPLE_HEART_RATE: {"unit": "count/min", "range": (50, 180)},
    SDKMetricType.APPLE_RESTING_HEART_RATE: {"unit": "count/min", "range": (45, 85)},
    SDKMetricType.APPLE_HEART_RATE_VARIABILITY_SDNN: {"unit": "ms", "range": (15, 120)},
    SDKMetricType.HEART_RATE_RECOVERY_ONE_MINUTE: {"unit": "count/min", "range": (12, 55)},
    SDKMetricType.WALKING_HEART_RATE_AVERAGE: {"unit": "count/min", "range": (80, 130)},
    # Blood & Respiratory
    SDKMetricType.APPLE_OXYGEN_SATURATION: {"unit": "%", "range": (0.94, 1.0)},
    SDKMetricType.APPLE_BLOOD_GLUCOSE: {"unit": "mg/dL", "range": (70, 180)},
    SDKMetricType.APPLE_BLOOD_PRESSURE_SYSTOLIC: {"unit": "mmHg", "range": (90, 140)},
    SDKMetricType.APPLE_BLOOD_PRESSURE_DIASTOLIC: {"unit": "mmHg", "range": (60, 90)},
    SDKMetricType.APPLE_RESPIRATORY_RATE: {"unit": "count/min", "range": (12, 20)},
    # Body Composition
    SDKMetricType.APPLE_HEIGHT: {"unit": "m", "range": (1.50, 2.05)},
    SDKMetricType.APPLE_BODY_MASS: {"unit": "kg", "range": (45, 120)},
    SDKMetricType.APPLE_BODY_FAT_PERCENTAGE: {"unit": "%", "range": (0.08, 0.35)},
    SDKMetricType.APPLE_BODY_MASS_INDEX: {"unit": "count", "range": (18, 35)},
    SDKMetricType.LEAN_BODY_MASS: {"unit": "kg", "range": (35, 90)},
    SDKMetricType.APPLE_BODY_TEMPERATURE: {"unit": "degC", "range": (36.0, 37.5)},
    # Fitness Metrics
    SDKMetricType.APPLE_VO2_MAX: {"unit": "mL/kg/min", "range": (25, 65)},
    SDKMetricType.SIX_MINUTE_WALK_TEST_DISTANCE: {"unit": "m", "range": (300, 700)},
    # Activity - Basic
    SDKMetricType.APPLE_STEP_COUNT: {"unit": "count", "range": (10, 2000)},
    SDKMetricType.APPLE_ACTIVE_ENERGY_BURNED: {"unit": "kcal", "range": (5, 500)},
    SDKMetricType.APPLE_BASAL_ENERGY_BURNED: {"unit": "kcal", "range": (50, 150)},
    SDKMetricType.APPLE_STAND_TIME: {"unit": "min", "range": (1, 60)},
    SDKMetricType.APPLE_EXERCISE_TIME: {"unit": "min", "range": (1, 120)},
    SDKMetricType.FLIGHTS_CLIMBED: {"unit": "count", "range": (1, 30)},
    # Activity - Distance
    SDKMetricType.DISTANCE_WALKING_RUNNING: {"unit": "m", "range": (50, 15000)},
    SDKMetricType.DISTANCE_CYCLING: {"unit": "m", "range": (500, 50000)},
    SDKMetricType.DISTANCE_SWIMMING: {"unit": "m", "range": (25, 3000)},
    SDKMetricType.DISTANCE_DOWNHILL_SNOW_SPORTS: {"unit": "m", "range": (100, 20000)},
    # Walking Metrics
    SDKMetricType.WALKING_STEP_LENGTH: {"unit": "m", "range": (0.4, 0.9)},
    SDKMetricType.WALKING_SPEED: {"unit": "m/s", "range": (0.8, 2.0)},
    SDKMetricType.WALKING_DOUBLE_SUPPORT_PERCENTAGE: {"unit": "%", "range": (0.2, 0.4)},
    SDKMetricType.WALKING_ASYMMETRY_PERCENTAGE: {"unit": "%", "range": (0.0, 0.15)},
    SDKMetricType.APPLE_WALKING_STEADINESS: {"unit": "%", "range": (0.7, 1.0)},
    SDKMetricType.STAIR_DESCENT_SPEED: {"unit": "m/s", "range": (0.3, 0.8)},
    SDKMetricType.STAIR_ASCENT_SPEED: {"unit": "m/s", "range": (0.2, 0.6)},
    # Running Metrics
    SDKMetricType.RUNNING_POWER: {"unit": "W", "range": (150, 450)},
    SDKMetricType.RUNNING_SPEED: {"unit": "m/s", "range": (2.0, 6.0)},
    SDKMetricType.RUNNING_VERTICAL_OSCILLATION: {"unit": "cm", "range": (5, 12)},
    SDKMetricType.RUNNING_GROUND_CONTACT_TIME: {"unit": "ms", "range": (180, 300)},
    SDKMetricType.RUNNING_STRIDE_LENGTH: {"unit": "m", "range": (0.8, 1.8)},
    # Swimming Metrics
    SDKMetricType.SWIMMING_STROKE_COUNT: {"unit": "count", "range": (10, 500)},
    # Environmental
    SDKMetricType.ENVIRONMENTAL_AUDIO_EXPOSURE: {"unit": "dBASPL", "range": (40, 90)},
    SDKMetricType.HEADPHONE_AUDIO_EXPOSURE: {"unit": "dBASPL", "range": (50, 100)},
}

# Workout-specific configurations for realistic stats
WORKOUT_CONFIGS: dict[SDKWorkoutType, dict[str, Any]] = {
    SDKWorkoutType.RUNNING: {
        "duration_range": (15 * 60, 90 * 60),  # 15-90 min
        "distance_range": (2000, 20000),  # 2-20 km
        "energy_range": (150, 800),
        "hr_range": (120, 180),
        "elevation_range": (0, 300),
    },
    SDKWorkoutType.WALKING: {
        "duration_range": (15 * 60, 120 * 60),
        "distance_range": (1000, 10000),
        "energy_range": (50, 400),
        "hr_range": (80, 130),
        "elevation_range": (0, 150),
    },
    SDKWorkoutType.CYCLING: {
        "duration_range": (20 * 60, 180 * 60),
        "distance_range": (5000, 80000),
        "energy_range": (200, 1500),
        "hr_range": (100, 170),
        "elevation_range": (0, 1500),
    },
    SDKWorkoutType.SWIMMING: {
        "duration_range": (15 * 60, 90 * 60),
        "distance_range": (400, 4000),
        "energy_range": (150, 700),
        "hr_range": (100, 160),
        "elevation_range": None,
    },
    SDKWorkoutType.HIKING: {
        "duration_range": (60 * 60, 480 * 60),
        "distance_range": (5000, 30000),
        "energy_range": (300, 2000),
        "hr_range": (90, 150),
        "elevation_range": (100, 2000),
    },
    SDKWorkoutType.YOGA: {
        "duration_range": (20 * 60, 90 * 60),
        "distance_range": None,
        "energy_range": (50, 200),
        "hr_range": (60, 100),
        "elevation_range": None,
    },
    SDKWorkoutType.STRENGTH_TRAINING: {
        "duration_range": (20 * 60, 90 * 60),
        "distance_range": None,
        "energy_range": (100, 500),
        "hr_range": (80, 150),
        "elevation_range": None,
    },
    SDKWorkoutType.HIIT: {
        "duration_range": (15 * 60, 60 * 60),
        "distance_range": (500, 5000),
        "energy_range": (200, 700),
        "hr_range": (130, 185),
        "elevation_range": None,
    },
}

# Default config for workouts not in WORKOUT_CONFIGS
DEFAULT_WORKOUT_CONFIG: dict[str, Any] = {
    "duration_range": (20 * 60, 60 * 60),
    "distance_range": (1000, 10000),
    "energy_range": (100, 500),
    "hr_range": (90, 160),
    "elevation_range": (0, 100),
}

# Outdoor workout types that may include weather data
OUTDOOR_WORKOUT_TYPES: set[SDKWorkoutType] = {
    SDKWorkoutType.WALKING,
    SDKWorkoutType.RUNNING,
    SDKWorkoutType.CYCLING,
    SDKWorkoutType.HIKING,
    SDKWorkoutType.GOLF,
    SDKWorkoutType.TENNIS,
    SDKWorkoutType.SOCCER,
}

# Common record types that appear more frequently in real data
COMMON_RECORD_TYPES: list[SDKMetricType] = [
    SDKMetricType.APPLE_STEP_COUNT,
    SDKMetricType.APPLE_HEART_RATE,
    SDKMetricType.APPLE_ACTIVE_ENERGY_BURNED,
    SDKMetricType.DISTANCE_WALKING_RUNNING,
    SDKMetricType.APPLE_BASAL_ENERGY_BURNED,
]

# Record types that should produce integer values
INTEGER_RECORD_TYPES: set[SDKMetricType] = {
    SDKMetricType.APPLE_STEP_COUNT,
    SDKMetricType.FLIGHTS_CLIMBED,
}

# All workout types available from the SDK
ALL_WORKOUT_TYPES: list[SDKWorkoutType] = list(SDKWorkoutType)


def _generate_watch_source() -> dict[str, Any]:
    """Generate a realistic Apple Watch source."""
    watch_models = [
        ("Watch6,1", "8.0"),
        ("Watch6,2", "8.5"),
        ("Watch7,1", "9.0"),
        ("Watch7,3", "10.0"),
        ("Watch7,5", "10.3.1"),
    ]
    model, sw_version = random.choice(watch_models)
    major = int(sw_version.split(".")[0])

    return {
        "name": "Apple Watch",
        "bundleIdentifier": "com.apple.health",
        "deviceManufacturer": "Apple Inc.",
        "deviceModel": "Watch",
        "productType": model,
        "deviceHardwareVersion": model,
        "deviceSoftwareVersion": sw_version,
        "operatingSystemVersion": {
            "majorVersion": major,
            "minorVersion": int(sw_version.split(".")[1]) if "." in sw_version else 0,
            "patchVersion": int(sw_version.split(".")[2]) if sw_version.count(".") > 1 else 0,
        },
    }


def _generate_phone_source() -> dict[str, Any]:
    """Generate a realistic iPhone source."""
    phone_models = [
        ("iPhone14,2", "16.0"),
        ("iPhone14,5", "16.5"),
        ("iPhone15,2", "17.0"),
        ("iPhone15,3", "17.4"),
        ("iPhone16,1", "17.6.1"),
    ]
    model, sw_version = random.choice(phone_models)
    parts = sw_version.split(".")
    major = int(parts[0])
    minor = int(parts[1]) if len(parts) > 1 else 0
    patch = int(parts[2]) if len(parts) > 2 else 0

    return {
        "name": "iPhone",
        "bundleIdentifier": "com.apple.health",
        "deviceManufacturer": "Apple Inc.",
        "deviceModel": "iPhone",
        "productType": model,
        "deviceHardwareVersion": model,
        "deviceSoftwareVersion": sw_version,
        "operatingSystemVersion": {
            "majorVersion": major,
            "minorVersion": minor,
            "patchVersion": patch,
        },
    }


def _generate_realistic_workouts(start_date: datetime, end_date: datetime, count: int) -> list[dict[str, Any]]:
    """Generate realistic workout records distributed across the date range."""
    workouts = []
    total_seconds = (end_date - start_date).total_seconds()

    # Use a consistent watch source (like a real user with one Apple Watch)
    watch_source = _generate_watch_source()

    for i in range(count):
        workout_type = random.choice(ALL_WORKOUT_TYPES)
        config = WORKOUT_CONFIGS.get(workout_type, DEFAULT_WORKOUT_CONFIG)

        # Random time within range, preferring morning/evening hours
        hour = random.choices(
            list(range(24)),
            weights=[0.5, 0.2, 0.1, 0.1, 0.1, 0.5, 1, 2, 3, 2, 1.5, 1, 1, 1, 1, 1.5, 2, 3, 3, 2, 1, 0.8, 0.6, 0.5],
        )[0]
        offset_seconds = random.uniform(0, total_seconds)
        workout_start = start_date + timedelta(seconds=offset_seconds)
        workout_start = workout_start.replace(hour=hour, minute=random.randint(0, 59))

        # Duration
        duration_min, duration_max = config["duration_range"]
        duration = random.uniform(duration_min, duration_max)
        workout_end = workout_start + timedelta(seconds=duration)

        # Energy
        energy_min, energy_max = config["energy_range"]
        active_energy = round(random.uniform(energy_min, energy_max), 2)
        basal_energy = round(duration / 3600 * random.uniform(40, 70), 2)

        # Distance
        distance = None
        if config["distance_range"]:
            dist_min, dist_max = config["distance_range"]
            distance = round(random.uniform(dist_min, dist_max), 2)

        # Heart rate
        hr_min_range, hr_max_range = config["hr_range"]
        hr_avg = round(random.uniform(hr_min_range, hr_max_range), 2)
        hr_min = max(50, int(hr_avg - random.uniform(20, 40)))
        hr_max = min(200, int(hr_avg + random.uniform(15, 35)))

        # Elevation
        elevation = None
        if config["elevation_range"]:
            elev_min, elev_max = config["elevation_range"]
            elevation = round(random.uniform(elev_min, elev_max), 2)

        # Build statistics
        stats: list[dict[str, Any]] = [
            {"type": "duration", "unit": "s", "value": round(duration, 2)},
            {"type": "activeEnergyBurned", "unit": "kcal", "value": active_energy},
            {"type": "basalEnergyBurned", "unit": "kcal", "value": basal_energy},
            {"type": "minHeartRate", "unit": "bpm", "value": hr_min},
            {"type": "averageHeartRate", "unit": "bpm", "value": hr_avg},
            {"type": "maxHeartRate", "unit": "bpm", "value": hr_max},
        ]

        if distance is not None:
            stats.append({"type": "distance", "unit": "m", "value": distance})

        if elevation is not None:
            stats.append({"type": "elevationAscended", "unit": "m", "value": elevation})

        # Optional weather (50% chance for outdoor activities)
        if workout_type in OUTDOOR_WORKOUT_TYPES and random.random() > 0.5:
            stats.extend(
                [
                    {"type": "weatherTemperature", "unit": "degC", "value": round(random.uniform(-5, 35), 2)},
                    {"type": "weatherHumidity", "unit": "%", "value": random.randint(20, 95)},
                ]
            )

        # Add METs for some workouts
        if random.random() > 0.3:
            stats.append({"type": "averageMETs", "unit": "kcal/kg/hr", "value": round(random.uniform(1.0, 12.0), 2)})

        workout = {
            "uuid": str(uuid4()).upper(),
            "type": workout_type.value,
            "startDate": workout_start.isoformat().replace("+00:00", "Z"),
            "endDate": workout_end.isoformat().replace("+00:00", "Z"),
            "source": watch_source,
            "workoutStatistics": stats,
        }
        workouts.append(workout)

    return sorted(workouts, key=lambda w: w["startDate"])


def _generate_realistic_records(start_date: datetime, end_date: datetime, count: int) -> list[dict[str, Any]]:
    """Generate realistic health records distributed across the date range."""
    records = []
    total_seconds = (end_date - start_date).total_seconds()

    rare_types = [t for t in RECORD_TYPE_CONFIG if t not in COMMON_RECORD_TYPES]

    # Use consistent device sources (like a real user with one phone + one watch)
    phone_source = _generate_phone_source()
    watch_source = _generate_watch_source()

    for i in range(count):
        # 70% common types, 30% rare types
        record_type = random.choice(COMMON_RECORD_TYPES) if random.random() < 0.7 else random.choice(rare_types)

        config = RECORD_TYPE_CONFIG[record_type]
        val_min, val_max = config["range"]
        value = round(random.uniform(val_min, val_max), 2)

        if record_type in INTEGER_RECORD_TYPES:
            value = int(value)

        # Random time within range
        offset_seconds = random.uniform(0, total_seconds)
        record_start = start_date + timedelta(seconds=offset_seconds)

        # Duration depends on type
        if record_type == SDKMetricType.APPLE_STEP_COUNT:
            duration = random.randint(60, 900)  # 1-15 min
        elif record_type in (SDKMetricType.APPLE_HEART_RATE, SDKMetricType.APPLE_RESTING_HEART_RATE):
            duration = random.randint(1, 60)  # 1-60 sec
        elif record_type in (SDKMetricType.APPLE_ACTIVE_ENERGY_BURNED, SDKMetricType.APPLE_BASAL_ENERGY_BURNED):
            duration = random.randint(300, 3600)  # 5-60 min
        else:
            duration = random.randint(1, 300)  # 1 sec - 5 min

        record_end = record_start + timedelta(seconds=duration)

        record = {
            "uuid": str(uuid4()).upper(),
            "type": record_type.value,
            "unit": config["unit"],
            "value": value,
            "startDate": record_start.isoformat().replace("+00:00", "Z"),
            "endDate": record_end.isoformat().replace("+00:00", "Z"),
            "recordMetadata": [],
            "source": phone_source if random.random() > 0.3 else watch_source,
        }
        records.append(record)

    return sorted(records, key=lambda r: r["startDate"])


def _create_sleep_record(
    start_time: datetime, duration_minutes: int, phase: SleepPhase, source: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Create a single sleep record segment."""
    end_time = start_time + timedelta(minutes=duration_minutes)
    return {
        "uuid": str(uuid4()).upper(),
        "type": AppleCategoryType.SLEEP_ANALYSIS.value,
        "unit": None,
        "value": phase.value,
        "startDate": start_time.isoformat().replace("+00:00", "Z"),
        "endDate": end_time.isoformat().replace("+00:00", "Z"),
        "recordMetadata": [{"key": "HKTimeZone", "value": "Europe/Warsaw"}],
        "source": source or _generate_phone_source(),
    }


def _generate_realistic_sleep(start_date: datetime, end_date: datetime, count: int) -> list[dict[str, Any]]:
    """
    Generate realistic sleep sessions.
    Each session contains multiple segments (in_bed, awake, core, deep, rem).
    """
    sleep_records = []
    total_days = (end_date - start_date).days

    # Use a consistent phone source across all sleep sessions (like a real user)
    phone_source = _generate_phone_source()

    # Pick unique nights so sessions don't overlap on the same calendar night
    available_nights = list(range(max(1, total_days)))
    if count <= len(available_nights):
        chosen_nights = sorted(random.sample(available_nights, count))
    else:
        # More sessions requested than available nights – allow duplicates as fallback
        chosen_nights = sorted(random.choices(available_nights, k=count))

    for night_offset in chosen_nights:
        night_start = start_date + timedelta(days=night_offset)

        # Sleep typically starts between 21:00 and 01:00
        sleep_hour = random.choices([21, 22, 23, 0, 1], weights=[1, 3, 4, 2, 1])[0]
        if sleep_hour < 12:
            night_start = night_start + timedelta(days=1)
        sleep_start = night_start.replace(hour=sleep_hour, minute=random.randint(0, 59), second=0, microsecond=0)

        # All segments in a session come from the same device
        session_source = phone_source

        # Total sleep duration: 4-10 hours
        total_sleep_minutes = random.randint(240, 600)
        current_time = sleep_start
        phases_remaining = total_sleep_minutes

        # Start with "in bed" phase (5-30 min)
        in_bed_duration = random.randint(5, 30)
        sleep_records.append(
            _create_sleep_record(current_time, in_bed_duration, SleepPhase.IN_BED, source=session_source)
        )
        current_time += timedelta(minutes=in_bed_duration)
        phases_remaining -= in_bed_duration

        # Generate sleep cycles (typically 4-6 cycles of 90 min each)
        num_cycles = random.randint(3, 6)
        cycle_duration = phases_remaining // num_cycles

        for cycle in range(num_cycles):
            remaining_in_cycle = min(cycle_duration, phases_remaining)
            if remaining_in_cycle <= 0:
                break

            # Each cycle: light(core) -> deep -> REM (with possible awake)
            # Core sleep: 40-60% of cycle
            core_duration = int(remaining_in_cycle * random.uniform(0.4, 0.6))
            if core_duration > 0:
                sleep_records.append(
                    _create_sleep_record(current_time, core_duration, SleepPhase.ASLEEP_LIGHT, source=session_source)
                )
                current_time += timedelta(minutes=core_duration)
                phases_remaining -= core_duration

            # Deep sleep: 15-25% of cycle (more in early cycles)
            deep_factor = 0.25 - (cycle * 0.03)  # Decreases in later cycles
            deep_duration = int(remaining_in_cycle * max(0.1, deep_factor))
            if deep_duration > 0 and phases_remaining > 0:
                sleep_records.append(
                    _create_sleep_record(current_time, deep_duration, SleepPhase.ASLEEP_DEEP, source=session_source)
                )
                current_time += timedelta(minutes=deep_duration)
                phases_remaining -= deep_duration

            # REM sleep: 15-25% of cycle (more in later cycles)
            rem_factor = 0.15 + (cycle * 0.03)  # Increases in later cycles
            rem_duration = int(remaining_in_cycle * min(0.3, rem_factor))
            if rem_duration > 0 and phases_remaining > 0:
                sleep_records.append(
                    _create_sleep_record(current_time, rem_duration, SleepPhase.ASLEEP_REM, source=session_source)
                )
                current_time += timedelta(minutes=rem_duration)
                phases_remaining -= rem_duration

            # Brief awakening between cycles (10% chance, 1-5 min)
            if random.random() < 0.1 and phases_remaining > 5:
                awake_duration = random.randint(1, 5)
                sleep_records.append(
                    _create_sleep_record(current_time, awake_duration, SleepPhase.AWAKE, source=session_source)
                )
                current_time += timedelta(minutes=awake_duration)
                phases_remaining -= awake_duration

    return sorted(sleep_records, key=lambda s: s["startDate"])


def generate_realistic_payload(
    start_date: datetime,
    end_date: datetime,
    workouts_count: int = 10,
    records_count: int = 100,
    sleep_records_count: int = 10,
    seed: int | None = None,
) -> dict[str, Any]:
    """
    Generate a large, realistic HealthKit payload for testing.

    Args:
        start_date: Start of the date range (timezone-aware)
        end_date: End of the date range (timezone-aware)
        workouts_count: Number of workouts to generate
        records_count: Number of health records to generate
        sleep_records_count: Number of sleep sessions to generate
        seed: Random seed for reproducibility (optional)

    Returns:
        Complete payload dict matching the real Apple HealthKit export format
    """
    if seed is not None:
        random.seed(seed)

    total_days = (end_date - start_date).days
    if total_days <= 0:
        raise ValueError("end_date must be after start_date")

    workouts = _generate_realistic_workouts(start_date, end_date, workouts_count)
    records = _generate_realistic_records(start_date, end_date, records_count)
    sleep = _generate_realistic_sleep(start_date, end_date, sleep_records_count)

    return {"data": {"workouts": workouts, "records": records, "sleep": sleep}}


def parse_date(date_str: str) -> datetime:
    """Parse date string (YYYY-MM-DD) to timezone-aware datetime."""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.replace(tzinfo=timezone.utc)
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid date format: {date_str}. Use YYYY-MM-DD")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate realistic HealthKit test payloads",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s output.json --start-date 2025-01-01 --end-date 2025-01-31 --workouts 50 --records 1000 --sleep 30
  %(prog)s large_payload.json -s 2024-01-01 -e 2024-12-31 -w 365 -r 10000 -l 365 --seed 42
        """,
    )

    parser.add_argument("output", type=str, help="Output JSON file path")
    parser.add_argument("-s", "--start-date", type=parse_date, required=True, help="Start date (YYYY-MM-DD)")
    parser.add_argument("-e", "--end-date", type=parse_date, required=True, help="End date (YYYY-MM-DD)")
    parser.add_argument("-w", "--workouts", type=int, default=10, help="Number of workouts to generate (default: 10)")
    parser.add_argument(
        "-r", "--records", type=int, default=100, help="Number of health records to generate (default: 100)"
    )
    parser.add_argument(
        "-l", "--sleep", type=int, default=10, help="Number of sleep sessions to generate (default: 10)"
    )
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility (optional)")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output (larger file size)")

    args = parser.parse_args()

    if args.end_date <= args.start_date:
        parser.error("end-date must be after start-date")

    print("Generating payload...")
    print(f"  Date range: {args.start_date.date()} to {args.end_date.date()}")
    print(f"  Workouts: {args.workouts}")
    print(f"  Records: {args.records}")
    print(f"  Sleep sessions: {args.sleep}")
    if args.seed is not None:
        print(f"  Seed: {args.seed}")

    payload = generate_realistic_payload(
        start_date=args.start_date,
        end_date=args.end_date,
        workouts_count=args.workouts,
        records_count=args.records,
        sleep_records_count=args.sleep,
        seed=args.seed,
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    indent = 2 if args.pretty else None
    with open(output_path, "w") as f:
        json.dump(payload, f, indent=indent)

    file_size = output_path.stat().st_size
    if file_size > 1024 * 1024:
        size_str = f"{file_size / (1024 * 1024):.2f} MB"
    elif file_size > 1024:
        size_str = f"{file_size / 1024:.2f} KB"
    else:
        size_str = f"{file_size} bytes"

    print(f"\nGenerated: {output_path} ({size_str})")
    print(f"  Workouts: {len(payload['data']['workouts'])}")
    print(f"  Records: {len(payload['data']['records'])}")
    print(f"  Sleep records: {len(payload['data']['sleep'])}")


if __name__ == "__main__":
    main()
