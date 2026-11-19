"""Tests for the extensions' queue lookup that worker.sh runs."""

import importlib.util
from pathlib import Path
from types import ModuleType
from unittest.mock import create_autospec

import pytest

_SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "start" / "extension_queues.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("extension_queues", _SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


extension_queues = _load_module()


def test_prints_the_extension_queues(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(extension_queues, "collect_celery_queues", lambda: ("my_queue", "other"))

    extension_queues.main()

    captured = capsys.readouterr()
    assert captured.out == "EXTENSION_QUEUES=my_queue,other\n"
    assert captured.err == ""


def test_failed_lookup_prints_no_queues_and_the_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        extension_queues,
        "collect_celery_queues",
        create_autospec(extension_queues.collect_celery_queues, side_effect=RuntimeError("boom")),
    )

    extension_queues.main()

    captured = capsys.readouterr()
    assert captured.out == "EXTENSION_QUEUES=\n"
    assert "boom" in captured.err
