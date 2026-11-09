"""Tests for the extensions' queue lookup that worker.sh runs."""

import importlib.util
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

_SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "start" / "extension_queues.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("extension_queues", _SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


main = _load_module().main


def _patch_extensions(monkeypatch: pytest.MonkeyPatch, queues: object, loaded: tuple = ()) -> None:
    def collect() -> tuple[str, ...]:
        if isinstance(queues, Exception):
            raise queues
        return queues  # type: ignore[return-value]

    monkeypatch.setattr("app.extensions.collect_celery_queues", collect)
    monkeypatch.setattr("app.extensions.get_extensions", lambda: loaded)


def test_prints_the_extension_queues(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    _patch_extensions(monkeypatch, ("agent", "other"))

    main()

    captured = capsys.readouterr()
    assert captured.out == "EXTENSION_QUEUES=agent,other\n"
    assert captured.err == ""


def test_failed_lookup_prints_no_queues_and_the_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _patch_extensions(monkeypatch, RuntimeError("boom"))

    main()

    captured = capsys.readouterr()
    assert captured.out == "EXTENSION_QUEUES=\n"
    assert "boom" in captured.err


def test_reports_a_disabled_extension(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    loaded = (
        SimpleNamespace(name="agent", error="migration failed"),
        SimpleNamespace(name="fine", error=None),
    )
    _patch_extensions(monkeypatch, (), loaded)

    main()

    captured = capsys.readouterr()
    assert captured.out == "EXTENSION_QUEUES=\n"
    assert "Extension agent disabled" in captured.err
    assert "migration failed" in captured.err
    assert "fine" not in captured.err
