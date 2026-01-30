#!/usr/bin/env python3
"""Seed activity data: create 10 users with comprehensive health data using Faker."""

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import TypedDict
from uuid import UUID, uuid4

import yaml
from faker import Faker

from app.database import SessionLocal
from app.models import EventRecordDetail, PersonalRecord, UserConnection
from app.repositories import CrudRepository
from app.repositories.event_record_detail_repository import EventRecordDetailRepository
from app.schemas.event_record import EventRecordCreate
from app.schemas.event_record_detail import EventRecordDetailCreate
from app.schemas.oauth import ConnectionStatus, ProviderName, UserConnectionCreate, UserConnectionUpdate
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


class ProviderConfig(TypedDict):
    """Type definition for provider configuration."""

    source_name: str
    manufacturer: str
    devices: list[str]
    os_versions: list[str]


# Provider configurations keyed by ProviderName enum
PROVIDER_CONFIGS: dict[ProviderName, ProviderConfig] = {
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
        "devices": ["WHOOP 4.0", "WHOOP 3.0"],
        "os_versions": ["4.0", "3.0"],
    },
}

# Providers available for seeding
SEED_PROVIDERS = list(PROVIDER_CONFIGS.keys())

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
        config = yaml.safe_load(yamlfile) or {}

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
    provider_sync_times: dict[ProviderName, datetime],
) -> tuple[EventRecordCreate, EventRecordDetailCreate]:
    """Generate a single workout with random data."""
    # Select provider first so we can use its last_synced_at as upper bound
    provider = fake_instance.random.choice(list(provider_sync_times.keys()))
    last_synced_at = provider_sync_times[provider]

    # Generate start datetime within last 6 months, but not after last sync
    start_datetime = fake_instance.date_time_between(start_date="-6M", end_date=last_synced_at, tzinfo=timezone.utc)

    # Duration between 15 minutes and 3 hours
    duration_minutes = fake_instance.random_int(min=15, max=180)
    duration_seconds = duration_minutes * 60

    end_datetime = start_datetime + timedelta(seconds=float(duration_seconds))

    steps = fake_instance.random_int(min=500, max=20000)
    heart_rate_min = fake_instance.random_int(min=90, max=120)
    heart_rate_max = fake_instance.random_int(min=140, max=180)
    heart_rate_avg = Decimal((heart_rate_min + heart_rate_max) / 2)

    workout_id = uuid4()
    config = PROVIDER_CONFIGS[provider]

    # Simulate device
    has_device = fake_instance.boolean(chance_of_getting_true=80)
    device_name: str | None = None
    manufacturer: str | None = None
    sw_version: str | None = None

    if has_device:
        device_name = fake_instance.random.choice(config["devices"])
        manufacturer = str(config["manufacturer"])
        sw_version = fake_instance.random.choice(config["os_versions"])

    record = EventRecordCreate(
        id=workout_id,
        source=provider.value,
        user_id=user_id,
        category="workout",
        type=fake_instance.random.choice(WORKOUT_TYPES),
        duration_seconds=duration_seconds,
        source_name=config["source_name"],
        device_model=device_name,
        manufacturer=manufacturer,
        software_version=sw_version,
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
    provider_sync_times: dict[ProviderName, datetime],
) -> tuple[EventRecordCreate, EventRecordDetailCreate]:
    """Generate a single sleep record with random data."""
    # Select provider first so we can use its last_synced_at as upper bound
    provider = fake_instance.random.choice(list(provider_sync_times.keys()))
    last_synced_at = provider_sync_times[provider]

    # Generate sleep start datetime within last 6 months, but not after last sync (typically evening/night)
    base_datetime = fake_instance.date_time_between(start_date="-6M", end_date=last_synced_at, tzinfo=timezone.utc)
    # Sleep typically starts between 9 PM and 1 AM
    start_hour = fake_instance.random_int(min=21, max=25) % 24
    start_datetime = base_datetime.replace(hour=start_hour, minute=fake_instance.random_int(min=0, max=59))

    # Sleep duration between 5 and 10 hours
    sleep_duration_minutes = fake_instance.random_int(min=300, max=600)
    sleep_duration_seconds = sleep_duration_minutes * 60
    end_datetime = start_datetime + timedelta(seconds=float(sleep_duration_seconds))

    # Time in bed is typically 15-60 minutes more than sleep duration
    time_in_bed_minutes = sleep_duration_minutes + fake_instance.random_int(min=15, max=60)

    # Sleep stages (should roughly add up to sleep_duration_minutes)
    deep_minutes = fake_instance.random_int(min=60, max=120)
    rem_minutes = fake_instance.random_int(min=80, max=140)
    light_minutes = sleep_duration_minutes - deep_minutes - rem_minutes - fake_instance.random_int(min=10, max=40)
    awake_minutes = fake_instance.random_int(min=5, max=30)

    # Sleep efficiency (total sleep / time in bed)
    sleep_efficiency = Decimal(sleep_duration_minutes) / Decimal(time_in_bed_minutes) * 100

    # Is nap? (10% chance)
    is_nap = fake_instance.boolean(chance_of_getting_true=10)

    sleep_id = uuid4()
    config = PROVIDER_CONFIGS[provider]

    # Simulate device
    has_device = fake_instance.boolean(chance_of_getting_true=80)
    device_name: str | None = None
    manufacturer: str | None = None
    sw_version: str | None = None

    if has_device:
        device_name = fake_instance.random.choice(config["devices"])
        manufacturer = str(config["manufacturer"])
        sw_version = fake_instance.random.choice(config["os_versions"])

    record = EventRecordCreate(
        id=sleep_id,
        source=provider.value,
        user_id=user_id,
        category="sleep",
        type=None,
        duration_seconds=sleep_duration_seconds,
        source_name=config["source_name"],
        device_model=device_name,
        manufacturer=manufacturer,
        software_version=sw_version,
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
    source: str,
    device_model: str | None = None,
    manufacturer: str | None = None,
    software_version: str | None = None,
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
                        source=source,
                        device_model=device_model,
                        manufacturer=manufacturer,
                        software_version=software_version,
                        recorded_at=current_time,
                        value=Decimal(str(value)),
                        series_type=series_type,
                    )
                )

        current_time += timedelta(seconds=fake_instance.random_int(min=20, max=60))

    return samples


