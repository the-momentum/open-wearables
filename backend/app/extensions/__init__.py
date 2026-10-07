"""Extensions: separately installed packages that plug into the backend.

An extension registers an ``OWExtension`` subclass in its pyproject.toml:

    [project.entry-points."open_wearables.extensions"]
    my_extension = "my_extension.extension:MyExtension"

This module is the supported surface for extensions, with ``app.extensions.migrations`` for
their database tables. Everything else in ``app`` can be imported too, but may change between
releases - pin ``requires_core`` accordingly.
"""

from collections.abc import Collection
from dataclasses import dataclass, field
from datetime import timedelta
from functools import cache
from importlib import import_module
from importlib.metadata import entry_points
from importlib.util import find_spec
from logging import getLogger
from typing import Any

from fastapi import APIRouter
from packaging.specifiers import InvalidSpecifier, SpecifierSet

from app import __version__ as core_version
from app.database import engine
from app.extensions import events, migrations
from app.utils.sentry_helpers import log_and_capture_error
from app.utils.structured_logging import log_structured

logger = getLogger(__name__)

ENTRY_POINT_GROUP = "open_wearables.extensions"

# The fields Celery documents for a beat_schedule entry; beat fails to start on an unknown one.
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
    # Alembic script location of the extension's own history, e.g. "my_extension:migrations".
    migrations: str = ""

    def beat_schedule(self) -> dict[str, dict[str, Any]]:
        return {}

    def routers(self) -> list[APIRouter]:
        """Routers mounted under the API v1 prefix."""
        return []

    def event_handlers(self) -> dict[str, str]:
        """Celery task queued with ``user_id`` per event, e.g. ``{"sync.completed": "my_ext.tasks.recompute"}``."""
        return {}


@dataclass
class LoadedExtension:
    name: str
    extension: OWExtension | None
    error: str | None = None

    @property
    def active(self) -> bool:
        return self.extension is not None and self.error is None


def _compatibility_error(ext: OWExtension) -> str | None:
    """Return an error message when the extension does not support this core version."""
    if not ext.requires_core:
        return None
    try:
        supported = SpecifierSet(ext.requires_core).contains(core_version, prereleases=True)
    except InvalidSpecifier:
        return f"invalid requires_core specifier {ext.requires_core!r}"
    return None if supported else f"requires core {ext.requires_core}, running {core_version}"


def _migration_error(ext: OWExtension) -> str | None:
    """Migrate the extension's tables to head, so it never runs against an older schema."""
    if not ext.migrations:
        return None
    if error := migrations.name_error(ext.name):
        return error
    try:
        migrations.upgrade(ext.name, ext.migrations, engine)
    except Exception as exc:
        log_and_capture_error(exc, logger, "Extension migrations failed", extra={"extension": ext.name})
        return f"migrations failed: {exc}"
    return None


def _task_import_error(ext: OWExtension) -> str | None:
    """Import the task modules now, so one that fails disables the extension instead of stopping Celery."""
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
            error = _compatibility_error(ext) or _migration_error(ext) or _task_import_error(ext)
        name = getattr(ext, "name", "") or ep.name
        if error:
            log_structured(
                logger, "warning", "Extension disabled", action="extension_disabled", extension=name, reason=error
            )
        else:
            log_structured(
                logger, "info", "Extension loaded", action="extension_loaded", extension=name, version=ext.version
            )
        extension = ext if isinstance(ext, OWExtension) else None
        loaded.append(LoadedExtension(name=name, extension=extension, error=error))
    return tuple(loaded)


def get_active_extensions() -> list[OWExtension]:
    return [e.extension for e in get_extensions() if e.active and e.extension is not None]


def collect_routers() -> list[APIRouter]:
    routers: list[APIRouter] = []
    for ext in get_active_extensions():
        try:
            contributed = list(ext.routers())
        except Exception as exc:
            log_and_capture_error(
                exc, logger, "Extension routers() failed, its endpoints are not mounted", extra={"extension": ext.name}
            )
            continue
        for router in contributed:
            if isinstance(router, APIRouter):
                routers.append(router)
            else:
                log_structured(
                    logger,
                    "error",
                    "Extension router skipped",
                    action="extension_router_skipped",
                    extension=ext.name,
                    reason=f"not an APIRouter: {type(router).__name__}",
                )
    return routers


def collect_event_handlers() -> dict[str, tuple[str, ...]]:
    handlers: dict[str, list[str]] = {}
    for ext in get_active_extensions():
        try:
            declared = dict(ext.event_handlers())
        except Exception as exc:
            log_and_capture_error(
                exc, logger, "Extension event_handlers() failed, it receives no events", extra={"extension": ext.name}
            )
            continue
        for event, task in declared.items():
            if event not in events.SUPPORTED_EVENTS:
                error = f"unknown event {event!r}"
            elif not isinstance(task, str) or not task:
                error = f"invalid task name {task!r}"
            else:
                handlers.setdefault(event, []).append(task)
                continue
            log_structured(
                logger,
                "error",
                "Extension event handler skipped",
                action="extension_event_handler_skipped",
                extension=ext.name,
                event=event,
                reason=error,
            )
    return {event: tuple(tasks) for event, tasks in handlers.items()}


def _beat_entry_error(key: str, entry: Any, reserved: Collection[str], scheduled: Collection[str]) -> str | None:
    if key in reserved or key in scheduled:
        return "key already taken"
    if not isinstance(entry, dict):
        return f"entry is a {type(entry).__name__}, not a dict"
    if not {"task", "schedule"} <= set(entry) <= _BEAT_ENTRY_FIELDS:
        return f"invalid fields {sorted(entry)}"
    if not isinstance(entry["task"], str) or not entry["task"]:
        return f"invalid task name {entry['task']!r}"
    schedule = entry["schedule"]
    # What celery.schedules.maybe_schedule can turn into a schedule; anything else stops beat.
    if not isinstance(schedule, int | float | timedelta) and not hasattr(schedule, "is_due"):
        return f"invalid schedule {schedule!r}"
    return None


def collect_beat_schedule(reserved: Collection[str] = ()) -> dict[str, dict[str, Any]]:
    """An entry is skipped when its key is in ``reserved`` (the core's own entries) or taken by an
    earlier extension, or when beat could not build it."""
    schedule: dict[str, dict[str, Any]] = {}
    for ext in get_active_extensions():
        try:
            entries = dict(ext.beat_schedule())
        except Exception as exc:
            log_and_capture_error(
                exc,
                logger,
                "Extension beat_schedule() failed, its periodic tasks are not scheduled",
                extra={"extension": ext.name},
            )
            continue
        for key, entry in entries.items():
            error = _beat_entry_error(key, entry, reserved, schedule)
            if error:
                log_structured(
                    logger,
                    "error",
                    "Extension beat entry skipped",
                    action="extension_beat_entry_skipped",
                    extension=ext.name,
                    key=key,
                    reason=error,
                )
            else:
                schedule[key] = entry
    return schedule


__all__ = [
    "ENTRY_POINT_GROUP",
    "LoadedExtension",
    "OWExtension",
    "collect_beat_schedule",
    "collect_event_handlers",
    "collect_routers",
    "get_active_extensions",
    "get_extensions",
]
