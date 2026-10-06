"""Extension point for add-on modules shipped as separate Python packages.

An extension registers itself under the ``open_wearables.extensions`` entry point
group in its own pyproject.toml:

    [project.entry-points."open_wearables.extensions"]
    health_scores = "ow_health_scores.extension:HealthScoresExtension"

The entry point resolves to an ``OWExtension`` subclass. Core instantiates it once
per process and wires in its Celery tasks, beat schedule and API routers. Extensions
write into core tables (e.g. ``health_score``), so their output goes out through the
regular API and webhooks.

This module is the supported surface for extensions. Everything else in ``app`` can be
imported too, but may change between releases - pin ``requires_core`` accordingly.
"""

from dataclasses import dataclass, field
from functools import cache
from importlib.metadata import entry_points
from logging import getLogger
from typing import TYPE_CHECKING, Any

from packaging.specifiers import InvalidSpecifier, SpecifierSet

from app import __version__ as core_version

if TYPE_CHECKING:
    from fastapi import APIRouter

logger = getLogger(__name__)

ENTRY_POINT_GROUP = "open_wearables.extensions"


@dataclass
class OWExtension:
    """Base class for extensions. Subclasses override the attributes and hooks they need."""

    name: str = ""
    display_name: str = ""
    version: str = ""
    # PEP 440 specifier of supported core versions, e.g. ">=0.9,<0.11". Empty = any.
    requires_core: str = ""
    # Packages Celery autodiscovers tasks in (looks for a `tasks` module inside each).
    celery_task_packages: list[str] = field(default_factory=list)

    def beat_schedule(self) -> dict[str, dict[str, Any]]:
        """Periodic tasks merged into the Celery beat schedule."""
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


@cache
def get_extensions() -> tuple[LoadedExtension, ...]:
    """Discover installed extensions once per process.

    A broken or incompatible extension is logged and skipped - it must never stop the core
    from starting.
    """
    loaded: list[LoadedExtension] = []
    for ep in entry_points(group=ENTRY_POINT_GROUP):
        try:
            ext = ep.load()()
        except Exception as exc:
            logger.exception("Failed to load extension %s", ep.name)
            loaded.append(LoadedExtension(name=ep.name, extension=None, error=str(exc)))
            continue

        if not isinstance(ext, OWExtension):
            error = f"entry point does not resolve to an OWExtension subclass ({type(ext).__name__})"
        else:
            error = _is_compatible(ext)
        if error:
            logger.warning("Extension %s disabled: %s", ep.name, error)
        else:
            logger.info("Extension %s %s loaded", ext.name or ep.name, ext.version)
        loaded.append(LoadedExtension(name=getattr(ext, "name", "") or ep.name, extension=ext, error=error))
    return tuple(loaded)


def get_active_extensions() -> list[OWExtension]:
    """Installed extensions that loaded and support this core version."""
    return [e.extension for e in get_extensions() if e.active and e.extension is not None]


def collect_routers() -> list["APIRouter"]:
    """Routers of all active extensions; an extension whose hook raises is skipped."""
    routers: list[APIRouter] = []
    for ext in get_active_extensions():
        try:
            routers.extend(ext.routers())
        except Exception:
            logger.exception("Extension %s: routers() failed, its endpoints are not mounted", ext.name)
    return routers


def collect_beat_schedule() -> dict[str, dict[str, Any]]:
    """Merged beat schedule of all active extensions; an extension whose hook raises is skipped."""
    schedule: dict[str, dict[str, Any]] = {}
    for ext in get_active_extensions():
        try:
            schedule.update(ext.beat_schedule())
        except Exception:
            logger.exception("Extension %s: beat_schedule() failed, its periodic tasks are not scheduled", ext.name)
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
