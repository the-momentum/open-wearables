import subprocess
import sys
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from celery.schedules import crontab
from fastapi import APIRouter
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import text as sa_text

import app.extensions as extensions
from app.database import BaseDbModel
from app.extensions import (
    LoadedExtension,
    OWExtension,
    collect_beat_schedule,
    collect_routers,
    get_active_extensions,
    get_extensions,
)
from app.extensions.migrations import TABLE_PREFIX, is_core_object
from app.integrations.celery.core import create_celery

BACKEND_DIR = Path(__file__).resolve().parents[2]


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
        return [APIRouter()]


@dataclass
class MixedRoutersExtension(OWExtension):
    name: str = "mixed_routers"

    def routers(self) -> list[Any]:
        return [None, APIRouter()]


@dataclass
class NoneHooksExtension(OWExtension):
    name: str = "none_hooks"

    def beat_schedule(self) -> Any:
        return None

    def routers(self) -> Any:
        return None


@dataclass
class OtherContributingExtension(OWExtension):
    name: str = "other_contributing"

    def beat_schedule(self) -> dict[str, dict[str, Any]]:
        return {"contributing-job": {"task": "other.tasks.run", "schedule": 30.0}}


@dataclass
class CoreKeyExtension(OWExtension):
    name: str = "core_key"

    def beat_schedule(self) -> dict[str, dict[str, Any]]:
        return {
            "sync-all-users-periodic": {"task": "core_key.tasks.hijack", "schedule": 1.0},
            "core-key-own-job": {"task": "core_key.tasks.run", "schedule": 60.0},
        }


@dataclass
class MalformedBeatExtension(OWExtension):
    name: str = "malformed_beat"

    def beat_schedule(self) -> dict[str, Any]:
        return {
            "not-a-dict": None,
            "no-schedule": {"task": "malformed.tasks.run"},
            "unknown-key": {"task": "malformed.tasks.run", "schedule": 60.0, "interval": 5},
            "string-schedule": {"task": "malformed.tasks.run", "schedule": "every minute"},
            "no-task-name": {"task": None, "schedule": 60.0},
            "empty-task-name": {"task": "", "schedule": 60.0},
            "valid": {"task": "malformed.tasks.run", "schedule": 60.0, "kwargs": {"a": 1}},
        }


@dataclass
class ScheduleTypesExtension(OWExtension):
    name: str = "schedule_types"

    def beat_schedule(self) -> dict[str, dict[str, Any]]:
        return {
            "seconds": {"task": "types.tasks.run", "schedule": 60},
            "timedelta": {"task": "types.tasks.run", "schedule": timedelta(minutes=5)},
            "crontab": {"task": "types.tasks.run", "schedule": crontab(minute=0)},
        }


class PlainSubclassExtension(OWExtension):
    """Not a @dataclass: the inherited __init__ resets these to the base defaults."""

    name = "plain"
    requires_core = "<0.0.1"


class NotAnExtension:
    pass


def _extension_with_tasks(package: str) -> type[OWExtension]:
    @dataclass
    class TasksExtension(OWExtension):
        name: str = package
        celery_task_packages: list[str] = field(default_factory=lambda: [package])

    return TasksExtension


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


