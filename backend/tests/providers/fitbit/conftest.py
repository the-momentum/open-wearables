"""
Fitbit provider test configuration.

Disables factory session setup for pure unit tests that don't use factories.
"""

import pytest


@pytest.fixture(autouse=True)
def set_factory_session() -> None:
    """Override autouse DB fixture — fitbit unit tests don't use factory-boy."""
    return  # override: suppress DB fixture for unit tests
