"""Tests for moving webhook subscriptions off the renamed and retired series event types.

See scripts/data_migrations/rename_series_webhook_events.py.
"""

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import cast

import pytest

from app.schemas.webhooks.event_types import WebhookEventType

_SPEC = importlib.util.spec_from_file_location(
    "rename_series_webhook_events",
    Path(__file__).resolve().parents[2] / "scripts/data_migrations/rename_series_webhook_events.py",
)
assert _SPEC is not None
assert _SPEC.loader is not None
_MODULE = cast(ModuleType, importlib.util.module_from_spec(_SPEC))
_SPEC.loader.exec_module(_MODULE)

OLD = "series.walking_heart_rate_average.created"
NEW = "series.walking_heart_rate.created"
RETIRED = "series.average_met.created"
STEPS = "series.steps.created"
BASAL = "series.basal_energy.created"
BMR = "series.basal_metabolic_rate.created"
target_filters = _MODULE._target_filters


@pytest.mark.parametrize(
    ("current", "phase", "expected"),
    [
        pytest.param([OLD, STEPS], "add", [OLD, STEPS, NEW], id="add-appends-the-new-name"),
        pytest.param([OLD, NEW], "add", None, id="add-is-idempotent"),
        pytest.param([RETIRED, STEPS], "add", None, id="add-has-nothing-to-add-for-a-retired-event"),
        pytest.param([], "add", None, id="add-leaves-firehose-alone"),
        pytest.param([OLD, NEW, RETIRED, STEPS], "remove", [NEW, STEPS], id="remove-drops-old-and-retired"),
        pytest.param([NEW, STEPS], "remove", None, id="remove-is-idempotent"),
        pytest.param([RETIRED], "remove", None, id="remove-never-empties-the-filter-list"),
        pytest.param([BASAL, STEPS], "add", [BASAL, STEPS, BMR], id="add-appends-the-split-off-event"),
        pytest.param([BASAL, BMR], "add", None, id="add-split-is-idempotent"),
        pytest.param([BASAL, STEPS], "remove", None, id="remove-keeps-the-split-source-it-still-fires"),
        pytest.param([OLD, BASAL], "remove", [BASAL], id="remove-drops-renamed-but-keeps-split-source"),
    ],
)
def test_filter_transitions(current: list[str], phase: str, expected: list[str] | None) -> None:
    assert target_filters(current, phase) == expected


def test_every_new_name_is_one_we_dispatch() -> None:
    dispatched = {event.value for event in WebhookEventType}
    assert {new for new in _MODULE.RENAMED.values() if new} <= dispatched
    assert not set(_MODULE.RENAMED) & dispatched


def test_split_pairs_stay_add_only() -> None:
    """A split's source keeps firing for the providers whose data never moved, so neither
    direction may appear in RENAMED, and both names must be ones we dispatch."""
    dispatched = {event.value for event in WebhookEventType}
    assert set(_MODULE.SPLIT) <= dispatched
    assert set(_MODULE.SPLIT.values()) <= dispatched
    assert not set(_MODULE.SPLIT) & set(_MODULE.RENAMED)
    assert not set(_MODULE.SPLIT.values()) & set(_MODULE.RENAMED)
