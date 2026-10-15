import subprocess
import sys
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from celery.schedules import crontab
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import text as sa_text
from sqlalchemy.orm import Session

import app.extensions as extensions
from app.database import BaseDbModel
from app.extensions import (
    LoadedExtension,
    OWExtension,
    collect_beat_schedule,
    collect_event_handlers,
    events,
    get_active_extensions,
    get_extensions,
    mount_routers,
)
from app.extensions.migrations import TABLE_PREFIX, is_core_object
from app.integrations.celery.core import create_celery
from app.integrations.redis_client import get_redis_client
from app.schemas.sync_status import SyncSource, SyncStage, SyncStatus, SyncStatusEvent
from app.services.sync_status_service import emit
from tests.factories import ApiKeyFactory
from tests.utils import api_key_headers

BACKEND_DIR = Path(__file__).resolve().parents[2]


def _ping_router() -> APIRouter:
    router = APIRouter()
    router.add_api_route("/ping", lambda: {"pong": True})
    return router


def _mounted_paths() -> list[str]:
    app = FastAPI()
    mount_routers(app, "/api/v1", Depends(lambda: None))
    return [path for path in app.openapi()["paths"] if path.startswith("/api/v1/ext/")]


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

    def event_handlers(self) -> dict[str, str]:
        raise RuntimeError("boom")


@dataclass
class ContributingExtension(OWExtension):
    name: str = "contributing"

    def beat_schedule(self) -> dict[str, dict[str, Any]]:
        return {"contributing-job": {"task": "contributing.tasks.run", "schedule": 60.0}}

    def routers(self) -> list[Any]:
        return [_ping_router()]


@dataclass
class MixedRoutersExtension(OWExtension):
    name: str = "mixed_routers"

    def routers(self) -> list[Any]:
        return [None, _ping_router()]


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
    events.register({})


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

    @pytest.mark.parametrize("name", ["", "Bad-Name", "has space", "1st"])
    def test_name_that_cannot_prefix_urls_and_tables_is_skipped(
        self, installed: Callable[..., None], name: str
    ) -> None:
        installed(FakeEntryPoint("misnamed", lambda: OWExtension(name=name)))

        [loaded] = get_extensions()

        assert not loaded.active
        assert "lowercase identifier" in (loaded.error or "")

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
        assert _mounted_paths() == ["/api/v1/ext/contributing/ping"]

    def test_hooks_returning_none_are_skipped(self, installed: Callable[..., None]) -> None:
        installed(FakeEntryPoint("none_hooks", NoneHooksExtension))

        assert collect_beat_schedule() == {}
        assert _mounted_paths() == []

    def test_values_that_are_not_routers_are_skipped(self, installed: Callable[..., None]) -> None:
        installed(FakeEntryPoint("mixed_routers", MixedRoutersExtension))

        assert _mounted_paths() == ["/api/v1/ext/mixed_routers/ping"]


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
        assert ext.event_handlers() == {}


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


@dataclass
class ListeningExtension(OWExtension):
    name: str = "listening"

    def event_handlers(self) -> dict[str, Any]:
        return {"sync.completed": "listening.tasks.recompute", "user.deleted": "listening.tasks.forget", "": None}


def _sync_event(stage: SyncStage, status: SyncStatus, user_id: str | None = None) -> SyncStatusEvent:
    return SyncStatusEvent(
        run_id=f"run_{uuid4().hex}",
        user_id=user_id or str(uuid4()),
        provider="garmin",
        source=SyncSource.WEBHOOK,
        stage=stage,
        status=status,
    )


def _pending() -> dict[str, float]:
    return dict(get_redis_client().zrange(events.pending_key(events.SYNC_COMPLETED), 0, -1, withscores=True))


