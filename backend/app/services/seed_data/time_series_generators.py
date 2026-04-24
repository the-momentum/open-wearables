"""Continuous time-series generators (independent of workouts).

Emits samples across a date range based on per-type cadence declared in
``series_type_config.yaml``. Workout-bound series are emitted by
``support_generators._generate_time_series_samples`` instead.
"""

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from faker import Faker

from app.schemas.enums import ProviderName, SeriesType
from app.schemas.model_crud.activities import TimeSeriesSampleCreate

from .constants import PAIRED_SERIES_SPECS, SERIES_TYPE_SPECS, Cadence, PairedGenSpec, SeriesTypeGenSpec


@dataclass(frozen=True)
class ProviderDescriptor:
    """Identifies a provider source for a generated sample."""

    provider: ProviderName
    source: str
    device_model: str | None
    software_version: str | None


def _sample_value(fake: Faker, min_value: float, max_value: float) -> Decimal:
    if min_value != int(min_value) or max_value != int(max_value):
        value = fake.random.uniform(min_value, max_value)
    else:
        value = fake.random_int(min=int(min_value), max=int(max_value))
    return Decimal(str(value))


def _make_sample(
    user_id: UUID,
    recorded_at: datetime,
    series_type: SeriesType,
    value: Decimal,
    provider_desc: ProviderDescriptor,
) -> TimeSeriesSampleCreate:
    return TimeSeriesSampleCreate(
        id=uuid4(),
        user_id=user_id,
        source=provider_desc.source,
        device_model=provider_desc.device_model,
        provider=provider_desc.provider.value,
        software_version=provider_desc.software_version,
        recorded_at=recorded_at,
        value=value,
        series_type=series_type,
    )


def _iter_intraday_timestamps(start: datetime, end: datetime, interval_seconds: int) -> Iterator[datetime]:
    cursor = start
    step = timedelta(seconds=interval_seconds)
    while cursor <= end:
        yield cursor
        cursor += step


def _iter_daily_timestamps(
    start: datetime, end: datetime, fake: Faker, hour_min: int, hour_max: int
) -> Iterator[datetime]:
    """Yield one timestamp per calendar day in [start, end]."""
    day = start.replace(hour=0, minute=0, second=0, microsecond=0)
    end_day = end.replace(hour=23, minute=59, second=59, microsecond=0)
    while day <= end_day:
        hour = fake.random_int(min=hour_min, max=hour_max)
        minute = fake.random_int(min=0, max=59)
        ts = day.replace(hour=hour, minute=minute)
        if start <= ts <= end:
            yield ts
        day += timedelta(days=1)


def _iter_weekly_timestamps(start: datetime, end: datetime, fake: Faker) -> Iterator[datetime]:
    cursor = start
    while cursor <= end:
        hour = fake.random_int(min=8, max=20)
        minute = fake.random_int(min=0, max=59)
        yield cursor.replace(hour=hour, minute=minute)
        cursor += timedelta(days=fake.random_int(min=6, max=8))


def _emit_intraday(
    spec: SeriesTypeGenSpec,
    series_type: SeriesType,
    user_id: UUID,
    start: datetime,
    end: datetime,
    provider_desc: ProviderDescriptor,
    fake: Faker,
) -> list[TimeSeriesSampleCreate]:
    interval = spec.interval_seconds or 600
    return [
        _make_sample(
            user_id,
            ts,
            series_type,
            _sample_value(fake, spec.min_value, spec.max_value),
            provider_desc,
        )
        for ts in _iter_intraday_timestamps(start, end, interval)
    ]


def _emit_daily(
    spec: SeriesTypeGenSpec,
    series_type: SeriesType,
    user_id: UUID,
    start: datetime,
    end: datetime,
    provider_desc: ProviderDescriptor,
    fake: Faker,
    *,
    hour_min: int = 8,
    hour_max: int = 21,
) -> list[TimeSeriesSampleCreate]:
    return [
        _make_sample(
            user_id,
            ts,
            series_type,
            _sample_value(fake, spec.min_value, spec.max_value),
            provider_desc,
        )
        for ts in _iter_daily_timestamps(start, end, fake, hour_min, hour_max)
    ]


def _emit_weekly(
    spec: SeriesTypeGenSpec,
    series_type: SeriesType,
    user_id: UUID,
    start: datetime,
    end: datetime,
    provider_desc: ProviderDescriptor,
    fake: Faker,
) -> list[TimeSeriesSampleCreate]:
    return [
        _make_sample(
            user_id,
            ts,
            series_type,
            _sample_value(fake, spec.min_value, spec.max_value),
            provider_desc,
        )
        for ts in _iter_weekly_timestamps(start, end, fake)
    ]


def _emit_paired(
    paired: PairedGenSpec,
    user_id: UUID,
    start: datetime,
    end: datetime,
    provider_resolver: Callable[[SeriesType], ProviderDescriptor | None],
    fake: Faker,
) -> list[TimeSeriesSampleCreate]:
    """Emit each member series at the SAME timestamp (e.g. BP systolic+diastolic)."""
    if paired.cadence is Cadence.WEEKLY:
        timestamps = list(_iter_weekly_timestamps(start, end, fake))
    else:
        timestamps = list(_iter_daily_timestamps(start, end, fake, 8, 21))

    samples: list[TimeSeriesSampleCreate] = []
    for ts in timestamps:
        for series_type, (lo, hi) in paired.members.items():
            provider_desc = provider_resolver(series_type)
            if provider_desc is None:
                continue
            samples.append(
                _make_sample(
                    user_id,
                    ts,
                    series_type,
                    _sample_value(fake, lo, hi),
                    provider_desc,
                )
            )
    return samples


def _generate_continuous_time_series(
    user_id: UUID,
    start: datetime,
    end: datetime,
    enabled_types: set[SeriesType],
    include_blood_pressure: bool,
    provider_map: dict[SeriesType, ProviderDescriptor],
    fake: Faker,
) -> list[TimeSeriesSampleCreate]:
    """Generate continuous time-series samples across [start, end].

    Only types present in ``enabled_types`` are emitted. Workout-bound types
    are skipped here (handled by the workout generator).
    """
    samples: list[TimeSeriesSampleCreate] = []

    for series_type, spec in SERIES_TYPE_SPECS.items():
        if spec.cadence is Cadence.WORKOUT_BOUND:
            continue
        if series_type not in enabled_types:
            continue
        provider_desc = provider_map.get(series_type)
        if provider_desc is None:
            continue

        match spec.cadence:
            case Cadence.INTRADAY:
                samples.extend(_emit_intraday(spec, series_type, user_id, start, end, provider_desc, fake))
            case Cadence.DAILY:
                samples.extend(_emit_daily(spec, series_type, user_id, start, end, provider_desc, fake))
            case Cadence.DAILY_MORNING:
                samples.extend(
                    _emit_daily(spec, series_type, user_id, start, end, provider_desc, fake, hour_min=6, hour_max=9)
                )
            case Cadence.WEEKLY:
                samples.extend(_emit_weekly(spec, series_type, user_id, start, end, provider_desc, fake))

    if include_blood_pressure:
        for paired in PAIRED_SERIES_SPECS:
            samples.extend(_emit_paired(paired, user_id, start, end, provider_map.get, fake))

    return samples
