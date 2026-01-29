"""
Factory functions for generating HealthKit test payloads.

These are Python functions (not JSON files) for easier parametrization in tests.
"""

import random
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

# Workout types from apple_sdk.py (snake_case format)
WORKOUT_TYPES = [
    "walking",
    "running",
    "cycling",
    "hiking",
    "swimming",
    "yoga",
    "strength_training",
    "hiit",
    "elliptical",
    "rowing",
    "stair_climbing",
    "cross_training",
    "pilates",
    "dance",
    "tennis",
    "basketball",
    "soccer",
    "golf",
    "boxing",
    "skiing",
]

# Record types with their units and realistic value ranges (min, max)
RECORD_TYPE_CONFIG: dict[str, dict[str, Any]] = {
    # Heart & Cardiovascular
    "HKQuantityTypeIdentifierHeartRate": {"unit": "count/min", "range": (50, 180)},
    "HKQuantityTypeIdentifierRestingHeartRate": {"unit": "count/min", "range": (45, 85)},
    "HKQuantityTypeIdentifierHeartRateVariabilitySDNN": {"unit": "ms", "range": (15, 120)},
    "HKQuantityTypeIdentifierHeartRateRecoveryOneMinute": {"unit": "count/min", "range": (12, 55)},
    "HKQuantityTypeIdentifierWalkingHeartRateAverage": {"unit": "count/min", "range": (80, 130)},
    # Blood & Respiratory
    "HKQuantityTypeIdentifierOxygenSaturation": {"unit": "%", "range": (0.94, 1.0)},
    "HKQuantityTypeIdentifierBloodGlucose": {"unit": "mg/dL", "range": (70, 180)},
    "HKQuantityTypeIdentifierBloodPressureSystolic": {"unit": "mmHg", "range": (90, 140)},
    "HKQuantityTypeIdentifierBloodPressureDiastolic": {"unit": "mmHg", "range": (60, 90)},
    "HKQuantityTypeIdentifierRespiratoryRate": {"unit": "count/min", "range": (12, 20)},
    # Body Composition
    "HKQuantityTypeIdentifierHeight": {"unit": "m", "range": (1.50, 2.05)},
    "HKQuantityTypeIdentifierBodyMass": {"unit": "kg", "range": (45, 120)},
    "HKQuantityTypeIdentifierBodyFatPercentage": {"unit": "%", "range": (0.08, 0.35)},
    "HKQuantityTypeIdentifierBodyMassIndex": {"unit": "count", "range": (18, 35)},
    "HKQuantityTypeIdentifierLeanBodyMass": {"unit": "kg", "range": (35, 90)},
    "HKQuantityTypeIdentifierBodyTemperature": {"unit": "degC", "range": (36.0, 37.5)},
    # Fitness Metrics
    "HKQuantityTypeIdentifierVO2Max": {"unit": "mL/kg/min", "range": (25, 65)},
    "HKQuantityTypeIdentifierSixMinuteWalkTestDistance": {"unit": "m", "range": (300, 700)},
    # Activity - Basic
    "HKQuantityTypeIdentifierStepCount": {"unit": "count", "range": (10, 2000)},
    "HKQuantityTypeIdentifierActiveEnergyBurned": {"unit": "kcal", "range": (5, 500)},
    "HKQuantityTypeIdentifierBasalEnergyBurned": {"unit": "kcal", "range": (50, 150)},
    "HKQuantityTypeIdentifierAppleStandTime": {"unit": "min", "range": (1, 60)},
    "HKQuantityTypeIdentifierAppleExerciseTime": {"unit": "min", "range": (1, 120)},
    "HKQuantityTypeIdentifierFlightsClimbed": {"unit": "count", "range": (1, 30)},
    # Activity - Distance
    "HKQuantityTypeIdentifierDistanceWalkingRunning": {"unit": "m", "range": (50, 15000)},
    "HKQuantityTypeIdentifierDistanceCycling": {"unit": "m", "range": (500, 50000)},
    "HKQuantityTypeIdentifierDistanceSwimming": {"unit": "m", "range": (25, 3000)},
    "HKQuantityTypeIdentifierDistanceDownhillSnowSports": {"unit": "m", "range": (100, 20000)},
    # Walking Metrics
    "HKQuantityTypeIdentifierWalkingStepLength": {"unit": "m", "range": (0.4, 0.9)},
    "HKQuantityTypeIdentifierWalkingSpeed": {"unit": "m/s", "range": (0.8, 2.0)},
    "HKQuantityTypeIdentifierWalkingDoubleSupportPercentage": {"unit": "%", "range": (0.2, 0.4)},
    "HKQuantityTypeIdentifierWalkingAsymmetryPercentage": {"unit": "%", "range": (0.0, 0.15)},
    "HKQuantityTypeIdentifierAppleWalkingSteadiness": {"unit": "%", "range": (0.7, 1.0)},
    "HKQuantityTypeIdentifierStairDescentSpeed": {"unit": "m/s", "range": (0.3, 0.8)},
    "HKQuantityTypeIdentifierStairAscentSpeed": {"unit": "m/s", "range": (0.2, 0.6)},
    # Running Metrics
    "HKQuantityTypeIdentifierRunningPower": {"unit": "W", "range": (150, 450)},
    "HKQuantityTypeIdentifierRunningSpeed": {"unit": "m/s", "range": (2.0, 6.0)},
    "HKQuantityTypeIdentifierRunningVerticalOscillation": {"unit": "cm", "range": (5, 12)},
    "HKQuantityTypeIdentifierRunningGroundContactTime": {"unit": "ms", "range": (180, 300)},
    "HKQuantityTypeIdentifierRunningStrideLength": {"unit": "m", "range": (0.8, 1.8)},
    # Swimming Metrics
    "HKQuantityTypeIdentifierSwimmingStrokeCount": {"unit": "count", "range": (10, 500)},
    # Environmental
    "HKQuantityTypeIdentifierEnvironmentalAudioExposure": {"unit": "dBASPL", "range": (40, 90)},
    "HKQuantityTypeIdentifierHeadphoneAudioExposure": {"unit": "dBASPL", "range": (50, 100)},
}