def generate_user_connections(
    user_id: UUID,
    fake_instance: Faker,
    num_connections: int = 2,
) -> tuple[list[UserConnectionCreate], dict[ProviderName, datetime]]:
    """Generate random provider connections for a user.

    Args:
        user_id: The user ID to create connections for.
        fake_instance: Faker instance for generating random data.
        num_connections: Number of connections to create (default: 2).

    Returns:
        Tuple of (connections list, provider_sync_times dict).
    """
    # Select random providers without repetition
    selected_providers = fake_instance.random.sample(SEED_PROVIDERS, num_connections)
    now = datetime.now(timezone.utc)

    connections = []
    provider_sync_times: dict[ProviderName, datetime] = {}

    for provider in selected_providers:
        # Apple uses SDK-based connections (no OAuth tokens needed)
        is_sdk_provider = provider == ProviderName.APPLE

        # Last sync within the last 1-7 days (stored separately for later update)
        provider_sync_times[provider] = now - timedelta(days=fake_instance.random_int(min=1, max=7))

        connection = UserConnectionCreate(
            id=uuid4(),
            user_id=user_id,
            provider=provider.value,
            provider_user_id=f"{provider.value}_{uuid4().hex[:8]}" if not is_sdk_provider else None,
            provider_username=fake_instance.user_name() if not is_sdk_provider else None,
            access_token=f"access_{uuid4().hex}" if not is_sdk_provider else None,
            refresh_token=f"refresh_{uuid4().hex}" if not is_sdk_provider else None,
            token_expires_at=now + timedelta(days=30) if not is_sdk_provider else None,
            scope="read_all" if not is_sdk_provider else None,
            status=ConnectionStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        )
        connections.append(connection)

    return connections, provider_sync_times


def seed_activity_data() -> None:
    """Create 10 users with comprehensive health data."""
    with SessionLocal() as db:
        users_created = 0
        workouts_created = 0
        sleeps_created = 0
        time_series_samples_created = 0
        connections_created = 0

        # Initialize repositories
        personal_record_repo = CrudRepository(PersonalRecord)
        event_detail_repo = EventRecordDetailRepository(EventRecordDetail)
        connection_repo = CrudRepository(UserConnection)

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

            # Create provider connections (2 per user)
            user_connections, provider_sync_times = generate_user_connections(user.id, fake, num_connections=2)
            for connection_data in user_connections:
                created_connection = connection_repo.create(db, connection_data)
                # Update with last_synced_at (simulating a sync after connection creation)
                provider = ProviderName(connection_data.provider)
                update_data = UserConnectionUpdate(last_synced_at=provider_sync_times[provider])
                connection_repo.update(db, created_connection, update_data)
                connections_created += 1
            provider_names = ", ".join(c.provider for c in user_connections)
            print(f"  ✓ Created {len(user_connections)} provider connections: {provider_names}")

            # Create 80 workouts for this user
            for workout_num in range(1, 81):
                record, detail = generate_workout(user.id, fake, provider_sync_times)
                event_record_service.create(db, record)
                event_record_service.create_detail(db, detail)  # Defaults to "workout"
                workouts_created += 1

                # Generate time series samples for some workouts (30% chance)
                if fake.boolean(chance_of_getting_true=30):
                    samples = generate_time_series_samples(
                        record.start_datetime,
                        record.end_datetime,
                        fake,
                        user_id=user.id,
                        source=record.source or "unknown",
                        device_model=record.device_model,
                        manufacturer=record.manufacturer,
                        software_version=record.software_version,
                    )
                    if samples:
                        timeseries_service.bulk_create_samples(db, samples)
                        time_series_samples_created += len(samples)

                if workout_num % 20 == 0:
                    print(f"  Created {workout_num}/80 workouts for user {user_num}")

            # Create 20 sleep records for this user
            for sleep_num in range(1, 21):
                record, detail = generate_sleep(user.id, fake, provider_sync_times)
                event_record_service.create(db, record)
                event_detail_repo.create(db, detail, detail_type="sleep")
                sleeps_created += 1

                if sleep_num % 10 == 0:
                    print(f"  Created {sleep_num}/20 sleep records for user {user_num}")

            db.commit()
            print(f"  ✓ Completed all health data for user {user_num}\n")

        print("✓ Successfully created:")
        print(f"  - {users_created} users")
        print(f"  - {connections_created} provider connections")
        print(f"  - {workouts_created} workouts")
        print(f"  - {sleeps_created} sleep records")
        print(f"  - {time_series_samples_created} time series samples")


if __name__ == "__main__":
    seed_activity_data()
