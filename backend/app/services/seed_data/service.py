"""SeedDataService - orchestrates seed data generation across all entity types."""

import logging
import os
import random
from datetime import date, datetime, timedelta, timezone

from faker import Faker
from sqlalchemy.orm import Session

from app.models import EventRecordDetail, PersonalRecord, UserConnection
from app.repositories import CrudRepository
from app.repositories.event_record_detail_repository import EventRecordDetailRepository
from app.schemas.enums import ProviderName, SeriesType, WorkoutType
from app.schemas.model_crud.user_management import UserConnectionUpdate, UserCreate
from app.schemas.utils.seed_data import SeedDataRequest
from app.services.event_record_service import event_record_service
from app.services.health_score_service import health_score_service
from app.services.timeseries_service import timeseries_service
from app.services.user_service import user_service

from .constants import PAIRED_SERIES_SPECS, PROVIDER_CONFIGS, SERIES_TYPE_SPECS, Cadence
from .event_generators import _generate_personal_record, _generate_sleep, _generate_workout
from .health_score_generators import _generate_health_scores
from .support_generators import _generate_time_series_samples, _generate_user_connections
from .time_series_generators import ProviderDescriptor, _generate_continuous_time_series

logger = logging.getLogger(__name__)


def _build_provider_map(
    providers: list[ProviderName],
    fake: Faker,
) -> dict[SeriesType, ProviderDescriptor]:
    """Assign one provider descriptor per series type, reused for all samples.

    Ensures that e.g. every heart_rate sample for a user comes from the same
    provider + device + software version. Covers non-workout-bound types plus
    paired members (blood pressure).
    """
    provider_map: dict[SeriesType, ProviderDescriptor] = {}
    if not providers:
        return provider_map

    all_series = [st for st, spec in SERIES_TYPE_SPECS.items() if spec.cadence is not Cadence.WORKOUT_BOUND]
    for paired in PAIRED_SERIES_SPECS:
        all_series.extend(paired.members.keys())

    for series_type in all_series:
        prov = fake.random.choice(providers)
        prov_config = PROVIDER_CONFIGS[prov]
        is_sdk = prov == ProviderName.APPLE
        # Oura exposes no device info; Apple is SDK-style (source name only)
        device_model = None if prov == ProviderName.OURA else fake.random.choice(prov_config["devices"])
        software_version = (
            None if prov == ProviderName.OURA or is_sdk else fake.random.choice(prov_config["os_versions"])
        )
        provider_map[series_type] = ProviderDescriptor(
            provider=prov,
            source=prov_config["source_name"],
            device_model=device_model,
            software_version=software_version,
        )

    return provider_map


def _resolve_time_series_window(
    config_date_from: date | None,
    config_date_to: date | None,
    date_range_months: int,
    last_synced_at: datetime,
) -> tuple[datetime, datetime]:
    if config_date_from and config_date_to:
        start = datetime(config_date_from.year, config_date_from.month, config_date_from.day, tzinfo=timezone.utc)
        end = datetime(config_date_to.year, config_date_to.month, config_date_to.day, 23, 59, 59, tzinfo=timezone.utc)
    else:
        start = last_synced_at - timedelta(days=date_range_months * 30)
        end = last_synced_at
    return start, end