# Workout-specific configurations for realistic stats
WORKOUT_CONFIGS: dict[str, dict[str, Any]] = {
    "running": {
        "duration_range": (15 * 60, 90 * 60),  # 15-90 min
        "distance_range": (2000, 20000),  # 2-20 km
        "energy_range": (150, 800),
        "hr_range": (120, 180),
        "elevation_range": (0, 300),
    },
    "walking": {
        "duration_range": (15 * 60, 120 * 60),
        "distance_range": (1000, 10000),
        "energy_range": (50, 400),
        "hr_range": (80, 130),
        "elevation_range": (0, 150),
    },
    "cycling": {
        "duration_range": (20 * 60, 180 * 60),
        "distance_range": (5000, 80000),
        "energy_range": (200, 1500),
        "hr_range": (100, 170),
        "elevation_range": (0, 1500),
    },
    "swimming": {
        "duration_range": (15 * 60, 90 * 60),
        "distance_range": (400, 4000),
        "energy_range": (150, 700),
        "hr_range": (100, 160),
        "elevation_range": None,
    },
    "hiking": {
        "duration_range": (60 * 60, 480 * 60),
        "distance_range": (5000, 30000),
        "energy_range": (300, 2000),
        "hr_range": (90, 150),
        "elevation_range": (100, 2000),
    },
    "yoga": {
        "duration_range": (20 * 60, 90 * 60),
        "distance_range": None,
        "energy_range": (50, 200),
        "hr_range": (60, 100),
        "elevation_range": None,
    },
    "strength_training": {
        "duration_range": (20 * 60, 90 * 60),
        "distance_range": None,
        "energy_range": (100, 500),
        "hr_range": (80, 150),
        "elevation_range": None,
    },
    "hiit": {
        "duration_range": (15 * 60, 60 * 60),
        "distance_range": (500, 5000),
        "energy_range": (200, 700),
        "hr_range": (130, 185),
        "elevation_range": None,
    },
}

