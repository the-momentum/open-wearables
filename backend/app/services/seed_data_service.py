"""Service for generating parameterized seed data.

Refactored from scripts/init/seed_activity_data.py to support
dashboard-driven data generation with configurable profiles.
"""

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import yaml
from faker import Faker
from sqlalchemy.orm import Session

from app.models import EventRecordDetail, PersonalRecord, UserConnection
from app.repositories import CrudRepository
from app.repositories.event_record_detail_repository import EventRecordDetailRepository
from app.schemas.auth import ConnectionStatus
from app.schemas.enums import ProviderName, SeriesType, WorkoutType
from app.schemas.model_crud.activities import (
    EventRecordCreate,
    EventRecordDetailCreate,
    PersonalRecordCreate,
    TimeSeriesSampleCreate,
)
from app.schemas.model_crud.user_management import (
    UserConnectionCreate,
    UserConnectionUpdate,
    UserCreate,
)
from app.schemas.utils.seed_data import (
    SeedDataRequest,
    SleepConfig,
    WorkoutConfig,
)
from app.services.event_record_service import event_record_service
from app.services.timeseries_service import timeseries_service
from app.services.user_service import user_service
from app.utils.structured_logging import log_structured

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
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
}

SEED_PROVIDERS = list(PROVIDER_CONFIGS.keys())


# ---------------------------------------------------------------------------
# Series type configuration (loaded once from YAML)
# ---------------------------------------------------------------------------


def _load_series_type_config() -> tuple[dict[SeriesType, tuple[float, float]], dict[SeriesType, int]]:
    # __file__ = backend/app/services/seed_data_service.py → .parent x3 = backend/
    config_path = Path(__file__).parent.parent.parent / "scripts" / "init" / "series_type_config.yaml"
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


# ---------------------------------------------------------------------------
# Generation helpers
# ---------------------------------------------------------------------------


