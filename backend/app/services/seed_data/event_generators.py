"""Generators for workout, sleep, meal, and personal record seed data."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from faker import Faker

from app.constants.sleep import SleepStageType
from app.schemas.enums import ProviderName, SeriesType, WorkoutType
from app.schemas.enums.workout_types import WORKOUTS_WITH_PACE
from app.schemas.model_crud.activities import (
    EventRecordCreate,
    EventRecordDetailCreate,
    MealDetailCreate,
    PersonalRecordCreate,
)
from app.schemas.model_crud.activities.sleep import SleepStage
from app.schemas.model_crud.activities.zones import HRZone, HRZones, PowerZone, PowerZones
from app.schemas.utils.seed_data import SLEEP_STAGE_PROFILES, MealConfig, SleepConfig, WorkoutConfig

from .constants import (
    DEFAULT_MEAL_TYPES,
    GENDERS,
    MEAL_TITLES,
    OUTDOOR_WORKOUT_TYPES,
    PROVIDER_CONFIGS,
)
from .time_series_generators import ProviderDescriptor

# Zones reach us from a FIT file (Garmin) or from per-zone durations in the
# provider's own payload (Whoop). Nobody else reports them, and seeding them
# elsewhere would make dev data claim a capability the integration does not have.
ZONE_PROVIDERS = frozenset({ProviderName.GARMIN, ProviderName.WHOOP})

# Power zones only where power samples also arrive: Garmin's activity details
# carry watts, Whoop's payload does not, and zones describing a metric nobody
# recorded are zones with nothing to draw them against.
POWER_ZONE_PROVIDERS = frozenset({ProviderName.GARMIN})

# Power is a bike metric: no other sport reports watts often enough to seed.
CYCLING_WORKOUT_TYPES = frozenset(
    {
        WorkoutType.CYCLING,
        WorkoutType.MOUNTAIN_BIKING,
        WorkoutType.INDOOR_CYCLING,
        WorkoutType.CYCLOCROSS,
    }
)

# Average speed (m/s) per pace-based sport; distance and Garmin's average_speed
# both derive from it so they agree with the workout duration.
_SPEED_RANGES: dict[frozenset[WorkoutType], tuple[float, float]] = {
    frozenset({WorkoutType.SWIMMING, WorkoutType.POOL_SWIMMING, WorkoutType.OPEN_WATER_SWIMMING}): (0.6, 1.4),
    frozenset(
        {
            WorkoutType.WALKING,
            WorkoutType.HIKING,
            WorkoutType.MOUNTAINEERING,
            WorkoutType.TRAIL_HIKING,
            WorkoutType.WALKING_FITNESS,
            WorkoutType.CASUAL_WALKING,
        }
    ): (1.0, 1.8),
    frozenset({WorkoutType.RUNNING, WorkoutType.TRAIL_RUNNING, WorkoutType.TREADMILL}): (2.3, 4.5),
    frozenset(
        {
            WorkoutType.CYCLING,
            WorkoutType.MOUNTAIN_BIKING,
            WorkoutType.INDOOR_CYCLING,
            WorkoutType.CYCLOCROSS,
            WorkoutType.E_BIKING,
        }
    ): (5.0, 10.0),
}
_DEFAULT_SPEED_RANGE = (1.5, 5.0)


def _pick_speed(workout_type: WorkoutType, fake: Faker) -> float:
    low, high = next((r for types, r in _SPEED_RANGES.items() if workout_type in types), _DEFAULT_SPEED_RANGE)
    return round(fake.random.uniform(low, high), 3)


# Fractions of max heart rate, the boundaries a FIT file carries.
HR_ZONE_CEILINGS = (0.6, 0.7, 0.8, 0.9, 1.0)

# Most of a session sits in the middle; the top zone is where it hurts.
ZONE_SHARES = (0.12, 0.28, 0.32, 0.20, 0.08)


def _generate_hr_zones(duration_seconds: int, heart_rate_max: int) -> HRZones:
    """Time in five zones, bounded as a FIT file bounds them."""
    return HRZones(
        zones=[
            HRZone(
                zone=index,
                seconds=round(duration_seconds * share, 1),
                max_bpm=round(heart_rate_max * ceiling),
            )
            for index, (share, ceiling) in enumerate(zip(ZONE_SHARES, HR_ZONE_CEILINGS, strict=True))
        ],
        max_hr=heart_rate_max,
        threshold_hr=round(heart_rate_max * 0.87),
    )


def _generate_power_zones(duration_seconds: int, ftp_watts: int) -> PowerZones:
    """Only the bike reports these, and only from a FIT file."""
    return PowerZones(
        zones=[
            PowerZone(
                zone=index,
                seconds=round(duration_seconds * share, 1),
                max_watts=round(ftp_watts * ceiling),
            )
            for index, (share, ceiling) in enumerate(zip(ZONE_SHARES, (0.6, 0.8, 0.95, 1.1, 1.5), strict=True))
        ],
        ftp_watts=ftp_watts,
    )


def _resolve_date_bounds(
    date_from: date | None,
    date_to: date | None,
    date_range_months: int,
    last_synced_at: datetime,
) -> tuple[datetime, datetime]:
    """Return (start_bound, end_bound) as tz-aware datetimes.

    If explicit dates are provided they take priority; otherwise fall back to
    ``date_range_months`` relative to ``last_synced_at``.
    """
    if date_from is not None and date_to is not None:
        start_bound = datetime(date_from.year, date_from.month, date_from.day, tzinfo=timezone.utc)
        end_bound = datetime(date_to.year, date_to.month, date_to.day, 23, 59, 59, tzinfo=timezone.utc)
    else:
        start_bound = last_synced_at - timedelta(days=date_range_months * 30)
        end_bound = last_synced_at

    return start_bound, end_bound


def _generate_sleep_stages(
    start_datetime: datetime,
    deep_minutes: int,
    rem_minutes: int,
    light_minutes: int,
    awake_minutes: int,
    fake: Faker,
) -> list[SleepStage]:
    """Generate contiguous sleep stage intervals whose totals match the aggregate columns."""

    def _split_minutes(total: int, min_block: int, max_block: int) -> list[int]:
        """Split *total* minutes into a list of random-sized blocks."""
        if total <= 0:
            return []
        blocks: list[int] = []
        remaining = total
        while remaining > 0:
            size = min(fake.random_int(min=min_block, max=max_block), remaining)
            blocks.append(size)
            remaining -= size
        return blocks

    # Build pool of (stage_type, duration_minutes) blocks
    pool: list[tuple[SleepStageType, int]] = []
    for mins, stage, lo, hi in [
        (deep_minutes, SleepStageType.DEEP, 5, 25),
        (rem_minutes, SleepStageType.REM, 3, 35),
        (light_minutes, SleepStageType.LIGHT, 3, 20),
        (awake_minutes, SleepStageType.AWAKE, 1, 5),
    ]:
        for block in _split_minutes(mins, lo, hi):
            pool.append((stage, block))

    fake.random.shuffle(pool)

    # Assign contiguous timestamps
    stages: list[SleepStage] = []
    cursor = start_datetime
    for stage_type, block_minutes in pool:
        block_end = cursor + timedelta(minutes=block_minutes)
        stages.append(SleepStage(stage=stage_type, start_time=cursor, end_time=block_end))
        cursor = block_end

    return stages


def _generate_workout(
    user_id: UUID,
    fake: Faker,
    provider: ProviderName,
    last_synced_at: datetime,
    config: WorkoutConfig,
    device: ProviderDescriptor | None = None,
) -> tuple[EventRecordCreate, EventRecordDetailCreate]:
    """Generate a single workout with parameters from *config*, recorded on *device* if given."""
    start_bound, end_bound = _resolve_date_bounds(
        config.date_from,
        config.date_to,
        config.date_range_months,
        last_synced_at,
    )
    start_datetime = fake.date_time_between(
        start_date=start_bound,
        end_date=end_bound,
        tzinfo=timezone.utc,
    )

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

    # Oura doesn't expose device info via its API
    device_name: str | None = None
    sw_version: str | None = None
    if device is not None:
        device_name = device.device_model
        sw_version = device.software_version
    elif provider != ProviderName.OURA and fake.boolean(chance_of_getting_true=80):
        device_name = fake.random.choice(prov_config["devices"])
        sw_version = fake.random.choice(prov_config["os_versions"])

    # Provider-specific workout detail fields
    energy_burned: Decimal | None = None
    elevation_gain: Decimal | None = None
    average_speed: Decimal | None = None
    distance: Decimal | None = None

    # Every seeded provider reports distance for pace-based sports
    speed = _pick_speed(workout_type, fake) if workout_type in WORKOUTS_WITH_PACE else None
    if speed is not None:
        distance = Decimal(round(speed * duration_seconds))

    if provider == ProviderName.GARMIN:
        energy_burned = Decimal(fake.random_int(min=200, max=800))
        if workout_type in OUTDOOR_WORKOUT_TYPES:
            elevation_gain = Decimal(fake.random_int(min=10, max=500))
        if speed is not None:
            average_speed = Decimal(str(speed))
    elif provider == ProviderName.APPLE:
        energy_burned = Decimal(fake.random_int(min=150, max=700))
        if workout_type in OUTDOOR_WORKOUT_TYPES:
            elevation_gain = Decimal(fake.random_int(min=5, max=300))
    elif provider in (ProviderName.POLAR, ProviderName.SUUNTO):
        energy_burned = Decimal(fake.random_int(min=100, max=700))
        if workout_type in OUTDOOR_WORKOUT_TYPES:
            elevation_gain = Decimal(fake.random_int(min=5, max=400))

    hr_zones = None
    power_zones = None
    if provider in ZONE_PROVIDERS:
        hr_zones = _generate_hr_zones(duration_seconds, heart_rate_max)
        if provider in POWER_ZONE_PROVIDERS and workout_type in CYCLING_WORKOUT_TYPES:
            power_zones = _generate_power_zones(duration_seconds, fake.random_int(min=180, max=280))

    record = EventRecordCreate(
        id=workout_id,
        source=provider.value,
        user_id=user_id,
        category="workout",
        type=workout_type,
        duration_seconds=duration_seconds,
        source_name=prov_config["source_name"],
        device_model=device_name,
        provider=provider.value,
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
        energy_burned=energy_burned,
        distance=distance,
        total_elevation_gain=elevation_gain,
        average_speed=average_speed,
        hr_zones=hr_zones,
        power_zones=power_zones,
    )

    return record, detail


def _generate_sleep(
    user_id: UUID,
    fake: Faker,
    provider: ProviderName,
    last_synced_at: datetime,
    config: SleepConfig,
) -> tuple[EventRecordCreate, EventRecordDetailCreate]:
    """Generate a single sleep record with parameters from *config*."""
    start_bound, end_bound = _resolve_date_bounds(
        config.date_from,
        config.date_to,
        config.date_range_months,
        last_synced_at,
    )
    base_datetime = fake.date_time_between(
        start_date=start_bound,
        end_date=end_bound,
        tzinfo=timezone.utc,
    )

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

    # Resolve stage distribution (named profile overrides custom distribution)
    dist = config.stage_distribution
    if config.stage_profile and config.stage_profile in SLEEP_STAGE_PROFILES:
        dist = SLEEP_STAGE_PROFILES[config.stage_profile]["distribution"]

    deep_pct = fake.random_int(min=dist.deep_pct_range[0], max=dist.deep_pct_range[1]) / 100
    rem_pct = fake.random_int(min=dist.rem_pct_range[0], max=dist.rem_pct_range[1]) / 100
    awake_pct = fake.random_int(min=dist.awake_pct_range[0], max=dist.awake_pct_range[1]) / 100

    # Clamp total non-light to 95% to guarantee light sleep
    total_pct = deep_pct + rem_pct + awake_pct
    if total_pct > 0.95:
        scale = 0.95 / total_pct
        deep_pct, rem_pct, awake_pct = deep_pct * scale, rem_pct * scale, awake_pct * scale

    deep_minutes = max(1, round(sleep_duration_minutes * deep_pct))
    rem_minutes = max(1, round(sleep_duration_minutes * rem_pct))
    awake_minutes = max(1, round(sleep_duration_minutes * awake_pct))
    light_minutes = sleep_duration_minutes - deep_minutes - rem_minutes - awake_minutes
    if light_minutes < 1:
        deep_minutes -= 1 - light_minutes
        light_minutes = 1

    sleep_efficiency = Decimal(sleep_duration_minutes) / Decimal(time_in_bed_minutes) * 100
    is_nap = fake.boolean(chance_of_getting_true=config.nap_chance_pct)

    # Generate contiguous sleep stage intervals
    sleep_stages = _generate_sleep_stages(start_datetime, deep_minutes, rem_minutes, light_minutes, awake_minutes, fake)

    sleep_id = uuid4()
    prov_config = PROVIDER_CONFIGS[provider]

    # Oura doesn't expose device info via its API
    device_name: str | None = None
    sw_version: str | None = None
    if provider != ProviderName.OURA and fake.boolean(chance_of_getting_true=80):
        device_name = fake.random.choice(prov_config["devices"])
        sw_version = fake.random.choice(prov_config["os_versions"])

    record = EventRecordCreate(
        id=sleep_id,
        source=provider.value,
        user_id=user_id,
        category="sleep",
        type=None,
        duration_seconds=sleep_duration_seconds,
        source_name=prov_config["source_name"],
        device_model=device_name,
        provider=provider.value,
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
        sleep_stages=sleep_stages,
    )

    return record, detail


def _generate_personal_record(user_id: UUID, fake: Faker) -> PersonalRecordCreate:
    return PersonalRecordCreate(
        id=uuid4(),
        user_id=user_id,
        birth_date=fake.date_of_birth(minimum_age=18, maximum_age=80),
        gender=fake.random.choice(GENDERS) if fake.boolean(chance_of_getting_true=80) else None,
    )


def _generate_spread_timestamps(fake: Faker, start: datetime, end: datetime, count: int) -> list[datetime]:
    """*count* timestamps, one random draw per equal-width slice of [start, end]."""
    if count <= 0:
        return []
    bucket_width = (end - start) / count
    return [
        start + i * bucket_width + timedelta(seconds=fake.random.uniform(0, bucket_width.total_seconds()))
        for i in range(count)
    ]


def _generate_meal(
    user_id: UUID,
    fake: Faker,
    provider: ProviderName,
    start_datetime: datetime,
    config: MealConfig,
) -> tuple[EventRecordCreate, MealDetailCreate]:
    """Generate a single meal at *start_datetime*, its nutrients on the meal detail."""
    meal_type = fake.random.choice(DEFAULT_MEAL_TYPES)
    title = fake.random.choice(MEAL_TITLES[meal_type])

    end_datetime = start_datetime + timedelta(minutes=fake.random_int(min=5, max=30))

    calories = fake.random_int(min=config.calories_range[0], max=config.calories_range[1])
    protein_pct = fake.random.uniform(0.15, 0.30)
    fat_pct = fake.random.uniform(0.20, 0.35)
    carbs_pct = 1 - protein_pct - fat_pct

    protein_g = round(calories * protein_pct / 4, 1)
    fat_g = round(calories * fat_pct / 9, 1)
    carbs_g = round(calories * carbs_pct / 4, 1)
    fiber_g = round(carbs_g * fake.random.uniform(0.08, 0.15), 1)

    meal_id = uuid4()
    prov_config = PROVIDER_CONFIGS[provider]

    device_name: str | None = None
    sw_version: str | None = None
    if fake.boolean(chance_of_getting_true=80):
        device_name = fake.random.choice(prov_config["devices"])
        sw_version = fake.random.choice(prov_config["os_versions"])

    record = EventRecordCreate(
        id=meal_id,
        external_id=str(meal_id),
        source=provider.value,
        user_id=user_id,
        category="meal",
        type=None,
        duration_seconds=int((end_datetime - start_datetime).total_seconds()),
        source_name=prov_config["source_name"],
        device_model=device_name,
        provider=provider.value,
        software_version=sw_version,
        start_datetime=start_datetime,
        end_datetime=end_datetime,
    )
    detail = MealDetailCreate(
        record_id=meal_id,
        title=title,
        meal_type=meal_type,
        nutrients={
            SeriesType.dietary_energy_consumed: float(calories),
            SeriesType.dietary_protein: protein_g,
            SeriesType.dietary_carbohydrates: carbs_g,
            SeriesType.dietary_fat_total: fat_g,
            SeriesType.dietary_fiber: fiber_g,
            SeriesType.hydration: float(fake.random_int(min=100, max=500)),
        },
    )
    return record, detail
