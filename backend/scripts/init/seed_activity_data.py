#!/usr/bin/env python3
"""Seed activity data: create 10 users with comprehensive health data using Faker."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from faker import Faker

from app.database import SessionLocal
from app.models import EventRecordDetail, PersonalRecord
from app.repositories import CrudRepository
from app.repositories.event_record_detail_repository import EventRecordDetailRepository
from app.schemas.event_record import EventRecordCreate
from app.schemas.event_record_detail import EventRecordDetailCreate
from app.schemas.personal_record import PersonalRecordCreate
from app.schemas.time_series import HeartRateSampleCreate, SeriesType, StepSampleCreate, TimeSeriesSampleCreate
from app.schemas.user import UserCreate
from app.services import event_record_service, time_series_service, user_service

fake = Faker()

# Workout types and sources for variety
WORKOUT_TYPES = [
    "Running",
    "Walking",
    "Cycling",
    "Swimming",
    "Strength Training",
    "Yoga",
    "HIIT",
    "Rowing",
    "Elliptical",
    "Hiking",
    "Tennis",
    "Basketball",
    "Soccer",
    "CrossFit",
    "Pilates",
]

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
        provider_id=str(uuid4()) if fake_instance.boolean(chance_of_getting_true=70) else None,
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
        steps_min=steps,
        steps_max=steps,
        steps_avg=Decimal(steps),
        steps_total=steps,
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
    deep_minutes = fake_instance.random_int(min=60, max=180)
    rem_minutes = fake_instance.random_int(min=60, max=150)
    light_minutes = sleep_duration_minutes - deep_minutes - rem_minutes - fake_instance.random_int(min=10, max=30)
    awake_minutes = sleep_duration_minutes - deep_minutes - rem_minutes - light_minutes

    sleep_id = uuid4()
    device_id = (
        f"device_{fake_instance.random_int(min=1, max=3)}" if fake_instance.boolean(chance_of_getting_true=60) else None
    )

    record = EventRecordCreate(
        id=sleep_id,
        provider_id=str(uuid4()) if fake_instance.boolean(chance_of_getting_true=70) else None,
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
    provider_id: str | None = None,
    device_id: str | None = None,
) -> list[TimeSeriesSampleCreate]:
    """Generate time series samples for a workout period with realistic frequencies."""
    samples = []
    current_time = workout_start

    # Generate samples every 30 seconds during the workout
    while current_time <= workout_end:
        # Heart rate sample (very common during workouts)
        if fake_instance.boolean(chance_of_getting_true=80):
            samples.append(
                HeartRateSampleCreate(
                    id=uuid4(),
                    user_id=user_id,
                    provider_id=provider_id,
                    device_id=device_id,
                    recorded_at=current_time,
                    value=Decimal(fake_instance.random_int(min=90, max=180)),
                    series_type=SeriesType.heart_rate,
                ),
            )

        # Step sample (common during walking/running workouts)
        if fake_instance.boolean(chance_of_getting_true=30):
            samples.append(
                StepSampleCreate(
                    id=uuid4(),
                    user_id=user_id,
                    provider_id=provider_id,
                    device_id=device_id,
                    recorded_at=current_time,
                    value=Decimal(fake_instance.random_int(min=10, max=50)),
                    series_type=SeriesType.steps,
                ),
            )

        # Energy/calories burned (moderately frequent)
        if fake_instance.boolean(chance_of_getting_true=25):
            samples.append(
                TimeSeriesSampleCreate(
                    id=uuid4(),
                    user_id=user_id,
                    provider_id=provider_id,
                    device_id=device_id,
                    recorded_at=current_time,
                    value=Decimal(fake_instance.random_int(min=5, max=20)),
                    series_type=SeriesType.energy,
                ),
            )

        # Distance walking/running (common for running/walking workouts)
        if fake_instance.boolean(chance_of_getting_true=20):
            samples.append(
                TimeSeriesSampleCreate(
                    id=uuid4(),
                    user_id=user_id,
                    provider_id=provider_id,
                    device_id=device_id,
                    recorded_at=current_time,
                    value=Decimal(fake_instance.random_int(min=10, max=100)),
                    series_type=SeriesType.distance_walking_running,
                ),
            )

        # Distance cycling (less common, only for cycling workouts)
        if fake_instance.boolean(chance_of_getting_true=10):
            samples.append(
                TimeSeriesSampleCreate(
                    id=uuid4(),
                    user_id=user_id,
                    provider_id=provider_id,
                    device_id=device_id,
                    recorded_at=current_time,
                    value=Decimal(fake_instance.random_int(min=20, max=200)),
                    series_type=SeriesType.distance_cycling,
                ),
            )

        # Respiratory rate (moderately frequent during exercise)
        if fake_instance.boolean(chance_of_getting_true=25):
            samples.append(
                TimeSeriesSampleCreate(
                    id=uuid4(),
                    user_id=user_id,
                    provider_id=provider_id,
                    device_id=device_id,
                    recorded_at=current_time,
                    value=Decimal(fake_instance.random_int(min=12, max=30)),
                    series_type=SeriesType.respiratory_rate,
                ),
            )

        # Walking heart rate average (less frequent, calculated metric)
        if fake_instance.boolean(chance_of_getting_true=8):
            samples.append(
                TimeSeriesSampleCreate(
                    id=uuid4(),
                    user_id=user_id,
                    provider_id=provider_id,
                    device_id=device_id,
                    recorded_at=current_time,
                    value=Decimal(fake_instance.random_int(min=100, max=140)),
                    series_type=SeriesType.walking_heart_rate_average,
                ),
            )

        # Heart rate variability SDNN (less frequent, requires special sensors)
        if fake_instance.boolean(chance_of_getting_true=5):
            samples.append(
                TimeSeriesSampleCreate(
                    id=uuid4(),
                    user_id=user_id,
                    provider_id=provider_id,
                    device_id=device_id,
                    recorded_at=current_time,
                    value=Decimal(fake_instance.random_int(min=20, max=80)),
                    series_type=SeriesType.heart_rate_variability_sdnn,
                ),
            )

        # Oxygen saturation (less frequent, requires special sensors)
        if fake_instance.boolean(chance_of_getting_true=5):
            samples.append(
                TimeSeriesSampleCreate(
                    id=uuid4(),
                    user_id=user_id,
                    provider_id=provider_id,
                    device_id=device_id,
                    recorded_at=current_time,
                    value=Decimal(fake_instance.random_int(min=95, max=100)),
                    series_type=SeriesType.oxygen_saturation,
                ),
            )

        # Resting heart rate (very infrequent during workout, but occasionally measured)
        if fake_instance.boolean(chance_of_getting_true=1):
            samples.append(
                TimeSeriesSampleCreate(
                    id=uuid4(),
                    user_id=user_id,
                    provider_id=provider_id,
                    device_id=device_id,
                    recorded_at=current_time,
                    value=Decimal(fake_instance.random_int(min=55, max=75)),
                    series_type=SeriesType.resting_heart_rate,
                ),
            )

        # Body temperature (very infrequent, measured occasionally)
        if fake_instance.boolean(chance_of_getting_true=2):
            samples.append(
                TimeSeriesSampleCreate(
                    id=uuid4(),
                    user_id=user_id,
                    provider_id=provider_id,
                    device_id=device_id,
                    recorded_at=current_time,
                    value=Decimal(fake_instance.random_int(min=360, max=375)) / Decimal(10),  # 36.0-37.5°C
                    series_type=SeriesType.body_temperature,
                ),
            )

        # Weight (very infrequent, measured occasionally, not during workout)
        if fake_instance.boolean(chance_of_getting_true=1):
            samples.append(
                TimeSeriesSampleCreate(
                    id=uuid4(),
                    user_id=user_id,
                    provider_id=provider_id,
                    device_id=device_id,
                    recorded_at=current_time,
                    value=Decimal(fake_instance.random_int(min=500, max=1200)) / Decimal(10),  # 50.0-120.0 kg
                    series_type=SeriesType.weight,
                ),
            )

        # Body fat percentage (very infrequent, measured rarely)
        if fake_instance.boolean(chance_of_getting_true=1):
            samples.append(
                TimeSeriesSampleCreate(
                    id=uuid4(),
                    user_id=user_id,
                    provider_id=provider_id,
                    device_id=device_id,
                    recorded_at=current_time,
                    value=Decimal(fake_instance.random_int(min=100, max=300)) / Decimal(10),  # 10.0-30.0%
                    series_type=SeriesType.body_fat_percentage,
                ),
            )

        # Height (extremely infrequent, rarely changes)
        if fake_instance.boolean(chance_of_getting_true=1):
            samples.append(
                TimeSeriesSampleCreate(
                    id=uuid4(),
                    user_id=user_id,
                    provider_id=provider_id,
                    device_id=device_id,
                    recorded_at=current_time,
                    value=Decimal(fake_instance.random_int(min=150, max=200)),  # 150-200 cm
                    series_type=SeriesType.height,
                ),
            )

        current_time += timedelta(seconds=30)

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
                        provider_id=record.provider_id,
                        device_id=device_id,
                    )
                    if samples:
                        time_series_service.bulk_create_samples(db, samples)
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