class TestEvents:
    @pytest.fixture
    def send_task(self, monkeypatch: pytest.MonkeyPatch) -> MagicMock:
        app = MagicMock()
        monkeypatch.setattr(events, "current_app", app)
        return app.send_task

    def test_handlers_are_collected_and_bad_ones_skipped(self, installed: Callable[..., None]) -> None:
        installed(FakeEntryPoint("listening", ListeningExtension), FakeEntryPoint("faulty", FaultyHooksExtension))

        assert collect_event_handlers() == {"sync.completed": ("listening.tasks.recompute",)}

    @pytest.mark.parametrize(
        ("stage", "status", "pending"),
        [
            (SyncStage.COMPLETED, SyncStatus.SUCCESS, True),
            (SyncStage.COMPLETED, SyncStatus.PARTIAL, True),
            (SyncStage.COMPLETED, SyncStatus.SKIPPED, False),
            (SyncStage.FAILED, SyncStatus.FAILED, False),
            (SyncStage.STARTED, SyncStatus.IN_PROGRESS, False),
        ],
    )
    def test_only_a_sync_that_brought_data_marks_the_user(
        self, installed: Callable[..., None], stage: SyncStage, status: SyncStatus, pending: bool
    ) -> None:
        installed()
        events.register({events.SYNC_COMPLETED: ("listening.tasks.recompute",)})
        event = _sync_event(stage, status)

        emit(event)

        assert (str(event.user_id) in _pending()) is pending

    def test_nothing_is_recorded_without_handlers(self, installed: Callable[..., None]) -> None:
        installed()

        emit(_sync_event(SyncStage.COMPLETED, SyncStatus.SUCCESS))

        assert _pending() == {}

    def test_later_syncs_ride_on_the_first_window(self, installed: Callable[..., None]) -> None:
        installed()
        events.register({events.SYNC_COMPLETED: ("listening.tasks.recompute",)})
        user_id = str(uuid4())

        emit(_sync_event(SyncStage.COMPLETED, SyncStatus.SUCCESS, user_id))
        first = _pending()[user_id]
        emit(_sync_event(SyncStage.COMPLETED, SyncStatus.SUCCESS, user_id))

        assert _pending() == {user_id: first}

    def test_settled_users_are_queued_once_to_every_handler(
        self, installed: Callable[..., None], send_task: MagicMock
    ) -> None:
        installed()
        events.register({events.SYNC_COMPLETED: ("a.tasks.run", "b.tasks.run")})
        get_redis_client().zadd(events.pending_key(events.SYNC_COMPLETED), {"settled": 1, "recent": 9e12})

        dispatched = events.dispatch_due(get_redis_client(), debounce_seconds=300)

        assert dispatched == 1
        assert [c.args[0] for c in send_task.call_args_list] == ["a.tasks.run", "b.tasks.run"]
        assert {c.kwargs["kwargs"]["user_id"] for c in send_task.call_args_list} == {"settled"}
        assert list(_pending()) == ["recent"]

    def test_sweep_drains_in_batches(
        self, installed: Callable[..., None], send_task: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        installed()
        monkeypatch.setattr(events, "_SWEEP_BATCH", 2)
        events.register({events.SYNC_COMPLETED: ("a.tasks.run",)})
        get_redis_client().zadd(events.pending_key(events.SYNC_COMPLETED), {f"user{i}": i for i in range(5)})

        assert events.dispatch_due(get_redis_client(), debounce_seconds=300) == 5
        assert send_task.call_count == 5
        assert _pending() == {}

    def test_users_not_queued_go_back_when_the_broker_fails(
        self, installed: Callable[..., None], send_task: MagicMock
    ) -> None:
        installed()
        events.register({events.SYNC_COMPLETED: ("a.tasks.run",)})
        get_redis_client().zadd(events.pending_key(events.SYNC_COMPLETED), {"first": 1, "second": 2, "third": 3})
        send_task.side_effect = [None, ConnectionError("broker down")]

        with pytest.raises(ConnectionError):
            events.dispatch_due(get_redis_client(), debounce_seconds=300)

        assert _pending() == {"second": 0, "third": 0}

    def test_sweep_is_scheduled_only_when_an_extension_listens(self, installed: Callable[..., None]) -> None:
        installed()
        assert "dispatch-extension-events" not in create_celery().conf.beat_schedule

        installed(FakeEntryPoint("listening", ListeningExtension))
        entry = create_celery().conf.beat_schedule["dispatch-extension-events"]

        assert entry["task"] == "app.integrations.celery.tasks.extension_events_task.dispatch_extension_events"
        assert events.subscribed(events.SYNC_COMPLETED)


class TestMetaEndpoint:
    def test_lists_every_installed_extension_with_its_state(
        self, installed: Callable[..., None], client: TestClient, db: Session
    ) -> None:
        installed(
            FakeEntryPoint("compatible", CompatibleExtension),
            FakeEntryPoint("incompatible", IncompatibleExtension),
            FakeEntryPoint("broken", _broken),
        )

        response = client.get("/api/v1/meta/extensions", headers=api_key_headers(ApiKeyFactory().plain_key))

        assert response.status_code == 200
        body = response.json()
        assert body["core_version"]
        by_name = {e["name"]: e for e in body["extensions"]}
        assert by_name["compatible"] == {
            "name": "compatible",
            "display_name": "",
            "version": "1.0.0",
            "requires_core": ">=0",
            "active": True,
            "error": None,
        }
        assert not by_name["incompatible"]["active"]
        assert "requires core <0.0.1" in by_name["incompatible"]["error"]
        assert by_name["broken"]["version"] == ""
        assert "missing dependency" in by_name["broken"]["error"]

    def test_requires_authentication(self, client: TestClient) -> None:
        assert client.get("/api/v1/meta/extensions").status_code == 401


@dataclass
class RoutedExtension(OWExtension):
    name: str = "routed"
    display_name: str = "Routed"

    def routers(self) -> list[Any]:
        router = _ping_router()
        router.add_api_route("/users/{user_id}/summaries/activity", lambda user_id: {"ext": user_id})
        return [router]

    def public_routers(self) -> list[Any]:
        router = APIRouter()
        router.add_api_route("/webhook", lambda: {"received": True}, methods=["POST"])
        return [router]


class TestRouters:
    @pytest.fixture
    def app(self, installed: Callable[..., None]) -> FastAPI:
        def auth(request: Request) -> None:
            if request.headers.get("X-Test-Auth") != "ok":
                raise HTTPException(status_code=401)

        installed(FakeEntryPoint("routed", RoutedExtension))
        app = FastAPI()
        mount_routers(app, "/api/v1", Depends(auth))
        return app

    def test_routers_require_auth(self, app: FastAPI) -> None:
        client = TestClient(app)

        assert client.get("/api/v1/ext/routed/ping").status_code == 401
        assert client.get("/api/v1/ext/routed/ping", headers={"X-Test-Auth": "ok"}).json() == {"pong": True}

    def test_public_routers_skip_auth(self, app: FastAPI) -> None:
        assert TestClient(app).post("/api/v1/ext/routed/webhook").json() == {"received": True}

    def test_a_core_path_lands_under_the_extension_prefix(self, app: FastAPI) -> None:
        paths = set(app.openapi()["paths"])

        assert "/api/v1/ext/routed/users/{user_id}/summaries/activity" in paths
        assert "/api/v1/users/{user_id}/summaries/activity" not in paths

    def test_endpoints_are_grouped_under_the_extension_tag(self, app: FastAPI) -> None:
        tags = {tag for op in app.openapi()["paths"].values() for spec in op.values() for tag in spec["tags"]}

        assert tags == {"Extension: Routed"}
