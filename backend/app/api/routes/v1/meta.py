"""Public metadata endpoint — provider coverage matrix."""

from contextlib import suppress
from functools import lru_cache

from fastapi import APIRouter

from app.schemas.enums import ProviderName, SeriesType
from app.schemas.enums.series_types import SERIES_TYPE_CATEGORY_BY_ENUM, SERIES_TYPE_UNIT_BY_ENUM
from app.schemas.model_crud.coverage import (
    CoverageResponse,
    HealthScore,
    SleepField,
    TimeseriesCategory,
    TimeseriesMetric,
    WorkoutField,
)
from app.services.providers.base_strategy import ProviderCoverage
from app.services.providers.factory import ProviderFactory

router = APIRouter()

_CATEGORY_ORDER = [
    "Heart & Cardiovascular",
    "Blood & Respiratory",
    "Body Composition",
    "Fitness Metrics",
    "Activity - Basic",
    "Activity - Distance",
    "Activity - Walking",
    "Activity - Running",
    "Activity - Swimming",
    "Activity - Generic",
    "Environmental",
    "Provider-Specific",
    "Other",
]


def _build_coverage() -> CoverageResponse:
    factory = ProviderFactory()
    coverage_by_provider: dict[str, ProviderCoverage] = {}
    for name in ProviderName:
        # Skip sentinel providers (UNKNOWN/INTERNAL) that have no strategy.
        with suppress(ValueError):
            coverage_by_provider[name.value] = factory.get_provider(name.value).coverage
    providers = sorted(coverage_by_provider)

    # --- Timeseries grouped by category ---
    series_to_providers: dict[SeriesType, list[str]] = {}
    for provider, cov in coverage_by_provider.items():
        for st in cov.timeseries:
            series_to_providers.setdefault(st, []).append(provider)

    categories: dict[str, list[TimeseriesMetric]] = {}
    for st, prov_list in sorted(series_to_providers.items(), key=lambda x: x[0].value):
        cat = SERIES_TYPE_CATEGORY_BY_ENUM.get(st, "Other")
        unit = SERIES_TYPE_UNIT_BY_ENUM.get(st, "")
        categories.setdefault(cat, []).append(TimeseriesMetric(code=st.value, unit=unit, providers=sorted(prov_list)))

    timeseries = [TimeseriesCategory(name=cat, metrics=categories[cat]) for cat in _CATEGORY_ORDER if cat in categories]

    # --- Workout fields ---
    workout_to_providers: dict[str, list[str]] = {}
    for provider, cov in coverage_by_provider.items():
        for f in cov.workout_fields:
            workout_to_providers.setdefault(f, []).append(provider)

    workout_fields = [
        WorkoutField(code=f, providers=sorted(prov_list)) for f, prov_list in sorted(workout_to_providers.items())
    ]

    # --- Sleep fields ---
    sleep_to_providers: dict[str, list[str]] = {}
    for provider, cov in coverage_by_provider.items():
        for f in cov.sleep_fields:
            sleep_to_providers.setdefault(f, []).append(provider)

    sleep_fields = [
        SleepField(code=f, providers=sorted(prov_list)) for f, prov_list in sorted(sleep_to_providers.items())
    ]

    # --- Health scores ---
    score_to_providers: dict[str, list[str]] = {}
    for provider, cov in coverage_by_provider.items():
        for score in cov.health_scores:
            score_to_providers.setdefault(score.value, []).append(provider)

    health_scores = [
        HealthScore(code=score, providers=sorted(prov_list)) for score, prov_list in sorted(score_to_providers.items())
    ]

    return CoverageResponse(
        providers=providers,
        timeseries=timeseries,
        workout_fields=workout_fields,
        sleep_fields=sleep_fields,
        health_scores=health_scores,
    )


@lru_cache(maxsize=1)
def _coverage() -> CoverageResponse:
    """Coverage is static; build it once on first request (not at import time)."""
    return _build_coverage()


@router.get(
    "/meta/coverage",
    summary="Provider data coverage matrix",
    tags=["External: Meta"],
)
def get_coverage() -> CoverageResponse:
    return _coverage()
