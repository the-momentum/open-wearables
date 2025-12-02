#!/usr/bin/env python3
"""Seed activity data: create 10 users with 100 workouts each using Faker."""

from datetime import timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from faker import Faker

from app.database import SessionLocal
from app.schemas.user import UserCreate
from app.schemas.workout import WorkoutCreate
from app.services import user_service, workout_service

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


def generate_workout(user_id: UUID, fake_instance: Faker) -> WorkoutCreate:
    """Generate a single workout with random data."""
    # Generate start datetime within last 6 months
    start_datetime = fake_instance.date_time_between(start_date="-6M", end_date="now", tzinfo=timezone.utc)

    # Duration between 15 minutes and 3 hours
    duration_minutes = fake_instance.random_int(min=15, max=180)
    duration_seconds = Decimal(duration_minutes * 60)

    end_datetime = start_datetime + timedelta(seconds=float(duration_seconds))

    return WorkoutCreate(
        id=uuid4(),
        provider_id=str(uuid4()) if fake_instance.boolean(chance_of_getting_true=70) else None,
        user_id=user_id,
        type=fake_instance.random.choice(WORKOUT_TYPES),
        duration_seconds=duration_seconds,
        source_name=fake_instance.random.choice(SOURCE_NAMES),
        start_datetime=start_datetime,
        end_datetime=end_datetime,
    )


def seed_activity_data() -> None:
    """Create 10 users with 100 workouts each."""
    with SessionLocal() as db:
        users_created = 0
        workouts_created = 0

        for user_num in range(1, 11):
            # Create user
            user_data = UserCreate(
                first_name=fake.first_name(),
                last_name=fake.last_name(),
                email=fake.unique.email(),
                external_user_id=fake.unique.uuid4() if fake.boolean(chance_of_getting_true=80) else None,
            )

            user = user_service.create(db, user_data)
            users_created += 1
            print(f"✓ Created user {user_num}/10: {user.email} (ID: {user.id})")

            # Create 100 workouts for this user
            for workout_num in range(1, 101):
                workout = generate_workout(user.id, fake)
                workout_service.create(db, workout)
                workouts_created += 1

                if workout_num % 25 == 0:
                    print(f"  Created {workout_num}/100 workouts for user {user_num}")

            db.commit()
            print(f"  ✓ Completed 100 workouts for user {user_num}\n")

        print(f"✓ Successfully created {users_created} users with {workouts_created} total workouts")


if __name__ == "__main__":
    seed_activity_data()
