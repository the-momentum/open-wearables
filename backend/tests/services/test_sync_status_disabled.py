"""Sync-status emission must be a no-op (no Redis access) when disabled."""

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.config import settings
from app.schemas.sync_status import SyncSource
from app.services import sync_status_service


def test_emit_noop_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "sync_status_enabled", False)
    redis_factory = MagicMock()
    monkeypatch.setattr(sync_status_service, "get_redis_client", redis_factory)

    # started() builds an event and routes through emit().
    sync_status_service.started(uuid4(), "apple", SyncSource.SDK, run_id="run-1")

    redis_factory.assert_not_called()


def test_emit_uses_redis_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "sync_status_enabled", True)
    redis_factory = MagicMock()
    monkeypatch.setattr(sync_status_service, "get_redis_client", redis_factory)

    sync_status_service.started(uuid4(), "apple", SyncSource.SDK, run_id="run-2")

    redis_factory.assert_called()
