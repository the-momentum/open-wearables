"""Extensions: separately installed packages that plug into the backend.

An extension registers an ``OWExtension`` subclass in its pyproject.toml:

    [project.entry-points."open_wearables.extensions"]
    my_extension = "my_extension.extension:MyExtension"

This module is the supported surface for extensions. Everything else in ``app`` can be
imported too, but may change between releases - pin ``requires_core`` accordingly.
"""

from collections.abc import Collection
from dataclasses import dataclass, field
from functools import cache
from importlib import import_module
from importlib.metadata import entry_points
from importlib.util import find_spec
from logging import getLogger
from typing import TYPE_CHECKING, Any

from packaging.specifiers import InvalidSpecifier, SpecifierSet

from app import __version__ as core_version
from app.utils.sentry_helpers import log_and_capture_error
from app.utils.structured_logging import log_structured

if TYPE_CHECKING:
    from fastapi import APIRouter

logger = getLogger(__name__)

ENTRY_POINT_GROUP = "open_wearables.extensions"

# Fields celery beat accepts in a schedule entry; any other field stops beat on startup.
_BEAT_ENTRY_FIELDS = frozenset({"task", "schedule", "args", "kwargs", "options", "relative"})


@dataclass
class OWExtension:
    name: str = ""
    display_name: str = ""
    version: str = ""
    # PEP 440 specifier, e.g. ">=0.9,<0.11"; empty accepts any core version.
    requires_core: str = ""
    # Celery autodiscovers a `tasks` module in each of these packages.
    celery_task_packages: list[str] = field(default_factory=list)

    def beat_schedule(self) -> dict[str, dict[str, Any]]:
        return {}

    def routers(self) -> list["APIRouter"]:
        """Routers mounted under the API v1 prefix."""
        return []


@dataclass
class LoadedExtension:
    name: str
    extension: OWExtension | None
    error: str | None = None

    @property
    def active(self) -> bool:
        return self.extension is not None and self.error is None


def _is_compatible(ext: OWExtension) -> str | None:
    """Return an error message when the extension does not support this core version."""
    if not ext.requires_core:
        return None
    try:
        supported = SpecifierSet(ext.requires_core).contains(core_version, prereleases=True)
    except InvalidSpecifier:
        return f"invalid requires_core specifier {ext.requires_core!r}"
    return None if supported else f"requires core {ext.requires_core}, running {core_version}"


def _task_import_error(ext: OWExtension) -> str | None:
    """Import the extension's task modules now: one that fails disables the extension here
    instead of stopping Celery workers and beat when they autodiscover tasks on startup."""
    for package in ext.celery_task_packages:
        module = f"{package}.tasks"
        try:
            # None when the package exists but has no tasks module, which Celery ignores too.
            if find_spec(module) is not None:
                import_module(module)
        except Exception as exc:
            log_and_capture_error(
                exc, logger, "Extension task module failed to import", extra={"extension": ext.name, "module": module}
            )
            return f"cannot import {module}: {exc}"
    return None


@cache
def get_extensions() -> tuple[LoadedExtension, ...]:
    """A broken or incompatible extension is logged and skipped instead of stopping the core."""
    loaded: list[LoadedExtension] = []
    for ep in entry_points(group=ENTRY_POINT_GROUP):
        try:
            ext = ep.load()()
        except Exception as exc:
            log_and_capture_error(exc, logger, "Failed to load extension", extra={"extension": ep.name})
            loaded.append(LoadedExtension(name=ep.name, extension=None, error=str(exc)))
            continue

        if not isinstance(ext, OWExtension):
            error = f"entry point does not resolve to an OWExtension subclass ({type(ext).__name__})"
        elif "__dataclass_fields__" not in vars(type(ext)):
            # Without @dataclass the inherited __init__ resets the subclass's attributes to the defaults.
            error = f"{type(ext).__name__} must be declared with @dataclass"
        else:
            error = _is_compatible(ext) or _task_import_error(ext)
        name = getattr(ext, "name", "") or ep.name
        if error:
            log_structured(
                logger, "warning", "Extension disabled", action="extension_disabled", extension=name, reason=error
            )
        else:
            log_structured(
                logger, "info", "Extension loaded", action="extension_loaded", extension=name, version=ext.version
            )
        loaded.append(LoadedExtension(name=name, extension=ext, error=error))
    return tuple(loaded)


def get_active_extensions() -> list[OWExtension]:
    return [e.extension for e in get_extensions() if e.active and e.extension is not None]


def collect_routers() -> list["APIRouter"]:
    routers: list[APIRouter] = []
    for ext in get_active_extensions():
        try:
            routers.extend(ext.routers())
        except Exception as exc:
            log_and_capture_error(
                exc, logger, "Extension routers() failed, its endpoints are not mounted", extra={"extension": ext.name}
            )
    return routers


def collect_beat_schedule(reserved: Collection[str] = ()) -> dict[str, dict[str, Any]]:
    """An entry is skipped when its key is in `reserved` (the core's own entries) or taken by an
    earlier extension, or when beat could not build it."""
    schedule: dict[str, dict[str, Any]] = {}
    for ext in get_active_extensions():
        try:
            entries = ext.beat_schedule()
        except Exception as exc:
            log_and_capture_error(
                exc,
                logger,
                "Extension beat_schedule() failed, its periodic tasks are not scheduled",
                extra={"extension": ext.name},
            )
            continue
        for key, entry in entries.items():
            if key in reserved or key in schedule:
                reason = "key already taken"
            elif not {"task", "schedule"} <= set(entry) <= _BEAT_ENTRY_FIELDS:
                reason = f"invalid fields {sorted(entry)}"
            else:
                schedule[key] = entry
                continue
            log_structured(
                logger,
                "error",
                "Extension beat entry skipped",
                action="extension_beat_entry_skipped",
                extension=ext.name,
                key=key,
                reason=reason,
            )
    return schedule


__all__ = [
    "ENTRY_POINT_GROUP",
    "LoadedExtension",
    "OWExtension",
    "collect_beat_schedule",
    "collect_routers",
    "get_active_extensions",
    "get_extensions",
]