# Default config for workouts not in WORKOUT_CONFIGS
DEFAULT_WORKOUT_CONFIG = {
    "duration_range": (20 * 60, 60 * 60),
    "distance_range": (1000, 10000),
    "energy_range": (100, 500),
    "hr_range": (90, 160),
    "elevation_range": (0, 100),
}


def create_workout_statistics(
    energy_burned: float = 78.0,
    basal_energy: float = 20.0,
    distance: float = 5000.0,
    heart_rate_avg: float = 145.0,
    heart_rate_min: int = 95,
    heart_rate_max: int = 175,
    duration: float = 3600.0,
    elevation_gain: float | None = None,
) -> list[dict[str, Any]]:
    """Generate workout statistics array."""
    stats = [
        {"type": "duration", "unit": "s", "value": duration},
        {"type": "activeEnergyBurned", "unit": "kcal", "value": energy_burned},
        {"type": "basalEnergyBurned", "unit": "kcal", "value": basal_energy},
        {"type": "distance", "unit": "m", "value": distance},
        {"type": "minHeartRate", "unit": "bpm", "value": heart_rate_min},
        {"type": "averageHeartRate", "unit": "bpm", "value": heart_rate_avg},
        {"type": "maxHeartRate", "unit": "bpm", "value": heart_rate_max},
    ]
    if elevation_gain is not None:
        stats.append({"type": "elevationAscended", "unit": "m", "value": elevation_gain})
    return stats


def create_workout(
    workout_index: int = 0,
    workout_type: str = "HKWorkoutActivityTypeRunning",
    start_date: datetime | None = None,
    duration_seconds: int = 3600,
    energy_burned: float = 78.0,
    basal_energy: float = 20.0,
    distance: float = 5000.0,
    heart_rate_avg: float = 145.0,
    heart_rate_min: int = 95,
    heart_rate_max: int = 175,
    elevation_gain: float | None = None,
    uuid: str | None = None,
    include_statistics: bool = True,
) -> dict[str, Any]:
    """Generate a single workout."""
    if start_date is None:
        start_date = datetime(2025, 1, 15, 8 + workout_index, 0, 0, tzinfo=timezone.utc)
    end_date = start_date + timedelta(seconds=duration_seconds)

    workout: dict[str, Any] = {
        "uuid": uuid or f"workout-{workout_index:03d}-{uuid4().hex[:8]}",
        "type": workout_type,
        "startDate": start_date.isoformat().replace("+00:00", "Z"),
        "endDate": end_date.isoformat().replace("+00:00", "Z"),
        "source": {
            "name": "Test Apple Watch",
            "bundleIdentifier": "com.apple.health",
            "deviceManufacturer": "Apple Inc.",
            "deviceModel": "Watch",
            "productType": "Watch7,5",
            "deviceSoftwareVersion": "10.3.1",
        },
    }

    if include_statistics:
        workout["workoutStatistics"] = create_workout_statistics(
            energy_burned=energy_burned,
            basal_energy=basal_energy,
            distance=distance,
            heart_rate_avg=heart_rate_avg,
            heart_rate_min=heart_rate_min,
            heart_rate_max=heart_rate_max,
            duration=float(duration_seconds),
            elevation_gain=elevation_gain,
        )
    else:
        workout["workoutStatistics"] = []

    return workout


def create_record(
    record_index: int = 0,
    record_type: str = "HKQuantityTypeIdentifierStepCount",
    value: float = 100.0,
    unit: str = "count",
    start_date: datetime | None = None,
    duration_seconds: int = 300,
    uuid: str | None = None,
) -> dict[str, Any]:
    """Generate a single health record (time series data)."""
    if start_date is None:
        start_date = datetime(2025, 1, 15, 10, record_index * 5, 0, tzinfo=timezone.utc)
    end_date = start_date + timedelta(seconds=duration_seconds)

    return {
        "uuid": uuid or f"record-{record_index:03d}-{uuid4().hex[:8]}",
        "type": record_type,
        "unit": unit,
        "value": value,
        "startDate": start_date.isoformat().replace("+00:00", "Z"),
        "endDate": end_date.isoformat().replace("+00:00", "Z"),
        "recordMetadata": [],
        "source": {
            "name": "iPhone",
            "bundleIdentifier": "com.apple.health",
            "deviceManufacturer": "Apple Inc.",
            "deviceModel": "iPhone",
            "productType": "iPhone15,2",
            "deviceSoftwareVersion": "17.6.1",
        },
    }


