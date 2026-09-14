"""Guard tests: keep each provider's coverage.py in sync with its implementation.

For every provider that declares a coverage.py, we statically scan its
implementation files and assert that:

- every emitted ``series_type=SeriesType.<x>`` is declared in ``TIMESERIES``
- every EventRecordDetail data field it sets is declared in
  ``WORKOUT_FIELDS``, ``SLEEP_FIELDS`` or ``MENSTRUAL_CYCLE_FIELDS``
- declared field/score names are valid

A drift (new metric in the code, stale coverage) fails the test.
"""

import importlib
import re
from pathlib import Path
from types import ModuleType

import pytest

from app.constants.series_types.sdk.metric_types import (
    ANDROID_METRIC_TYPE_TO_SERIES_TYPE,
    APPLE_METRIC_TYPE_TO_SERIES_TYPE,
)
from app.constants.series_types.sdk.workout_statistics import WORKOUT_STATISTIC_TYPE_TO_SERIES_TYPE
from app.schemas.enums import SeriesType
from app.schemas.enums.health_score_category import HealthScoreCategory
from app.schemas.model_crud.activities import EventRecordDetailCreate
from app.services.providers.factory import ProviderFactory
from app.services.providers.google.health_api.metrics import METRICS as GOOGLE_HEALTH_API_METRICS

PROVIDERS_DIR = Path("app/services/providers")

# Implementation files that may emit timeseries / set detail fields.
IMPL_FILES = ("data_247.py", "workouts.py", "webhook_handler.py", "webhook_service.py")

# SDK providers emit via the shared healthkit pipeline (not their own data_247);
# their timeseries is derived from the SDK maps and sleep details are set in the
# shared sleep service, so those shared files are scanned for them too.
SDK_PROVIDERS = {"apple", "samsung", "google"}
SDK_SHARED_FILES = (
    Path("app/services/apple/healthkit/import_service.py"),
    Path("app/services/apple/healthkit/sleep_service.py"),
    Path("app/services/apple/apple_xml/xml_service.py"),
)

# EventRecordDetail fields that are NOT part of the coverage matrix (structural
# or composite objects rather than scalar metric coverage).
STRUCTURAL_DETAIL_FIELDS = {"record_id", "segments", "hr_zones", "power_zones"}


def _all_detail_fields() -> set[str]:
    """Fields across EventRecordDetailCreate AND every polymorphic subtype.

    Subtypes (e.g. MenstrualCycleDetailCreate) add their own fields on top of
    the base; scanning only the base would leave those fields untracked and let
    a whole detail category drift out of coverage unnoticed.
    """
    fields: set[str] = set()
    stack = [EventRecordDetailCreate]
    while stack:
        cls = stack.pop()
        fields |= set(cls.model_fields)
        stack.extend(cls.__subclasses__())
    return fields


ALL_DETAIL_FIELDS = _all_detail_fields()
TRACKED_DETAIL_FIELDS = ALL_DETAIL_FIELDS - STRUCTURAL_DETAIL_FIELDS

_SERIES_EMIT_RE = re.compile(r"series_type=SeriesType\.(\w+)")


def _providers_with_coverage() -> list[str]:
    return sorted(p.name for p in PROVIDERS_DIR.iterdir() if p.is_dir() and (p / "coverage.py").exists())


def _impl_source(provider: str) -> str:
    paths = [PROVIDERS_DIR / provider / fname for fname in IMPL_FILES]
    if provider in SDK_PROVIDERS:
        paths += list(SDK_SHARED_FILES)
    return "\n".join(p.read_text() for p in paths if p.exists())


def _load_coverage(provider: str) -> ModuleType:
    return importlib.import_module(f"app.services.providers.{provider}.coverage")


def _timeseries(cov: ModuleType) -> frozenset:
    return getattr(cov, "TIMESERIES", frozenset())


def _workout_fields(cov: ModuleType) -> frozenset:
    return getattr(cov, "WORKOUT_FIELDS", frozenset())


def _sleep_fields(cov: ModuleType) -> frozenset:
    return getattr(cov, "SLEEP_FIELDS", frozenset())


def _menstrual_cycle_fields(cov: ModuleType) -> frozenset:
    return getattr(cov, "MENSTRUAL_CYCLE_FIELDS", frozenset())


