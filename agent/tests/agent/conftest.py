"""Conftest for agent unit tests.

All tests in this directory are pure unit tests with mocked dependencies —
no database is needed. Override the parent conftest's autouse
set_factory_session fixture so postgres is never brought up.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def set_factory_session() -> None:  # type: ignore[override]
    """No-op: agent unit tests don't use factories or a DB session."""