def create_sleep_segment(
    segment_index: int = 0,
    sleep_value: int = 0,
    start_date: datetime | None = None,
    duration_seconds: int = 3600,
    uuid: str | None = None,
) -> dict[str, Any]:
    """Generate a single sleep segment."""
    if start_date is None:
        start_date = datetime(2025, 1, 15, 22, segment_index * 10, 0, tzinfo=timezone.utc)
    end_date = start_date + timedelta(seconds=duration_seconds)

    return {
        "uuid": uuid or f"sleep-{segment_index:03d}-{uuid4().hex[:8]}",
        "type": "HKCategoryTypeIdentifierSleepAnalysis",
        "unit": None,
        "value": sleep_value,
        "startDate": start_date.isoformat().replace("+00:00", "Z"),
        "endDate": end_date.isoformat().replace("+00:00", "Z"),
        "recordMetadata": [{"key": "HKTimeZone", "value": "Europe/Warsaw"}],
        "source": {
            "name": "Test iPhone",
            "bundleIdentifier": "com.apple.health",
            "deviceManufacturer": "Apple Inc.",
            "deviceModel": "iPhone",
            "productType": "iPhone15,2",
            "deviceSoftwareVersion": "17.6.1",
        },
    }


def create_healthkit_payload(
    workout_count: int = 1,
    record_count: int = 0,
    sleep_count: int = 0,
    energy_burned: float = 78.0,
    basal_energy: float = 20.0,
    distance: float = 5000.0,
    heart_rate_avg: float = 145.0,
    heart_rate_min: int = 95,
    heart_rate_max: int = 175,
    workout_type: str = "HKWorkoutActivityTypeRunning",
    include_statistics: bool = True,
    elevation_gain: float | None = None,
) -> dict[str, Any]:
    """
    Generate a complete HealthKit payload with N workouts, records, and sleep segments.

    Args:
        workout_count: Number of workouts to generate
        record_count: Number of health records (e.g., steps) to generate
        sleep_count: Number of sleep segments to generate
        energy_burned: Active energy burned per workout (kcal)
        basal_energy: Basal energy burned per workout (kcal)
        distance: Distance per workout (meters)
        heart_rate_avg: Average heart rate per workout (bpm)
        heart_rate_min: Min heart rate per workout (bpm)
        heart_rate_max: Max heart rate per workout (bpm)
        workout_type: Apple HealthKit workout type
        include_statistics: Whether to include workout statistics
        elevation_gain: Elevation gain per workout (meters), None to exclude

    Returns:
        Complete payload dict ready to be JSON serialized
    """
    workouts = [
        create_workout(
            workout_index=i,
            workout_type=workout_type,
            energy_burned=energy_burned,
            basal_energy=basal_energy,
            distance=distance,
            heart_rate_avg=heart_rate_avg,
            heart_rate_min=heart_rate_min,
            heart_rate_max=heart_rate_max,
            include_statistics=include_statistics,
            elevation_gain=elevation_gain,
        )
        for i in range(workout_count)
    ]

    records = [create_record(record_index=i) for i in range(record_count)]

    sleep = [create_sleep_segment(segment_index=i) for i in range(sleep_count)]

    return {"data": {"workouts": workouts, "records": records, "sleep": sleep}}


def create_empty_payload() -> dict[str, Any]:
    """Generate an empty payload with no data."""
    return {"data": {"workouts": [], "records": [], "sleep": []}}