def _health_scores(cov: ModuleType) -> frozenset:
    return getattr(cov, "HEALTH_SCORES", frozenset())


@pytest.mark.parametrize("provider", _providers_with_coverage())
def test_emitted_timeseries_are_declared(provider: str) -> None:
    cov = _load_coverage(provider)
    source = _impl_source(provider)

    emitted = {SeriesType[name] for name in _SERIES_EMIT_RE.findall(source)}
    undeclared = emitted - _timeseries(cov)

    assert not undeclared, (
        f"{provider}: emits SeriesType not declared in coverage.TIMESERIES: {sorted(s.value for s in undeclared)}"
    )


@pytest.mark.parametrize("provider", _providers_with_coverage())
def test_set_detail_fields_are_declared(provider: str) -> None:
    cov = _load_coverage(provider)
    source = _impl_source(provider)
    declared = _workout_fields(cov) | _sleep_fields(cov) | _menstrual_cycle_fields(cov)

    used = {field for field in TRACKED_DETAIL_FIELDS if re.search(rf"\b{field}=", source) or f'"{field}"' in source}
    undeclared = used - declared

    assert not undeclared, f"{provider}: sets EventRecordDetail fields not declared in coverage: {sorted(undeclared)}"


_SDK_METRIC_MAP = {
    "apple": APPLE_METRIC_TYPE_TO_SERIES_TYPE,
    "samsung": ANDROID_METRIC_TYPE_TO_SERIES_TYPE,
    "google": ANDROID_METRIC_TYPE_TO_SERIES_TYPE,
}


# SDK providers that also pull cloud series contribute extra timeseries beyond the
# SDK maps. google is hybrid: Health Connect SDK + Health API daily rollups.
_EXTRA_SDK_SERIES: dict[str, frozenset[SeriesType]] = {
    "google": frozenset(s for m in GOOGLE_HEALTH_API_METRICS for s in m.series_types()),
}


@pytest.mark.parametrize("provider", sorted(SDK_PROVIDERS))
def test_sdk_timeseries_match_maps(provider: str) -> None:
    cov = _load_coverage(provider)
    expected = (
        frozenset(_SDK_METRIC_MAP[provider].values())
        | frozenset(WORKOUT_STATISTIC_TYPE_TO_SERIES_TYPE.values())
        | _EXTRA_SDK_SERIES.get(provider, frozenset())
    )
    assert _timeseries(cov) == expected, (
        f"{provider}: TIMESERIES must equal the union of the provider-specific SDK metric + "
        f"workout-statistic maps (plus cloud rollup series for hybrid providers)"
    )


@pytest.mark.parametrize("provider", _providers_with_coverage())
def test_strategy_exposes_full_coverage(provider: str) -> None:
    cov = _load_coverage(provider)
    exposed = ProviderFactory().get_provider(provider).coverage

    assert exposed.timeseries == _timeseries(cov), f"{provider}: strategy drops/alters TIMESERIES"
    assert exposed.workout_fields == _workout_fields(cov), f"{provider}: strategy drops/alters WORKOUT_FIELDS"
    assert exposed.sleep_fields == _sleep_fields(cov), f"{provider}: strategy drops/alters SLEEP_FIELDS"
    assert exposed.menstrual_cycle_fields == _menstrual_cycle_fields(cov), (
        f"{provider}: strategy drops/alters MENSTRUAL_CYCLE_FIELDS"
    )
    assert exposed.health_scores == _health_scores(cov), f"{provider}: strategy drops/alters HEALTH_SCORES"


@pytest.mark.parametrize("provider", _providers_with_coverage())
def test_declared_names_are_valid(provider: str) -> None:
    cov = _load_coverage(provider)

    bad_fields = (_workout_fields(cov) | _sleep_fields(cov) | _menstrual_cycle_fields(cov)) - ALL_DETAIL_FIELDS
    assert not bad_fields, f"{provider}: unknown EventRecordDetail fields declared: {sorted(bad_fields)}"

    assert all(isinstance(s, HealthScoreCategory) for s in _health_scores(cov))
    assert all(isinstance(s, SeriesType) for s in _timeseries(cov))
