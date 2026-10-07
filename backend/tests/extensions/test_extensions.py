from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any

import pytest

import app.extensions as extensions
from app.extensions import (
    OWExtension,
    collect_beat_schedule,
    collect_routers,
    get_active_extensions,
    get_extensions,
)


@dataclass
class CompatibleExtension(OWExtension):
    name: str = "compatible"
    version: str = "1.0.0"
    requires_core: str = ">=0"


@dataclass
class IncompatibleExtension(OWExtension):
    name: str = "incompatible"
    requires_core: str = "<0.0.1"


@dataclass
class InvalidSpecifierExtension(OWExtension):
    name: str = "invalid_specifier"
    requires_core: str = "not a specifier"


@dataclass
class FaultyHooksExtension(OWExtension):
    name: str = "faulty_hooks"

    def beat_schedule(self) -> dict[str, dict[str, Any]]:
        raise RuntimeError("boom")

    def routers(self) -> list[Any]:
        raise RuntimeError("boom")


@dataclass
class ContributingExtension(OWExtension):
    name: str = "contributing"

    def beat_schedule(self) -> dict[str, dict[str, Any]]:
        return {"contributing-job": {"task": "contributing.tasks.run", "schedule": 60.0}}

    def routers(self) -> list[Any]:
        from fastapi import APIRouter

        return [APIRouter()]


class NotAnExtension:
    pass


def _broken() -> OWExtension:
    raise ImportError("missing dependency")


class FakeEntryPoint:
    def __init__(self, name: str, target: Callable[[], Any]) -> None:
        self.name = name
        self._target = target

    def load(self) -> Callable[[], Any]:
        return self._target


@pytest.fixture
def installed(monkeypatch: pytest.MonkeyPatch) -> Iterator[Callable[..., None]]:
    """Replace the installed entry points; the discovery cache is reset around each test."""

    def install(*eps: FakeEntryPoint) -> None:
        monkeypatch.setattr(extensions, "entry_points", lambda group: list(eps))
        get_extensions.cache_clear()

    yield install
    get_extensions.cache_clear()


class TestDiscovery:
    def test_no_extensions_installed(self, installed: Callable[..., None]) -> None:
        installed()

        assert get_extensions() == ()
        assert get_active_extensions() == []

    def test_compatible_extension_is_active(self, installed: Callable[..., None]) -> None:
        installed(FakeEntryPoint("compatible", CompatibleExtension))

        [loaded] = get_extensions()

        assert loaded.active
        assert loaded.name == "compatible"
        assert [e.name for e in get_active_extensions()] == ["compatible"]

    @pytest.mark.parametrize(
        ("entry_point", "error"),
        [
            (FakeEntryPoint("incompatible", IncompatibleExtension), "requires core <0.0.1"),
            (FakeEntryPoint("invalid_specifier", InvalidSpecifierExtension), "invalid requires_core"),
            (FakeEntryPoint("broken", _broken), "missing dependency"),
            (FakeEntryPoint("not_an_extension", NotAnExtension), "does not resolve to an OWExtension"),
        ],
    )
    def test_unusable_extension_is_skipped(
        self, installed: Callable[..., None], entry_point: FakeEntryPoint, error: str
    ) -> None:
        installed(entry_point, FakeEntryPoint("compatible", CompatibleExtension))

        loaded = {e.name: e for e in get_extensions()}

        assert not loaded[entry_point.name].active
        assert error in (loaded[entry_point.name].error or "")
        # A bad extension never takes the others down with it.
        assert [e.name for e in get_active_extensions()] == ["compatible"]


class TestHooks:
    def test_failing_hooks_do_not_affect_other_extensions(self, installed: Callable[..., None]) -> None:
        installed(
            FakeEntryPoint("faulty_hooks", FaultyHooksExtension),
            FakeEntryPoint("contributing", ContributingExtension),
        )

        assert list(collect_beat_schedule()) == ["contributing-job"]
        assert len(collect_routers()) == 1


class TestDefaults:
    def test_base_extension_contributes_nothing(self) -> None:
        ext = OWExtension()

        assert ext.beat_schedule() == {}
        assert ext.routers() == []
        assert ext.celery_task_packages == []
