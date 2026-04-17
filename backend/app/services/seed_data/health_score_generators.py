"""Generator for provider health score seed data."""

from datetime import datetime, timedelta
from uuid import UUID, uuid4

from faker import Faker

from app.schemas.enums import HealthScoreCategory, ProviderName
from app.schemas.model_crud.activities import HealthScoreCreate, ScoreComponent

from .constants import (
    _GARMIN_SLEEP_COMPONENTS,
    _GARMIN_SLEEP_QUALIFIERS,
    _OURA_ACTIVITY_COMPONENTS,
    _OURA_READINESS_COMPONENTS,
    _OURA_SLEEP_COMPONENTS,
)


def _generate_health_scores(
    user_id: UUID,
    provider: ProviderName,
    start_bound: datetime,
    end_bound: datetime,
    fake: Faker,
) -> list[HealthScoreCreate]:
    """Generate realistic daily health scores for *provider* over a date range.

    Oura produces SLEEP, READINESS, and ACTIVITY scores with named component
    breakdowns.  Garmin produces SLEEP (with qualifier), BODY_BATTERY, and
    STRESS scores.  WHOOP produces SLEEP and RECOVERY scores.  All other
    providers return an empty list.
    """
    if provider == ProviderName.OURA:
        return _generate_oura_scores(user_id, start_bound, end_bound, fake)
    if provider == ProviderName.GARMIN:
        return _generate_garmin_scores(user_id, start_bound, end_bound, fake)
    if provider == ProviderName.WHOOP:
        return _generate_whoop_scores(user_id, start_bound, end_bound, fake)
    return []


def _generate_oura_scores(
    user_id: UUID,
    start_bound: datetime,
    end_bound: datetime,
    fake: Faker,
) -> list[HealthScoreCreate]:
    scores: list[HealthScoreCreate] = []
    current = start_bound.replace(hour=8, minute=0, second=0, microsecond=0)

    base_sleep = fake.random_int(min=55, max=88)
    base_readiness = fake.random_int(min=55, max=88)
    base_activity = fake.random_int(min=50, max=85)

    while current <= end_bound:
        sleep_val = max(30, min(100, base_sleep + fake.random_int(min=-8, max=8)))
        readiness_val = max(30, min(100, base_readiness + fake.random_int(min=-8, max=8)))
        activity_val = max(30, min(100, base_activity + fake.random_int(min=-10, max=10)))

        scores.append(
            HealthScoreCreate(
                id=uuid4(),
                user_id=user_id,
                provider=ProviderName.OURA,
                category=HealthScoreCategory.SLEEP,
                value=sleep_val,
                recorded_at=current,
                components={k: ScoreComponent(value=fake.random_int(min=40, max=100)) for k in _OURA_SLEEP_COMPONENTS},
            )
        )
        scores.append(
            HealthScoreCreate(
                id=uuid4(),
                user_id=user_id,
                provider=ProviderName.OURA,
                category=HealthScoreCategory.READINESS,
                value=readiness_val,
                recorded_at=current,
                components={
                    k: ScoreComponent(value=fake.random_int(min=40, max=100)) for k in _OURA_READINESS_COMPONENTS
                },
            )
        )
        scores.append(
            HealthScoreCreate(
                id=uuid4(),
                user_id=user_id,
                provider=ProviderName.OURA,
                category=HealthScoreCategory.ACTIVITY,
                value=activity_val,
                recorded_at=current,
                components={
                    k: ScoreComponent(value=fake.random_int(min=40, max=100)) for k in _OURA_ACTIVITY_COMPONENTS
                },
            )
        )

        # Drift the bases slightly day-over-day for realism
        base_sleep = max(40, min(95, base_sleep + fake.random_int(min=-3, max=3)))
        base_readiness = max(40, min(95, base_readiness + fake.random_int(min=-3, max=3)))
        base_activity = max(35, min(95, base_activity + fake.random_int(min=-4, max=4)))
        current += timedelta(days=1)

    return scores