def _generate_workout(
    user_id: UUID,
    fake: Faker,
    provider_sync_times: dict[ProviderName, datetime],
    config: WorkoutConfig,
) -> tuple[EventRecordCreate, EventRecordDetailCreate]:
    """Generate a single workout with parameters from *config*."""
    provider = fake.random.choice(list(provider_sync_times.keys()))
    last_synced_at = provider_sync_times[provider]

    start_date_str = f"-{config.date_range_months}M"
    start_datetime = fake.date_time_between(start_date=start_date_str, end_date=last_synced_at, tzinfo=timezone.utc)

    duration_minutes = fake.random_int(min=config.duration_min_minutes, max=config.duration_max_minutes)
    duration_seconds = duration_minutes * 60
    end_datetime = start_datetime + timedelta(seconds=float(duration_seconds))

    steps = fake.random_int(min=config.steps_range[0], max=config.steps_range[1])
    heart_rate_min = fake.random_int(min=config.hr_min_range[0], max=config.hr_min_range[1])
    heart_rate_max = fake.random_int(min=config.hr_max_range[0], max=config.hr_max_range[1])
    heart_rate_avg = Decimal((heart_rate_min + heart_rate_max) / 2)

    # Pick workout type from configured list or all types
    workout_types = config.workout_types or list(WorkoutType)
    workout_type = fake.random.choice(workout_types)

    workout_id = uuid4()
    prov_config = PROVIDER_CONFIGS[provider]

    has_device = fake.boolean(chance_of_getting_true=80)
    device_name: str | None = None
    device_provider: str | None = None
    sw_version: str | None = None
    if has_device:
        device_name = fake.random.choice(prov_config["devices"])
        device_provider = provider.value
        sw_version = fake.random.choice(prov_config["os_versions"])

    record = EventRecordCreate(
        id=workout_id,
        source=device_provider,
        user_id=user_id,
        category="workout",
        type=workout_type,
        duration_seconds=duration_seconds,
        source_name=prov_config["source_name"],
        device_model=device_name,
        provider=device_provider,
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


def _generate_sleep(
    user_id: UUID,
    fake: Faker,
    provider_sync_times: dict[ProviderName, datetime],
    config: SleepConfig,
) -> tuple[EventRecordCreate, EventRecordDetailCreate]:
    """Generate a single sleep record with parameters from *config*."""
    provider = fake.random.choice(list(provider_sync_times.keys()))
    last_synced_at = provider_sync_times[provider]

    start_date_str = f"-{config.date_range_months}M"
    base_datetime = fake.date_time_between(start_date=start_date_str, end_date=last_synced_at, tzinfo=timezone.utc)

    # Sleep typically starts between 9 PM and 1 AM
    start_hour = fake.random_int(min=21, max=25) % 24
    start_datetime = base_datetime.replace(hour=start_hour, minute=fake.random_int(min=0, max=59))

    # Weekend catch-up: shorter on weekdays (Mon-Fri), longer on weekends (Sat-Sun)
    if config.weekend_catchup and start_datetime.weekday() < 5:
        # Weekday: use the lower end of the configured range
        dur_min = config.duration_min_minutes
        dur_max = min(config.duration_min_minutes + 60, config.duration_max_minutes)
    elif config.weekend_catchup:
        # Weekend: use extended range (8-10h)
        dur_min = max(config.duration_max_minutes - 60, config.duration_min_minutes)
        dur_max = min(config.duration_max_minutes + 120, 720)
    else:
        dur_min = config.duration_min_minutes
        dur_max = config.duration_max_minutes

    sleep_duration_minutes = fake.random_int(min=dur_min, max=dur_max)
    sleep_duration_seconds = sleep_duration_minutes * 60
    end_datetime = start_datetime + timedelta(seconds=float(sleep_duration_seconds))

    time_in_bed_minutes = sleep_duration_minutes + fake.random_int(min=15, max=60)

    deep_minutes = fake.random_int(min=60, max=120)
    rem_minutes = fake.random_int(min=80, max=140)
    light_minutes = sleep_duration_minutes - deep_minutes - rem_minutes - fake.random_int(min=10, max=40)
    awake_minutes = fake.random_int(min=5, max=30)

    sleep_efficiency = Decimal(sleep_duration_minutes) / Decimal(time_in_bed_minutes) * 100
    is_nap = fake.boolean(chance_of_getting_true=config.nap_chance_pct)

    sleep_id = uuid4()
    prov_config = PROVIDER_CONFIGS[provider]

    has_device = fake.boolean(chance_of_getting_true=80)
    device_name: str | None = None
    device_provider: str | None = None
    sw_version: str | None = None
    if has_device:
        device_name = fake.random.choice(prov_config["devices"])
        device_provider = provider.value
        sw_version = fake.random.choice(prov_config["os_versions"])

    record = EventRecordCreate(
        id=sleep_id,
        source=device_provider,
        user_id=user_id,
        category="sleep",
        type=None,
        duration_seconds=sleep_duration_seconds,
        source_name=prov_config["source_name"],
        device_model=device_name,
        provider=device_provider,
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


def _generate_personal_record(user_id: UUID, fake: Faker) -> PersonalRecordCreate:
    return PersonalRecordCreate(
        id=uuid4(),
        user_id=user_id,
        birth_date=fake.date_of_birth(minimum_age=18, maximum_age=80),
        gender=fake.random.choice(GENDERS) if fake.boolean(chance_of_getting_true=80) else None,
    )


def _generate_time_series_samples(
    workout_start: datetime,
    workout_end: datetime,
    fake: Faker,
    *,
    user_id: UUID,
    source: str,
    device_model: str | None = None,
    provider: str | None = None,
    software_version: str | None = None,
) -> list[TimeSeriesSampleCreate]:
    """Generate time series samples for a workout period."""
    samples: list[TimeSeriesSampleCreate] = []
    if not SERIES_TYPE_PERCENTAGES or not SERIES_VALUES_RANGES:
        return samples

    current_time = workout_start
    while current_time <= workout_end:
        for series_type, percentage in SERIES_TYPE_PERCENTAGES.items():
            min_value, max_value = SERIES_VALUES_RANGES[series_type]
            if fake.boolean(chance_of_getting_true=percentage):
                if min_value != int(min_value) or max_value != int(max_value):
                    value = fake.random.uniform(min_value, max_value)
                else:
                    value = fake.random_int(min=int(min_value), max=int(max_value))

                samples.append(
                    TimeSeriesSampleCreate(
                        id=uuid4(),
                        user_id=user_id,
                        source=source,
                        device_model=device_model,
                        provider=provider,
                        software_version=software_version,
                        recorded_at=current_time,
                        value=Decimal(str(value)),
                        series_type=series_type,
                    )
                )
        current_time += timedelta(seconds=fake.random_int(min=20, max=60))

    return samples


def _generate_user_connections(
    user_id: UUID,
    fake: Faker,
    num_connections: int = 2,
    providers: list[ProviderName] | None = None,
) -> tuple[list[UserConnectionCreate], dict[ProviderName, datetime]]:
    """Generate random provider connections for a user."""
    if providers:
        selected_providers = providers[:num_connections]
    else:
        selected_providers = fake.random.sample(SEED_PROVIDERS, min(num_connections, len(SEED_PROVIDERS)))

    now = datetime.now(timezone.utc)
    connections: list[UserConnectionCreate] = []
    provider_sync_times: dict[ProviderName, datetime] = {}

    for prov in selected_providers:
        is_sdk = prov == ProviderName.APPLE
        provider_sync_times[prov] = now - timedelta(days=fake.random_int(min=1, max=7))

        connection = UserConnectionCreate(
            id=uuid4(),
            user_id=user_id,
            provider=prov.value,
            provider_user_id=f"{prov.value}_{uuid4().hex[:8]}" if not is_sdk else None,
            provider_username=fake.user_name() if not is_sdk else None,
            access_token=f"access_{uuid4().hex}" if not is_sdk else None,
            refresh_token=f"refresh_{uuid4().hex}" if not is_sdk else None,
            token_expires_at=now + timedelta(days=30) if not is_sdk else None,
            scope="read_all" if not is_sdk else None,
            status=ConnectionStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        )
        connections.append(connection)

    return connections, provider_sync_times


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class SeedDataService:
    """Generates parameterized seed data for users."""

    def generate(self, db: Session, request: SeedDataRequest) -> dict:
        """Generate seed users with the given profile configuration.

        Returns a summary dict with counts of created entities.
        """
        profile = request.profile
        fake = Faker()

        personal_record_repo = CrudRepository(PersonalRecord)
        event_detail_repo = EventRecordDetailRepository(EventRecordDetail)
        connection_repo = CrudRepository(UserConnection)

        summary = {
            "users": 0,
            "connections": 0,
            "workouts": 0,
            "sleeps": 0,
            "time_series_samples": 0,
        }

        for user_num in range(1, request.num_users + 1):
            user = user_service.create(
                db,
                UserCreate(
                    first_name=fake.first_name(),
                    last_name=fake.last_name(),
                    email=fake.unique.email(),
                    external_user_id=fake.unique.uuid4() if fake.boolean(chance_of_getting_true=80) else None,
                ),
            )
            summary["users"] += 1

            # Personal record
            personal_record_repo.create(db, _generate_personal_record(user.id, fake))

            # Provider connections
            user_connections, provider_sync_times = _generate_user_connections(
                user.id,
                fake,
                num_connections=profile.num_connections,
                providers=profile.providers,
            )
            for conn_data in user_connections:
                created = connection_repo.create(db, conn_data)
                if created:
                    prov = ProviderName(conn_data.provider)
                    connection_repo.update(db, created, UserConnectionUpdate(last_synced_at=provider_sync_times[prov]))
                    summary["connections"] += 1

            # Workouts
            if profile.generate_workouts:
                for _ in range(profile.workout_config.count):
                    record, detail = _generate_workout(user.id, fake, provider_sync_times, profile.workout_config)
                    event_record_service.create(db, record)
                    event_record_service.create_detail(db, detail)
                    summary["workouts"] += 1

                    # Time series
                    if profile.generate_time_series and fake.boolean(
                        chance_of_getting_true=profile.workout_config.time_series_chance_pct
                    ):
                        samples = _generate_time_series_samples(
                            record.start_datetime,
                            record.end_datetime,
                            fake,
                            user_id=user.id,
                            source=record.source or "unknown",
                            device_model=record.device_model,
                            provider=record.provider,
                            software_version=record.software_version,
                        )
                        if samples:
                            timeseries_service.bulk_create_samples(db, samples)
                            summary["time_series_samples"] += len(samples)

            # Sleep records
            if profile.generate_sleep:
                for _ in range(profile.sleep_config.count):
                    record, detail = _generate_sleep(user.id, fake, provider_sync_times, profile.sleep_config)
                    event_record_service.create(db, record)
                    event_detail_repo.create(db, detail, detail_type="sleep")
                    summary["sleeps"] += 1

            db.commit()
            logger.info(
                "Seed user %d/%d created (workouts=%d, sleeps=%d, ts=%d)",
                user_num,
                request.num_users,
                summary["workouts"],
                summary["sleeps"],
                summary["time_series_samples"],
            )

        return summary


seed_data_service = SeedDataService()
