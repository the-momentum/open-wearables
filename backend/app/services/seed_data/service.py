"""SeedDataService — orchestrates seed data generation across all entity types."""

import logging
import os
import random
from datetime import datetime, timedelta, timezone

from faker import Faker
from sqlalchemy.orm import Session

from app.models import EventRecordDetail, PersonalRecord, UserConnection
from app.repositories import CrudRepository
from app.repositories.event_record_detail_repository import EventRecordDetailRepository
from app.schemas.enums import ProviderName
from app.schemas.model_crud.user_management import UserConnectionUpdate, UserCreate
from app.schemas.utils.seed_data import SeedDataRequest
from app.services.event_record_service import event_record_service
from app.services.health_score_service import health_score_service
from app.services.timeseries_service import timeseries_service
from app.services.user_service import user_service

from .event_generators import _generate_personal_record, _generate_sleep, _generate_workout
from .health_score_generators import _generate_health_scores
from .support_generators import _generate_time_series_samples, _generate_user_connections

logger = logging.getLogger(__name__)


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

            # Workouts
            if profile.generate_workouts:
                for _ in range(profile.workout_config.count):
                    prov = fake.random.choice(list(provider_sync_times.keys()))
                    record, detail = _generate_workout(
                        user.id, fake, prov, provider_sync_times[prov], profile.workout_config
                    )
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
                    prov = fake.random.choice(list(provider_sync_times.keys()))
                    record, detail = _generate_sleep(
                        user.id, fake, prov, provider_sync_times[prov], profile.sleep_config
                    )
                    event_record_service.create(db, record)
                    event_detail_repo.create(db, detail, detail_type="sleep")
                    summary["sleeps"] += 1

            # Health scores — one batch per provider covering the full seeded date range
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
