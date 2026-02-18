"""
Celery task test fixtures.
"""

from collections.abc import Generator
from typing import Callable
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session


@pytest.fixture
def mock_celery_app() -> Generator[MagicMock, None, None]:
    """Synchronous (eager) Celery app."""
    with patch("celery.current_app") as mock:
        mock.conf = {
            "task_always_eager": True,
            "task_eager_propagates": True,
        }
        yield mock


@pytest.fixture
def mock_session_local() -> Callable[[Session], MagicMock]:
    """Context-manager mock for ``SessionLocal`` in task code."""

    def _ctx(db: Session) -> MagicMock:
        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=db)
        cm.__exit__ = MagicMock(return_value=None)
        return cm

    return _ctx
