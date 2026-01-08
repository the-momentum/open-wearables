#!/usr/bin/env python3
"""Seed activity data: create 10 users with comprehensive health data using Faker."""

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import yaml
from faker import Faker

from app.database import SessionLocal
from app.models import EventRecordDetail, PersonalRecord
from app.repositories import CrudRepository
from app.repositories.event_record_detail_repository import EventRecordDetailRepository
from app.schemas.event_record import EventRecordCreate
from app.schemas.event_record_detail import EventRecordDetailCreate
from app.schemas.personal_record import PersonalRecordCreate
from app.schemas.series_types import SeriesType
from app.schemas.timeseries import TimeSeriesSampleCreate
from app.schemas.user import UserCreate
from app.schemas.workout_types import WorkoutType
from app.services import event_record_service, timeseries_service, user_service

logger = logging.getLogger(__name__)
fake = Faker()

# Workout types and sources for variety
WORKOUT_TYPES = list(WorkoutType)

SOURCE_NAMES = [
    "Apple Watch",
    "iPhone",
    "Garmin",
    "Polar",
    "Suunto",
    "Strava",
    "Fitbit",
]

GENDERS = ["female", "male", "nonbinary", "other"]


# Load series type configuration from YAML
def _load_series_type_config() -> tuple[dict[SeriesType, tuple[float, float]], dict[SeriesType, int]]:
    """Load series type configuration from YAML file.

    Returns:
        Tuple of (values_ranges, series_type_percentages) dictionaries
    """
    config_path = Path(__file__).parent / "series_type_config.yaml"
    values_ranges = {}
    series_type_percentages = {}

    with open(config_path, encoding="utf-8") as yamlfile:
        config = yaml.safe_load(yamlfile)

        for series_name, values in config.get("series_types", {}).items():
            try:
                series_type = SeriesType(series_name)
                min_val = float(values["min_value"])
                max_val = float(values["max_value"])
                percentage = int(values["percentage"])

                values_ranges[series_type] = (min_val, max_val)
                series_type_percentages[series_type] = percentage
            except (ValueError, KeyError) as e:
                logger.warning("Skipping invalid series type '%s': %s", series_name, e)
                continue

    return values_ranges, series_type_percentages


try:
    SERIES_VALUES_RANGES, SERIES_TYPE_PERCENTAGES = _load_series_type_config()
except FileNotFoundError:
    logger.error("series_type_config.yaml file not found. Using default configuration.")
    SERIES_VALUES_RANGES = {}
    SERIES_TYPE_PERCENTAGES = {}


def generate_workout(
    user_id: UUID,
    fake_instance: Faker,
) -> tuple[EventRecordCreate, EventRecordDetailCreate]:
    """Generate a single workout with random data."""
    # Generate start datetime within last 6 months
    start_datetime = fake_instance.date_time_between(start_date="-6M", end_date="now", tzinfo=timezone.utc)

    # Duration between 15 minutes and 3 hours
    duration_minutes = fake_instance.random_int(min=15, max=180)
    duration_seconds = duration_minutes * 60

    end_datetime = start_datetime + timedelta(seconds=float(duration_seconds))

    steps = fake_instance.random_int(min=500, max=20000)
    heart_rate_min = fake_instance.random_int(min=90, max=120)
    heart_rate_max = fake_instance.random_int(min=140, max=180)
    heart_rate_avg = Decimal((heart_rate_min + heart_rate_max) / 2)

    workout_id = uuid4()
    device_id = (
        f"device_{fake_instance.random_int(min=1, max=5)}" if fake_instance.boolean(chance_of_getting_true=50) else None
    )

    record = EventRecordCreate(
        id=workout_id,
        provider_name="Faker",
        user_id=user_id,
        category="workout",
        type=fake_instance.random.choice(WORKOUT_TYPES),
        duration_seconds=duration_seconds,
        source_name=fake_instance.random.choice(SOURCE_NAMES),
        device_id=device_id,
        start_datetime=start_datetime,
        end_datetime=end_datetime,
    )

    detail = EventRecordDetailCreate(
        record_id=workout_id,
        heart_rate_min=heart_rate_min,
        heart_rate_max=heart_rate_max,
        heart_rate_avg=heart_rate_avg,
        steps_count=steps,
    )

    return record, detail


