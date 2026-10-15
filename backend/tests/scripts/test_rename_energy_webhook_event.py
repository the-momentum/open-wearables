"""Tests for the webhook subscription rename from series.energy to series.active_energy.

A Svix endpoint filters on event-type names, so the migration decides per endpoint what its
filter list should become. The risky cases are the ones that must NOT be written: an endpoint
with no filters (a firehose), one already migrated, and one whose only filter is the old name
(removing it would silently widen the endpoint to every event).
See scripts/data_migrations/rename_energy_webhook_event.py.
"""

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import cast

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "rename_energy_webhook_event",
    Path(__file__).resolve().parents[2] / "scripts/data_migrations/rename_energy_webhook_event.py",
)
assert _SPEC is not None
assert _SPEC.loader is not None
_MODULE = cast(ModuleType, importlib.util.module_from_spec(_SPEC))
_SPEC.loader.exec_module(_MODULE)

OLD = _MODULE.OLD_EVENT
NEW = _MODULE.NEW_EVENT
target_filters = _MODULE._target_filters


class TestTargetFilters:
    @pytest.mark.parametrize(
        ("current", "phase", "expected"),
        [
            pytest.param([OLD, "series.steps.created"], "add", [OLD, "series.steps.created", NEW], id="add-appends"),
            pytest.param([OLD, NEW], "add", None, id="add-is-idempotent"),
            pytest.param(["series.steps.created"], "add", None, id="add-ignores-unrelated"),
            pytest.param([], "add", None, id="add-leaves-firehose-alone"),
            pytest.param([OLD], "add", [OLD, NEW], id="add-keeps-both-across-the-deploy"),
            pytest.param([OLD, NEW], "remove", [NEW], id="remove-drops-the-old-name"),
            pytest.param([NEW], "remove", None, id="remove-is-idempotent"),
        ],
    )
    def test_filter_transitions(self, current: list[str], phase: str, expected: list[str] | None) -> None:
        assert target_filters(current, phase) == expected

    def test_remove_never_empties_the_filter_list(self) -> None:
        """An endpoint left with no filters would start receiving every event type."""
        assert target_filters([OLD], "remove") is None
