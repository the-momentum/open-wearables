"""
Pytest configuration for Celery task tests.

Provides fixtures specific to testing asynchronous tasks.
"""

import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def mock_celery_app():
    """
    Configure Celery for synchronous test execution.

    Sets up Celery to run tasks eagerly (synchronously) during tests
    and propagate exceptions immediately.
    """
    with patch("app.integrations.celery.celery_app") as mock:
        mock.conf = {
            "task_always_eager": True,
            "task_eager_propagates": True,
        }
        yield mock


@pytest.fixture
def mock_session_local():
    """
    Mock SessionLocal for Celery tasks that create their own sessions.

    Returns a context manager that yields the test database session.
    """
    def _mock_session_context(db):
        """Create a mock SessionLocal context manager."""
        mock = MagicMock()
        mock.__enter__ = MagicMock(return_value=db)
        mock.__exit__ = MagicMock(return_value=None)
        return mock

    return _mock_session_context
