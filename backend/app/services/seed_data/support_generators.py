"""Generators for time series samples and user connections."""

from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from faker import Faker

from app.schemas.auth import ConnectionStatus
from app.schemas.enums import ProviderName
from app.schemas.model_crud.activities import TimeSeriesSampleCreate
from app.schemas.model_crud.user_management import UserConnectionCreate

from .constants import SEED_PROVIDERS, SERIES_TYPE_PERCENTAGES, SERIES_VALUES_RANGES


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
    now: datetime,
    num_connections: int = 2,
    providers: list[ProviderName] | None = None,
) -> tuple[list[UserConnectionCreate], dict[ProviderName, datetime]]:
    """Generate random provider connections for a user."""
    if providers:
        selected_providers = providers[:num_connections]
    else:
        selected_providers = fake.random.sample(SEED_PROVIDERS, min(num_connections, len(SEED_PROVIDERS)))

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