def generate_sleep(
    user_id: UUID,
    fake_instance: Faker,
) -> tuple[EventRecordCreate, EventRecordDetailCreate]:
    """Generate a single sleep record with random data."""
    # Generate sleep start datetime within last 6 months (typically evening/night)
    base_datetime = fake_instance.date_time_between(start_date="-6M", end_date="now", tzinfo=timezone.utc)
    # Sleep typically starts between 9 PM and 1 AM
    start_hour = fake_instance.random_int(min=21, max=25) % 24
    start_datetime = base_datetime.replace(hour=start_hour, minute=fake_instance.random_int(min=0, max=59))

    # Sleep duration between 5 and 10 hours
    sleep_duration_minutes = fake_instance.random_int(min=300, max=600)
    sleep_duration_seconds = sleep_duration_minutes * 60
    end_datetime = start_datetime + timedelta(seconds=float(sleep_duration_seconds))

    # Time in bed is typically 15-60 minutes more than sleep duration
    time_in_bed_minutes = sleep_duration_minutes + fake_instance.random_int(min=15, max=60)
    sleep_efficiency = Decimal(
        Decimal(sleep_duration_minutes) / Decimal(time_in_bed_minutes) * Decimal("100"),
    )

    # Sleep stages (should sum to approximately sleep_duration_minutes)
    # Calculate stages ensuring all values are non-negative
    deep_minutes = fake_instance.random_int(min=60, max=min(180, sleep_duration_minutes // 3))
    rem_minutes = fake_instance.random_int(min=60, max=min(150, sleep_duration_minutes // 3))
    awake_minutes = fake_instance.random_int(min=10, max=min(30, sleep_duration_minutes // 10))

    # Light sleep is the remainder, ensuring it's non-negative
    remaining_for_light = sleep_duration_minutes - deep_minutes - rem_minutes - awake_minutes
    light_minutes = max(0, remaining_for_light)

    is_nap = fake_instance.boolean(chance_of_getting_true=20)

    sleep_id = uuid4()
    device_id = (
        f"device_{fake_instance.random_int(min=1, max=3)}" if fake_instance.boolean(chance_of_getting_true=60) else None
    )

    record = EventRecordCreate(
        id=sleep_id,
        provider_name="Faker",
        user_id=user_id,
        category="sleep",
        type=None,
        duration_seconds=sleep_duration_seconds,
        source_name=fake_instance.random.choice(SOURCE_NAMES),
        device_id=device_id,
        start_datetime=start_datetime,
        end_datetime=end_datetime,
    )

    detail = EventRecordDetailCreate(
        record_id=sleep_id,
        sleep_total_duration_minutes=sleep_duration_minutes,
        sleep_time_in_bed_minutes=time_in_bed_minutes,
        sleep_efficiency_score=sleep_efficiency,
        sleep_deep_minutes=deep_minutes,
        sleep_rem_minutes=rem_minutes,
        sleep_light_minutes=light_minutes,
        sleep_awake_minutes=awake_minutes,
        is_nap=is_nap,
    )

    return record, detail


def generate_personal_record(
    user_id: UUID,
    fake_instance: Faker,
) -> PersonalRecordCreate:
    """Generate personal record data for a user."""
    # Birth date between 18 and 80 years ago
    birth_date = fake_instance.date_of_birth(minimum_age=18, maximum_age=80)

    return PersonalRecordCreate(
        id=uuid4(),
        user_id=user_id,
        birth_date=birth_date,
        gender=fake_instance.random.choice(GENDERS) if fake_instance.boolean(chance_of_getting_true=80) else None,
    )


def generate_time_series_samples(
    workout_start: datetime,
    workout_end: datetime,
    fake_instance: Faker,
    *,
    user_id: UUID,
    provider_name: str,
    device_id: str | None = None,
) -> list[TimeSeriesSampleCreate]:
    """Generate time series samples for a workout period with realistic frequencies."""
    samples = []
    current_time = workout_start

    if not SERIES_TYPE_PERCENTAGES or not SERIES_VALUES_RANGES:
        logger.warning("No series type configuration found. Skipping time series samples.")
        return samples

    # Generate samples every 20-60 seconds during the workout
    while current_time <= workout_end:
        for series_type, percentage in SERIES_TYPE_PERCENTAGES.items():
            min_value, max_value = SERIES_VALUES_RANGES[series_type]

            if fake_instance.boolean(chance_of_getting_true=percentage):
                # Generate value based on whether the range has fractional values
                if min_value != int(min_value) or max_value != int(max_value):
                    # Float range - use uniform distribution
                    value = fake_instance.random.uniform(min_value, max_value)
                else:
                    # Integer range
                    value = fake_instance.random_int(min=int(min_value), max=int(max_value))

                samples.append(
                    TimeSeriesSampleCreate(
                        id=uuid4(),
                        user_id=user_id,
                        provider_name=provider_name,
                        device_id=device_id,
                        recorded_at=current_time,
                        value=Decimal(str(value)),
                        series_type=series_type,
                    )
                )

        current_time += timedelta(seconds=fake_instance.random_int(min=20, max=60))

    return samples


def seed_activity_data() -> None:
    """Create 10 users with comprehensive health data."""
    with SessionLocal() as db:
        users_created = 0
        workouts_created = 0
        sleeps_created = 0
        time_series_samples_created = 0

        # Initialize repositories
        personal_record_repo = CrudRepository(PersonalRecord)
        event_detail_repo = EventRecordDetailRepository(EventRecordDetail)

        for user_num in range(1, 3):
            # Create user
            user_data = UserCreate(
                first_name=fake.first_name(),
                last_name=fake.last_name(),
                email=fake.unique.email(),
                external_user_id=fake.unique.uuid4() if fake.boolean(chance_of_getting_true=80) else None,
            )

            user = user_service.create(db, user_data)
            users_created += 1
            print(f"✓ Created user {user_num}/2: {user.email} (ID: {user.id})")

            # Create personal record (one per user)
            personal_record_data = generate_personal_record(user.id, fake)
            personal_record_repo.create(db, personal_record_data)
            print(f"  ✓ Created personal record for user {user_num}")

            # Create 80 workouts for this user
            for workout_num in range(1, 81):
                record, detail = generate_workout(user.id, fake)
                event_record_service.create(db, record)
                event_record_service.create_detail(db, detail)  # Defaults to "workout"
                workouts_created += 1

                # Generate time series samples for some workouts (30% chance)
                if fake.boolean(chance_of_getting_true=30):
                    device_id = f"device_{fake.random_int(min=1, max=5)}"
                    samples = generate_time_series_samples(
                        record.start_datetime,
                        record.end_datetime,
                        fake,
                        user_id=user.id,
                        provider_name=record.provider_name or "Apple",
                        device_id=device_id,
                    )
                    if samples:
                        timeseries_service.bulk_create_samples(db, samples)
                        time_series_samples_created += len(samples)

                if workout_num % 20 == 0:
                    print(f"  Created {workout_num}/80 workouts for user {user_num}")

            # Create 20 sleep records for this user
            for sleep_num in range(1, 21):
                record, detail = generate_sleep(user.id, fake)
                event_record_service.create(db, record)
                event_detail_repo.create(db, detail, detail_type="sleep")
                sleeps_created += 1

                if sleep_num % 10 == 0:
                    print(f"  Created {sleep_num}/20 sleep records for user {user_num}")

            db.commit()
            print(f"  ✓ Completed all health data for user {user_num}\n")

        print("✓ Successfully created:")
        print(f"  - {users_created} users")
        print(f"  - {workouts_created} workouts")
        print(f"  - {sleeps_created} sleep records")
        print(f"  - {time_series_samples_created} time series samples")


if __name__ == "__main__":
    seed_activity_data()
