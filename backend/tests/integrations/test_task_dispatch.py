"""Tests for the pluggable task dispatch helper."""

from unittest.mock import MagicMock

import pytest

from app.config import settings
from app.integrations.celery import dispatch as dispatch_mod
from app.integrations.celery.dispatch import dispatch, is_inline


@pytest.fixture
def fake_task() -> MagicMock:
    task = MagicMock()
    task.run.return_value = {"ran": "inline"}
    task.delay.return_value = MagicMock(id="task-123")
    return task


def test_is_inline_reflects_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "task_execution_mode", "inline")
    assert is_inline() is True
    monkeypatch.setattr(settings, "task_execution_mode", "celery")
    assert is_inline() is False


def test_dispatch_inline_runs_task_body(monkeypatch: pytest.MonkeyPatch, fake_task: MagicMock) -> None:
    monkeypatch.setattr(settings, "task_execution_mode", "inline")

    result = dispatch(fake_task, 1, kw="x")

    fake_task.run.assert_called_once_with(1, kw="x")
    fake_task.delay.assert_not_called()
    assert result == {"ran": "inline"}


def test_dispatch_celery_enqueues_task(monkeypatch: pytest.MonkeyPatch, fake_task: MagicMock) -> None:
    monkeypatch.setattr(settings, "task_execution_mode", "celery")

    result = dispatch(fake_task, 1, kw="x")

    fake_task.delay.assert_called_once_with(1, kw="x")
    fake_task.run.assert_not_called()
    assert result.id == "task-123"


def test_dispatch_module_exposes_helpers() -> None:
    assert hasattr(dispatch_mod, "dispatch")
    assert hasattr(dispatch_mod, "is_inline")