def _generate_garmin_scores(
    user_id: UUID,
    start_bound: datetime,
    end_bound: datetime,
    fake: Faker,
) -> list[HealthScoreCreate]:
    scores: list[HealthScoreCreate] = []
    current = start_bound.replace(hour=8, minute=0, second=0, microsecond=0)

    base_sleep = fake.random_int(min=55, max=88)
    base_battery = fake.random_int(min=50, max=90)
    base_stress = fake.random_int(min=15, max=55)

    while current <= end_bound:
        sleep_val = max(30, min(100, base_sleep + fake.random_int(min=-8, max=8)))
        battery_val = max(10, min(100, base_battery + fake.random_int(min=-10, max=10)))
        stress_val = max(5, min(95, base_stress + fake.random_int(min=-8, max=8)))

        sleep_qualifier = (
            "EXCELLENT" if sleep_val >= 80 else "GOOD" if sleep_val >= 65 else "FAIR" if sleep_val >= 50 else "POOR"
        )
        stress_qualifier = "High Stress" if stress_val >= 60 else "Medium Stress" if stress_val >= 30 else "Low Stress"

        scores.append(
            HealthScoreCreate(
                id=uuid4(),
                user_id=user_id,
                provider=ProviderName.GARMIN,
                category=HealthScoreCategory.SLEEP,
                value=sleep_val,
                qualifier=sleep_qualifier,
                recorded_at=current,
                components={
                    k: ScoreComponent(qualifier=fake.random.choice(_GARMIN_SLEEP_QUALIFIERS))
                    for k in _GARMIN_SLEEP_COMPONENTS
                },
            )
        )
        scores.append(
            HealthScoreCreate(
                id=uuid4(),
                user_id=user_id,
                provider=ProviderName.GARMIN,
                category=HealthScoreCategory.BODY_BATTERY,
                value=battery_val,
                recorded_at=current,
            )
        )
        scores.append(
            HealthScoreCreate(
                id=uuid4(),
                user_id=user_id,
                provider=ProviderName.GARMIN,
                category=HealthScoreCategory.STRESS,
                value=stress_val,
                qualifier=stress_qualifier,
                recorded_at=current,
            )
        )

        base_sleep = max(40, min(95, base_sleep + fake.random_int(min=-3, max=3)))
        base_battery = max(15, min(95, base_battery + fake.random_int(min=-5, max=5)))
        base_stress = max(5, min(90, base_stress + fake.random_int(min=-4, max=4)))
        current += timedelta(days=1)

    return scores


def _generate_whoop_scores(
    user_id: UUID,
    start_bound: datetime,
    end_bound: datetime,
    fake: Faker,
) -> list[HealthScoreCreate]:
    scores: list[HealthScoreCreate] = []
    current = start_bound.replace(hour=8, minute=0, second=0, microsecond=0)

    base_sleep = fake.random_int(min=50, max=90)
    base_recovery = fake.random_int(min=40, max=85)

    while current <= end_bound:
        sleep_val = max(20, min(100, base_sleep + fake.random_int(min=-10, max=10)))
        recovery_val = max(20, min(100, base_recovery + fake.random_int(min=-8, max=8)))

        scores.append(
            HealthScoreCreate(
                id=uuid4(),
                user_id=user_id,
                provider=ProviderName.WHOOP,
                category=HealthScoreCategory.SLEEP,
                value=sleep_val,
                recorded_at=current,
                components={
                    "sleep_consistency_percentage": ScoreComponent(value=fake.random_int(min=40, max=100)),
                    "sleep_efficiency_percentage": ScoreComponent(value=fake.random_int(min=60, max=98)),
                    "respiratory_rate": ScoreComponent(value=round(fake.random.uniform(12.0, 20.0), 1)),
                },
            )
        )
        scores.append(
            HealthScoreCreate(
                id=uuid4(),
                user_id=user_id,
                provider=ProviderName.WHOOP,
                category=HealthScoreCategory.RECOVERY,
                value=recovery_val,
                recorded_at=current,
                components={
                    "resting_heart_rate": ScoreComponent(value=fake.random_int(min=42, max=72)),
                    "hrv_rmssd_milli": ScoreComponent(value=round(fake.random.uniform(20.0, 90.0), 1)),
                    "spo2_percentage": ScoreComponent(value=round(fake.random.uniform(94.0, 100.0), 1)),
                    "skin_temp_celsius": ScoreComponent(value=round(fake.random.uniform(33.5, 37.0), 1)),
                },
            )
        )

        base_sleep = max(20, min(100, base_sleep + fake.random_int(min=-4, max=4)))
        base_recovery = max(20, min(100, base_recovery + fake.random_int(min=-4, max=4)))
        current += timedelta(days=1)

    return scores