@pytest.fixture
def make_package(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Callable[..., str]]:
    """Create an importable package under tmp_path; `tasks` is the source of its tasks module."""
    monkeypatch.syspath_prepend(str(tmp_path))
    created: list[str] = []

    def make(name: str, tasks: str | None = None) -> str:
        package_dir = tmp_path / name
        package_dir.mkdir()
        (package_dir / "__init__.py").write_text("")
        if tasks is not None:
            (package_dir / "tasks.py").write_text(tasks)
        created.append(name)
        return name

    yield make
    for name in created:
        for module in [m for m in sys.modules if m == name or m.startswith(f"{name}.")]:
            sys.modules.pop(module, None)


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

    def test_plain_subclass_is_skipped(self, installed: Callable[..., None]) -> None:
        installed(FakeEntryPoint("plain", PlainSubclassExtension), FakeEntryPoint("compatible", CompatibleExtension))

        loaded = {e.name: e for e in get_extensions()}

        assert not loaded["plain"].active
        assert "@dataclass" in (loaded["plain"].error or "")
        assert [e.name for e in get_active_extensions()] == ["compatible"]

    def test_load_failure_is_reported_to_sentry(
        self, installed: Callable[..., None], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        reported: list[Exception] = []
        monkeypatch.setattr(extensions, "log_and_capture_error", lambda exc, *args, **kwargs: reported.append(exc))
        installed(FakeEntryPoint("broken", _broken))

        get_extensions()

        assert [type(exc) for exc in reported] == [ImportError]

    def test_importing_the_api_does_not_discover_extensions(self) -> None:
        # Discovery must wait until main.py has configured logging and Sentry; it is cached,
        # so a run triggered by an import would log its results before either exists.
        code = "import app.api, app.extensions; print(app.extensions.get_extensions.cache_info().currsize)"

        result = subprocess.run(
            [sys.executable, "-c", code], cwd=BACKEND_DIR, capture_output=True, text=True, check=True
        )

        assert result.stdout.strip().splitlines()[-1] == "0"


class TestTaskModules:
    def test_extension_whose_tasks_fail_to_import_is_skipped(
        self, installed: Callable[..., None], make_package: Callable[..., str]
    ) -> None:
        package = make_package("ow_ext_test_broken_tasks", tasks="import library_that_is_not_installed\n")
        installed(
            FakeEntryPoint("broken_tasks", _extension_with_tasks(package)),
            FakeEntryPoint("compatible", CompatibleExtension),
        )

        loaded = {e.name: e for e in get_extensions()}

        assert not loaded[package].active
        assert "library_that_is_not_installed" in (loaded[package].error or "")
        assert [e.name for e in get_active_extensions()] == ["compatible"]

    def test_missing_task_package_is_skipped(self, installed: Callable[..., None]) -> None:
        installed(FakeEntryPoint("missing", _extension_with_tasks("ow_ext_test_no_such_package")))

        [loaded] = get_extensions()

        assert not loaded.active
        assert "ow_ext_test_no_such_package" in (loaded.error or "")

    def test_package_without_tasks_module_stays_active(
        self, installed: Callable[..., None], make_package: Callable[..., str]
    ) -> None:
        package = make_package("ow_ext_test_no_tasks")
        installed(FakeEntryPoint("no_tasks", _extension_with_tasks(package)))

        [loaded] = get_extensions()

        assert loaded.active

    def test_broken_tasks_do_not_stop_celery_from_importing_its_modules(
        self, installed: Callable[..., None], make_package: Callable[..., str]
    ) -> None:
        package = make_package("ow_ext_test_celery_broken", tasks="import library_that_is_not_installed\n")
        installed(FakeEntryPoint("broken_tasks", _extension_with_tasks(package)))
        celery_app = create_celery()

        # Workers and beat run this on startup; an exception here stops them.
        celery_app.loader.import_default_modules()

        assert "app.integrations.celery.tasks.periodic_sync_task.sync_all_users" in celery_app.tasks


class TestHooks:
    def test_failing_hooks_do_not_affect_other_extensions(self, installed: Callable[..., None]) -> None:
        installed(
            FakeEntryPoint("faulty_hooks", FaultyHooksExtension),
            FakeEntryPoint("contributing", ContributingExtension),
        )

        assert list(collect_beat_schedule()) == ["contributing-job"]
        assert len(collect_routers()) == 1

    def test_hooks_returning_none_are_skipped(self, installed: Callable[..., None]) -> None:
        installed(FakeEntryPoint("none_hooks", NoneHooksExtension))

        assert collect_beat_schedule() == {}
        assert collect_routers() == []

    def test_values_that_are_not_routers_are_skipped(self, installed: Callable[..., None]) -> None:
        installed(FakeEntryPoint("mixed_routers", MixedRoutersExtension))

        assert [type(router) for router in collect_routers()] == [APIRouter]


class TestBeatSchedule:
    def test_entry_with_a_core_key_is_skipped(self, installed: Callable[..., None]) -> None:
        installed(FakeEntryPoint("core_key", CoreKeyExtension))

        schedule = create_celery().conf.beat_schedule

        assert (
            schedule["sync-all-users-periodic"]["task"]
            == "app.integrations.celery.tasks.periodic_sync_task.sync_all_users"
        )
        assert schedule["core-key-own-job"]["task"] == "core_key.tasks.run"

    def test_first_extension_keeps_a_shared_key(self, installed: Callable[..., None]) -> None:
        installed(
            FakeEntryPoint("contributing", ContributingExtension),
            FakeEntryPoint("other_contributing", OtherContributingExtension),
        )

        schedule = collect_beat_schedule()

        assert schedule == {"contributing-job": {"task": "contributing.tasks.run", "schedule": 60.0}}

    def test_malformed_entries_are_skipped(self, installed: Callable[..., None]) -> None:
        installed(FakeEntryPoint("malformed_beat", MalformedBeatExtension))

        assert list(collect_beat_schedule()) == ["valid"]

    def test_every_schedule_type_beat_accepts_is_kept(self, installed: Callable[..., None]) -> None:
        installed(FakeEntryPoint("schedule_types", ScheduleTypesExtension))

        assert list(collect_beat_schedule()) == ["seconds", "timedelta", "crontab"]


class TestDefaults:
    def test_base_extension_contributes_nothing(self) -> None:
        ext = OWExtension()

        assert ext.beat_schedule() == {}
        assert ext.routers() == []
        assert ext.celery_task_packages == []


_REVISION = """
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None


def upgrade():
    op.create_table({table!r}, sa.Column("id", sa.Integer, primary_key=True))
    {after}


def downgrade():
    op.drop_table({table!r})
"""

_ENV = """
import sqlalchemy as sa
from app.extensions.migrations import run_env

metadata = sa.MetaData()
sa.Table({table!r}, metadata, sa.Column("id", sa.Integer, primary_key=True))
run_env({name!r}, metadata)
"""


class TestMigrations:
    @pytest.fixture
    def migrated(
        self,
        installed: Callable[..., None],
        make_package: Callable[..., str],
        tmp_path: Path,
        engine: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> Iterator[Callable[..., LoadedExtension]]:
        """Install an extension `name` whose single revision creates `table`, then run discovery."""
        monkeypatch.setattr(extensions, "engine", engine)

        def load(name: str, table: str, after: str = "pass") -> LoadedExtension:
            migrations_dir = tmp_path / make_package(name) / "migrations"
            (migrations_dir / "versions").mkdir(parents=True)
            (migrations_dir / "env.py").write_text(_ENV.format(name=name, table=table))
            (migrations_dir / "versions" / "0001_init.py").write_text(_REVISION.format(table=table, after=after))
            ext = OWExtension(name=name, migrations=f"{name}:migrations")
            installed(FakeEntryPoint(name, lambda: ext))
            [loaded] = get_extensions()
            return loaded

        yield load
        with engine.begin() as connection:
            for table in sa_inspect(connection).get_table_names():
                if table.startswith(TABLE_PREFIX):
                    connection.execute(sa_text(f'DROP TABLE "{table}"'))

    def test_tables_are_migrated_before_the_extension_loads(
        self, migrated: Callable[..., LoadedExtension], engine: Any
    ) -> None:
        loaded = migrated("demo", "ext_demo_item")

        assert loaded.active
        tables = set(sa_inspect(engine).get_table_names())
        assert {"ext_demo_item", "ext_demo_alembic_version"} <= tables
        # Every process migrates on start; once at head the next run is a no-op.
        get_extensions.cache_clear()
        assert get_extensions()[0].active

    def test_failed_migration_disables_the_extension_and_rolls_back(
        self, migrated: Callable[..., LoadedExtension], engine: Any
    ) -> None:
        loaded = migrated("failing", "ext_failing_item", after='raise RuntimeError("boom")')

        assert not loaded.active
        assert "migrations failed: boom" in (loaded.error or "")
        assert not {"ext_failing_item", "ext_failing_alembic_version"} & set(sa_inspect(engine).get_table_names())

    def test_tables_outside_the_extension_prefix_disable_it(self, migrated: Callable[..., LoadedExtension]) -> None:
        loaded = migrated("sloppy", "item")

        assert not loaded.active
        assert "must start with 'ext_sloppy_'" in (loaded.error or "")

    def test_name_that_cannot_prefix_tables_disables_it(self, installed: Callable[..., None]) -> None:
        @dataclass
        class BadNameExtension(OWExtension):
            name: str = "Bad-Name"
            migrations: str = "bad_name:migrations"

        installed(FakeEntryPoint("bad", BadNameExtension))

        [loaded] = get_extensions()

        assert not loaded.active
        assert "lowercase identifier" in (loaded.error or "")

    def test_core_autogenerate_leaves_extension_tables_alone(
        self, migrated: Callable[..., LoadedExtension], engine: Any
    ) -> None:
        migrated("demo", "ext_demo_item")

        with engine.connect() as connection:
            context = MigrationContext.configure(connection, opts={"include_name": is_core_object})
            diff = compare_metadata(context, BaseDbModel.metadata)

        assert not [op for op in diff if TABLE_PREFIX in str(op)]

    @pytest.mark.parametrize(
        ("name", "type_", "included"),
        [("ext_demo_item", "table", False), ("ext_demo_alembic_version", "table", False), ("user", "table", True)],
    )
    def test_core_autogenerate_skips_extension_tables(self, name: str, type_: str, included: bool) -> None:
        assert is_core_object(name, type_, {}) is included