def create_multi_workout_payload_with_unique_stats(
    workout_configs: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Generate a payload with multiple workouts, each having unique statistics.

    Args:
        workout_configs: List of dicts with workout parameters. Each dict can contain:
            - energy_burned: float (active energy)
            - basal_energy: float (defaults to 0 for easier total calculation)
            - distance: float (meters)
            - heart_rate_avg: float (bpm)
            - heart_rate_min: int (bpm)
            - heart_rate_max: int (bpm)
            - elevation_gain: float | None (meters)

    Returns:
        Complete payload with workouts having unique statistics

    Example:
        payload = create_multi_workout_payload_with_unique_stats([
            {"energy_burned": 100, "distance": 5000, "heart_rate_avg": 140},
            {"energy_burned": 200, "distance": 10000, "heart_rate_avg": 155},
            {"energy_burned": 150, "distance": 7500, "heart_rate_avg": 148},
        ])
    """
    workouts = []
    for i, config in enumerate(workout_configs):
        workout = create_workout(
            workout_index=i,
            energy_burned=config.get("energy_burned", 100.0),
            basal_energy=config.get("basal_energy", 0.0),  # Default 0 for easier assertions
            distance=config.get("distance", 5000.0),
            heart_rate_avg=config.get("heart_rate_avg", 145.0),
            heart_rate_min=config.get("heart_rate_min", 95),
            heart_rate_max=config.get("heart_rate_max", 175),
            elevation_gain=config.get("elevation_gain"),
        )
        workouts.append(workout)

    return {"data": {"workouts": workouts, "records": [], "sleep": []}}


def create_realistic_workout_payload() -> dict[str, Any]:
    """
    Generate a realistic HealthKit payload based on actual Apple Watch export format.

    This matches the real payload structure from Apple Health.
    """
    return {
        "data": {
            "records": [
                {
                    "uuid": "ED008640-6873-4647-92B2-24F7680014A0",
                    "type": "HKQuantityTypeIdentifierStepCount",
                    "unit": "count",
                    "value": 66,
                    "startDate": "2022-05-28T23:56:11Z",
                    "endDate": "2022-05-29T00:02:58Z",
                    "recordMetadata": [],
                    "source": {
                        "name": "iPhone",
                        "bundleIdentifier": "com.apple.health",
                        "deviceManufacturer": "Apple Inc.",
                        "deviceModel": "iPhone",
                        "productType": "iPhone10,5",
                        "deviceHardwareVersion": "iPhone10,5",
                        "deviceSoftwareVersion": "15.4.1",
                        "operatingSystemVersion": {
                            "majorVersion": 15,
                            "minorVersion": 4,
                            "patchVersion": 1,
                        },
                    },
                }
            ],
            "sleep": [
                {
                    "uuid": "E3D5647B-2B0E-43AA-BE3F-9FAD43D35581",
                    "type": "HKCategoryTypeIdentifierSleepAnalysis",
                    "unit": None,
                    "value": 0,
                    "startDate": "2025-04-02T21:50:46Z",
                    "endDate": "2025-04-02T21:50:50Z",
                    "recordMetadata": [{"key": "HKTimeZone", "value": "Europe/Warsaw"}],
                    "source": {
                        "name": "Kamil's iPhone",
                        "bundleIdentifier": "com.apple.health",
                        "deviceManufacturer": "Apple Inc.",
                        "deviceModel": "iPhone",
                        "productType": "iPhone15,2",
                        "deviceSoftwareVersion": "17.6.1",
                        "operatingSystemVersion": {
                            "majorVersion": 17,
                            "minorVersion": 6,
                            "patchVersion": 1,
                        },
                    },
                }
            ],
            "workouts": [
                {
                    "uuid": "801B68D7-F4AA-4A23-BD26-A3BA1BA6B08D",
                    "type": "walking",
                    "startDate": "2025-03-25T17:27:00Z",
                    "endDate": "2025-03-26T18:51:24Z",
                    "source": {
                        "name": "Kamil's Apple Watch",
                        "bundleIdentifier": "com.apple.health",
                        "deviceManufacturer": "Apple Inc.",
                        "deviceModel": "Watch",
                        "productType": "Watch7,5",
                        "deviceHardwareVersion": "Watch7,5",
                        "deviceSoftwareVersion": "10.3.1",
                        "operatingSystemVersion": {
                            "majorVersion": 10,
                            "minorVersion": 3,
                            "patchVersion": 1,
                        },
                    },
                    "workoutStatistics": [
                        {"type": "duration", "unit": "s", "value": 1683.27},
                        {"type": "activeEnergyBurned", "unit": "kcal", "value": 131.41},
                        {"type": "basalEnergyBurned", "unit": "kcal", "value": 48.59},
                        {"type": "distance", "unit": "m", "value": 2165.35},
                        {"type": "minHeartRate", "unit": "bpm", "value": 77},
                        {"type": "averageHeartRate", "unit": "bpm", "value": 121.49},
                        {"type": "maxHeartRate", "unit": "bpm", "value": 141},
                        {"type": "elevationAscended", "unit": "m", "value": 15.57},
                        {"type": "averageMETs", "unit": "kcal/kg/hr", "value": 1.6},
                        {"type": "indoorWorkout", "unit": "bool", "value": False},
                        {"type": "weatherTemperature", "unit": "degC", "value": 11.19},
                        {"type": "weatherHumidity", "unit": "%", "value": 66},
                    ],
                }
            ],
        }
    }


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


def _generate_realistic_workouts(start_date: datetime, end_date: datetime, count: int) -> list[dict[str, Any]]:
    """Generate realistic workout records distributed across the date range."""
    workouts = []
    total_seconds = (end_date - start_date).total_seconds()

    for i in range(count):
        # Distribute workouts across the date range
        workout_type = random.choice(WORKOUT_TYPES)
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
        stats = [
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
        outdoor_types = ["walking", "running", "cycling", "hiking", "golf", "tennis", "soccer"]
        if workout_type in outdoor_types and random.random() > 0.5:
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
            "type": workout_type,
            "startDate": workout_start.isoformat().replace("+00:00", "Z"),
            "endDate": workout_end.isoformat().replace("+00:00", "Z"),
            "source": _generate_watch_source(),
            "workoutStatistics": stats,
        }
        workouts.append(workout)

    return sorted(workouts, key=lambda w: w["startDate"])


def _generate_realistic_records(start_date: datetime, end_date: datetime, count: int) -> list[dict[str, Any]]:
    """Generate realistic health records distributed across the date range."""
    records = []
    total_seconds = (end_date - start_date).total_seconds()

    # Weight distribution: more common record types appear more often
    common_types = [
        "HKQuantityTypeIdentifierStepCount",
        "HKQuantityTypeIdentifierHeartRate",
        "HKQuantityTypeIdentifierActiveEnergyBurned",
        "HKQuantityTypeIdentifierDistanceWalkingRunning",
        "HKQuantityTypeIdentifierBasalEnergyBurned",
    ]
    rare_types = [t for t in RECORD_TYPE_CONFIG if t not in common_types]

    for i in range(count):
        # 70% common types, 30% rare types
        record_type = random.choice(common_types) if random.random() < 0.7 else random.choice(rare_types)

        config = RECORD_TYPE_CONFIG[record_type]
        val_min, val_max = config["range"]
        value = round(random.uniform(val_min, val_max), 2)

        # For step count, use integers
        if "StepCount" in record_type or "FlightsClimbed" in record_type:
            value = int(value)

        # Random time within range
        offset_seconds = random.uniform(0, total_seconds)
        record_start = start_date + timedelta(seconds=offset_seconds)

        # Duration depends on type
        if "StepCount" in record_type:
            duration = random.randint(60, 900)  # 1-15 min
        elif "HeartRate" in record_type:
            duration = random.randint(1, 60)  # 1-60 sec
        elif "Energy" in record_type:
            duration = random.randint(300, 3600)  # 5-60 min
        else:
            duration = random.randint(1, 300)  # 1 sec - 5 min

        record_end = record_start + timedelta(seconds=duration)

        record = {
            "uuid": str(uuid4()).upper(),
            "type": record_type,
            "unit": config["unit"],
            "value": value,
            "startDate": record_start.isoformat().replace("+00:00", "Z"),
            "endDate": record_end.isoformat().replace("+00:00", "Z"),
            "recordMetadata": [],
            "source": _generate_phone_source() if random.random() > 0.3 else _generate_watch_source(),
        }
        records.append(record)

    return sorted(records, key=lambda r: r["startDate"])


def _generate_realistic_sleep(start_date: datetime, end_date: datetime, count: int) -> list[dict[str, Any]]:
    """
    Generate realistic sleep sessions.
    Each session contains multiple segments (in_bed, awake, core, deep, rem).
    """
    sleep_records = []
    total_days = (end_date - start_date).days

    for i in range(count):
        # Pick a night within the range
        night_offset = random.randint(0, max(0, total_days - 1))
        night_start = start_date + timedelta(days=night_offset)

        # Sleep typically starts between 21:00 and 01:00
        sleep_hour = random.choices([21, 22, 23, 0, 1], weights=[1, 3, 4, 2, 1])[0]
        if sleep_hour < 12:
            night_start = night_start + timedelta(days=1)
        sleep_start = night_start.replace(hour=sleep_hour, minute=random.randint(0, 59), second=0, microsecond=0)

        # Total sleep duration: 4-10 hours
        total_sleep_minutes = random.randint(240, 600)
        current_time = sleep_start

        # Generate sleep phases
        # Sleep phases: 0=in_bed, 1=asleep_unspecified, 2=awake, 3=core, 4=deep, 5=rem
        phases_remaining = total_sleep_minutes

        # Start with "in bed" phase (5-30 min)
        in_bed_duration = random.randint(5, 30)
        sleep_records.append(_create_sleep_record(current_time, in_bed_duration, 0))
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
                sleep_records.append(_create_sleep_record(current_time, core_duration, 3))
                current_time += timedelta(minutes=core_duration)
                phases_remaining -= core_duration

            # Deep sleep: 15-25% of cycle (more in early cycles)
            deep_factor = 0.25 - (cycle * 0.03)  # Decreases in later cycles
            deep_duration = int(remaining_in_cycle * max(0.1, deep_factor))
            if deep_duration > 0 and phases_remaining > 0:
                sleep_records.append(_create_sleep_record(current_time, deep_duration, 4))
                current_time += timedelta(minutes=deep_duration)
                phases_remaining -= deep_duration

            # REM sleep: 15-25% of cycle (more in later cycles)
            rem_factor = 0.15 + (cycle * 0.03)  # Increases in later cycles
            rem_duration = int(remaining_in_cycle * min(0.3, rem_factor))
            if rem_duration > 0 and phases_remaining > 0:
                sleep_records.append(_create_sleep_record(current_time, rem_duration, 5))
                current_time += timedelta(minutes=rem_duration)
                phases_remaining -= rem_duration

            # Brief awakening between cycles (10% chance, 1-5 min)
            if random.random() < 0.1 and phases_remaining > 5:
                awake_duration = random.randint(1, 5)
                sleep_records.append(_create_sleep_record(current_time, awake_duration, 2))
                current_time += timedelta(minutes=awake_duration)
                phases_remaining -= awake_duration

    return sorted(sleep_records, key=lambda s: s["startDate"])


def _create_sleep_record(start_time: datetime, duration_minutes: int, phase: int) -> dict[str, Any]:
    """Create a single sleep record segment."""
    end_time = start_time + timedelta(minutes=duration_minutes)
    return {
        "uuid": str(uuid4()).upper(),
        "type": "HKCategoryTypeIdentifierSleepAnalysis",
        "unit": None,
        "value": phase,
        "startDate": start_time.isoformat().replace("+00:00", "Z"),
        "endDate": end_time.isoformat().replace("+00:00", "Z"),
        "recordMetadata": [{"key": "HKTimeZone", "value": "Europe/Warsaw"}],
        "source": _generate_phone_source(),
    }


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
