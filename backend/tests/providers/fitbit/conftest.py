"""
Fitbit provider test configuration.

Overrides session-scoped DB fixtures for pure unit tests that don't need a database.
"""

from unittest.mock import MagicMock, create_autospec

import pytest
from sqlalchemy import Engine


@pytest.fixture(scope="session")
def engine() -> MagicMock:
    """Override engine fixture — fitbit unit tests don't need a database."""
    return create_autospec(Engine, instance=True)


@pytest.fixture(autouse=True)
def set_factory_session() -> None:
    """Override autouse DB fixture — fitbit unit tests don't use factory-boy."""
    return  # override: suppress DB fixture for unit tests
