"""Tests for the seed data generation service."""

from datetime import date

from sqlalchemy.orm import Session

from app.models import (
    DataPointSeries,
    DataSource,
    EventRecord,
    PersonalRecord,
    SeriesTypeDefinition,
    User,
    UserConnection,
)
from app.schemas.enums import ProviderName, SeriesType, WorkoutType
from app.schemas.utils.seed_data import (
    SeedDataRequest,
    SeedProfileConfig,
    SleepConfig,
    TimeSeriesConfig,
    WorkoutConfig,
)
from app.services.seed_data import seed_data_service


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


def _samples_by_series(db: Session, series_type: SeriesType) -> list[DataPointSeries]:
    return (
        db.query(DataPointSeries)
        .join(SeriesTypeDefinition, DataPointSeries.series_type_definition_id == SeriesTypeDefinition.id)
        .filter(SeriesTypeDefinition.code == series_type.value)
        .all()
    )


class TestContinuousTimeSeries:
    """Continuous time-series generation runs independently of workouts."""

    def test_continuous_series_emitted_without_workouts(self, db: Session) -> None:
        """Time series should be produced even when no workouts are generated."""
        request = SeedDataRequest(
            num_users=1,
            random_seed=42,
            profile=SeedProfileConfig(
                generate_workouts=False,
                generate_sleep=False,
                generate_time_series=True,
                providers=[ProviderName.GARMIN],
                num_connections=1,
                time_series_config=TimeSeriesConfig(
                    enabled_types=[SeriesType.heart_rate, SeriesType.resting_heart_rate],
                    include_blood_pressure=False,
                    date_from=date(2024, 11, 1),
                    date_to=date(2024, 11, 3),
                ),
            ),
        )

        summary = seed_data_service.generate(db, request)

        assert summary["workouts"] == 0
        # heart_rate @ 5min for 3 days = plenty; resting_heart_rate = ~3 samples
        hr = _samples_by_series(db, SeriesType.heart_rate)
        rhr = _samples_by_series(db, SeriesType.resting_heart_rate)
        assert len(hr) > 100, f"expected dense heart_rate samples, got {len(hr)}"
        assert 1 <= len(rhr) <= 5, f"expected one RHR per day, got {len(rhr)}"

    def test_blood_pressure_samples_are_paired(self, db: Session) -> None:
        """Every systolic sample must share its recorded_at with a diastolic sample."""
        request = SeedDataRequest(
            num_users=1,
            random_seed=7,
            profile=SeedProfileConfig(
                generate_workouts=False,
                generate_sleep=False,
                generate_time_series=True,
                providers=[ProviderName.GARMIN],
                num_connections=1,
                time_series_config=TimeSeriesConfig(
                    enabled_types=[],  # exclude other types
                    include_blood_pressure=True,
                    date_from=date(2024, 11, 1),
                    date_to=date(2024, 11, 7),
                ),
            ),
        )

        seed_data_service.generate(db, request)

        sys = _samples_by_series(db, SeriesType.blood_pressure_systolic)
        dia = _samples_by_series(db, SeriesType.blood_pressure_diastolic)
        assert len(sys) == len(dia) > 0
        assert {s.recorded_at for s in sys} == {d.recorded_at for d in dia}

    def test_per_user_provider_consistency(self, db: Session) -> None:
        """All samples of a given series type for a user share the same provider."""
        request = SeedDataRequest(
            num_users=1,
            random_seed=11,
            profile=SeedProfileConfig(
                generate_workouts=False,
                generate_sleep=False,
                generate_time_series=True,
                providers=[ProviderName.GARMIN, ProviderName.OURA, ProviderName.WHOOP],
                num_connections=3,
                time_series_config=TimeSeriesConfig(
                    enabled_types=[SeriesType.heart_rate, SeriesType.weight],
                    include_blood_pressure=False,
                    date_from=date(2024, 11, 1),
                    date_to=date(2024, 11, 14),
                ),
            ),
        )

        seed_data_service.generate(db, request)

        for series_type in (SeriesType.heart_rate, SeriesType.weight):
            samples = _samples_by_series(db, series_type)
            assert samples, f"no samples generated for {series_type}"
            sources = (
                db.query(DataSource.provider)
                .filter(DataSource.id.in_({s.data_source_id for s in samples}))
                .distinct()
                .all()
            )
            assert len(sources) == 1, f"{series_type} used multiple providers: {sources}"

    def test_workout_bound_series_filtered_by_workout_type(self, db: Session) -> None:
        """running_power should only appear for running workouts, not cycling."""
        request = SeedDataRequest(
            num_users=1,
            random_seed=99,
            profile=SeedProfileConfig(
                generate_workouts=True,
                generate_sleep=False,
                generate_time_series=True,
                providers=[ProviderName.GARMIN],
                num_connections=1,
                workout_config=WorkoutConfig(
                    count=4,
                    workout_types=[WorkoutType.CYCLING],
                    duration_min_minutes=10,
                    duration_max_minutes=15,
                ),
                time_series_config=TimeSeriesConfig(
                    enabled_types=[SeriesType.running_power, SeriesType.power],
                    include_blood_pressure=False,
                ),
            ),
        )

        seed_data_service.generate(db, request)

        running_power = _samples_by_series(db, SeriesType.running_power)
        assert running_power == [], "running_power must not be emitted for cycling workouts"
        # power is allowed for cycling and should be emitted
        power = _samples_by_series(db, SeriesType.power)
        assert power, "power should be emitted for cycling workouts"

    def test_no_samples_when_nothing_selected(self, db: Session) -> None:
        """With empty enabled_types and BP off, zero time-series samples emit."""
        request = SeedDataRequest(
            num_users=1,
            random_seed=5,
            profile=SeedProfileConfig(
                generate_workouts=True,
                generate_sleep=False,
                generate_time_series=True,
                providers=[ProviderName.GARMIN],
                num_connections=1,
                workout_config=WorkoutConfig(count=3),
                time_series_config=TimeSeriesConfig(
                    enabled_types=[],
                    include_blood_pressure=False,
                ),
            ),
        )

        summary = seed_data_service.generate(db, request)

        assert summary["time_series_samples"] == 0
