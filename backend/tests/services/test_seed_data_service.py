"""Tests for the seed data generation service."""

from sqlalchemy.orm import Session

from app.models import EventRecord, PersonalRecord, User, UserConnection
from app.schemas.enums import ProviderName, WorkoutType
from app.schemas.utils.seed_data import (
    SeedDataRequest,
    SeedProfileConfig,
    SleepConfig,
    WorkoutConfig,
)
from app.services.seed_data_service import seed_data_service


class TestSeedDataServiceGenerate:
    """Tests for seed_data_service.generate()."""

    def test_generate_minimal_user(self, db: Session) -> None:
        """Generate a single user with minimal config - no time series."""
        request = SeedDataRequest(
            num_users=1,
            profile=SeedProfileConfig(
                generate_workouts=True,
                generate_sleep=True,
                generate_time_series=False,
                workout_config=WorkoutConfig(count=2),
                sleep_config=SleepConfig(count=2),
            ),
        )

        summary = seed_data_service.generate(db, request)

        assert summary["users"] == 1
        assert summary["workouts"] == 2
        assert summary["sleeps"] == 2
        assert summary["connections"] >= 1
        assert summary["time_series_samples"] == 0

        # Verify data in DB
        assert db.query(User).count() == 1
        assert db.query(PersonalRecord).count() == 1
        assert db.query(UserConnection).count() >= 1
        assert db.query(EventRecord).filter_by(category="workout").count() == 2
        assert db.query(EventRecord).filter_by(category="sleep").count() == 2

    def test_generate_workouts_only(self, db: Session) -> None:
        """Generate a user with workouts but no sleep data."""
        request = SeedDataRequest(
            num_users=1,
            profile=SeedProfileConfig(
                generate_workouts=True,
                generate_sleep=False,
                generate_time_series=False,
                workout_config=WorkoutConfig(count=3),
            ),
        )

        summary = seed_data_service.generate(db, request)

        assert summary["workouts"] == 3
        assert summary["sleeps"] == 0
        assert db.query(EventRecord).filter_by(category="sleep").count() == 0

    def test_generate_sleep_only(self, db: Session) -> None:
        """Generate a user with sleep data but no workouts."""
        request = SeedDataRequest(
            num_users=1,
            profile=SeedProfileConfig(
                generate_workouts=False,
                generate_sleep=True,
                generate_time_series=False,
                sleep_config=SleepConfig(count=3),
            ),
        )

        summary = seed_data_service.generate(db, request)

        assert summary["workouts"] == 0
        assert summary["sleeps"] == 3
        assert db.query(EventRecord).filter_by(category="workout").count() == 0

    def test_generate_multiple_users(self, db: Session) -> None:
        """Generate multiple users at once."""
        request = SeedDataRequest(
            num_users=3,
            profile=SeedProfileConfig(
                generate_workouts=True,
                generate_sleep=False,
                generate_time_series=False,
                workout_config=WorkoutConfig(count=1),
            ),
        )

        summary = seed_data_service.generate(db, request)

        assert summary["users"] == 3
        assert db.query(User).count() == 3
        assert db.query(PersonalRecord).count() == 3

    def test_generate_with_specific_workout_types(self, db: Session) -> None:
        """Workout types should be restricted to the configured list."""
        request = SeedDataRequest(
            num_users=1,
            profile=SeedProfileConfig(
                generate_workouts=True,
                generate_sleep=False,
                generate_time_series=False,
                workout_config=WorkoutConfig(
                    count=10,
                    workout_types=[WorkoutType.BOXING, WorkoutType.RUNNING],
                ),
            ),
        )

        summary = seed_data_service.generate(db, request)

        assert summary["workouts"] == 10
        workouts = db.query(EventRecord).filter_by(category="workout").all()
        for w in workouts:
            assert w.type in ("boxing", "running")

    def test_generate_with_specific_providers(self, db: Session) -> None:
        """Connections should use the specified providers."""
        request = SeedDataRequest(
            num_users=1,
            profile=SeedProfileConfig(
                generate_workouts=False,
                generate_sleep=False,
                generate_time_series=False,
                providers=[ProviderName.GARMIN, ProviderName.POLAR],
                num_connections=2,
            ),
        )

        summary = seed_data_service.generate(db, request)

        assert summary["connections"] == 2
        connections = db.query(UserConnection).all()
        provider_set = {c.provider for c in connections}
        assert provider_set == {"garmin", "polar"}