class SeedDataService:
    """Generates parameterized seed data for users."""

    def generate(self, db: Session, request: SeedDataRequest) -> dict:
        """Generate seed users with the given profile configuration.

        Returns a summary dict with counts of created entities.
        """
        profile = request.profile
        seed = request.random_seed if request.random_seed is not None else random.randint(0, 2**31 - 1)
        random.seed(seed)
        fake = Faker()
        Faker.seed(seed)
        # Unseeded Faker for user identity fields (name, email, UUID) so they
        # are always unique across runs, even when reusing the same seed.
        identity_fake = Faker()
        identity_fake.seed_instance(int.from_bytes(os.urandom(8)))

        # Use a fixed anchor date so the same seed always produces identical
        # data regardless of when the generator is run.
        now = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        personal_record_repo = CrudRepository(PersonalRecord)
        event_detail_repo = EventRecordDetailRepository(EventRecordDetail)
        connection_repo = CrudRepository(UserConnection)

        summary = {
            "users": 0,
            "connections": 0,
            "workouts": 0,
            "sleeps": 0,
            "time_series_samples": 0,
            "health_scores": 0,
        }

        enabled_types: set[SeriesType] = set(profile.time_series_config.enabled_types)

        for user_num in range(1, request.num_users + 1):
            user = user_service.create(
                db,
                UserCreate(
                    first_name=f"[SEED:{seed}|{profile.preset or 'custom'}] {identity_fake.first_name()}",
                    last_name=identity_fake.last_name(),
                    email=identity_fake.unique.email(),
                    external_user_id=identity_fake.unique.uuid4() if fake.boolean(chance_of_getting_true=80) else None,
                ),
            )
            summary["users"] += 1

            # Personal record
            personal_record_repo.create(db, _generate_personal_record(user.id, fake))

            # Provider connections
            user_connections, provider_sync_times = _generate_user_connections(
                user.id,
                fake,
                now,
                num_connections=profile.num_connections,
                providers=profile.providers,
            )
            for conn_data in user_connections:
                created = connection_repo.create(db, conn_data)
                if created:
                    prov = ProviderName(conn_data.provider)
                    connection_repo.update(db, created, UserConnectionUpdate(last_synced_at=provider_sync_times[prov]))
                    summary["connections"] += 1

            # Stable per-user mapping: each series type gets one provider, used
            # for every sample of that type across the whole generation run.
            provider_map = _build_provider_map(list(provider_sync_times.keys()), fake)

            # Workouts (+ workout-bound time series)
            if profile.generate_workouts:
                for _ in range(profile.workout_config.count):
                    prov = fake.random.choice(list(provider_sync_times.keys()))
                    record, detail = _generate_workout(
                        user.id, fake, prov, provider_sync_times[prov], profile.workout_config
                    )
                    event_record_service.create(db, record)
                    event_record_service.create_detail(db, detail)
                    summary["workouts"] += 1

                    if profile.generate_time_series and record.type is not None and enabled_types:
                        samples = _generate_time_series_samples(
                            record.start_datetime,
                            record.end_datetime,
                            WorkoutType(record.type),
                            enabled_types,
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
                    prov = fake.random.choice(list(provider_sync_times.keys()))
                    record, detail = _generate_sleep(
                        user.id, fake, prov, provider_sync_times[prov], profile.sleep_config
                    )
                    event_record_service.create(db, record)
                    event_detail_repo.create(db, detail, detail_type="sleep")
                    summary["sleeps"] += 1

            # Continuous time series (independent of workouts)
            if profile.generate_time_series and provider_sync_times:
                last_synced_at = max(provider_sync_times.values())
                ts_start, ts_end = _resolve_time_series_window(
                    profile.time_series_config.date_from,
                    profile.time_series_config.date_to,
                    profile.time_series_config.date_range_months,
                    last_synced_at,
                )
                continuous_samples = _generate_continuous_time_series(
                    user_id=user.id,
                    start=ts_start,
                    end=ts_end,
                    enabled_types=enabled_types,
                    include_blood_pressure=profile.time_series_config.include_blood_pressure,
                    provider_map=provider_map,
                    fake=fake,
                )
                if continuous_samples:
                    timeseries_service.bulk_create_samples(db, continuous_samples)
                    summary["time_series_samples"] += len(continuous_samples)

            # Health scores - one batch per provider covering the full seeded date range
            if profile.generate_workouts or profile.generate_sleep:
                date_range_months = (
                    max(
                        profile.workout_config.date_range_months if profile.generate_workouts else 0,
                        profile.sleep_config.date_range_months if profile.generate_sleep else 0,
                    )
                    or 6
                )
                for prov, last_synced_at in provider_sync_times.items():
                    sb = last_synced_at - timedelta(days=date_range_months * 30)
                    scores = _generate_health_scores(user.id, prov, sb, last_synced_at, fake)
                    if scores:
                        health_score_service.bulk_create(db, scores)
                        summary["health_scores"] += len(scores)

            db.commit()
            logger.info(
                "Seed user %d/%d created (workouts=%d, sleeps=%d, ts=%d, health_scores=%d)",
                user_num,
                request.num_users,
                summary["workouts"],
                summary["sleeps"],
                summary["time_series_samples"],
                summary["health_scores"],
            )

        summary["seed_used"] = seed
        return summary


seed_data_service = SeedDataService()
