# Extensions

Local checkouts of add-on modules for development. Every subdirectory with a
`pyproject.toml` is installed in editable mode when the backend containers start
(`backend/scripts/start/install_extensions.sh`), and its entry point under
`open_wearables.extensions` is picked up by the core.

```bash
git clone <extension repo> extensions/<name>
docker compose up -d
```

With `ENVIRONMENT=local` the API reloads on its own when an extension's code changes; Celery
does not:

```bash
docker compose restart celery-worker celery-beat
```

To remove an extension, delete its directory and restart the backend containers
(`docker compose restart app celery-worker celery-beat`), which uninstalls it. A checkout
that fails to install is skipped with a warning instead of stopping the backend.

Everything in this directory except this README is git-ignored.

## Database tables

An extension keeps its own Alembic history, separate from the core's. Its tables must start
with `ext_<name>_` (its version table is `ext_<name>_alembic_version`), and they must not have
foreign keys to core tables: store a core id such as `user_id` as a plain UUID column.

```python
# my_extension/extension.py
@dataclass
class MyExtension(OWExtension):
    name: str = "my_extension"
    migrations: str = "my_extension:migrations"
```

```python
# my_extension/migrations/env.py
from app.extensions.migrations import run_env
from my_extension.models import Base

run_env("my_extension", Base.metadata)
```

Every backend process migrates the extension to head before loading it, so there is no
separate migration step. If a migration fails, it is rolled back and the extension stays
disabled until the next start. The core's autogenerate ignores `ext_` tables, so a core
migration never creates or drops them.

## Reacting to new data

Instead of scanning every user on a beat schedule, an extension can have a Celery task queued
when a user's sync brings new data (a completed sync with status `success` or `partial`):

```python
@dataclass
class MyExtension(OWExtension):
    def event_handlers(self) -> dict[str, str]:
        return {"sync.completed": "my_extension.tasks.recompute_user"}
```

The task is called with `user_id` (a string) only, and loads what it needs itself. A user's
syncs are coalesced: the first opens a window of `EXTENSION_EVENT_DEBOUNCE_SECONDS` (5 min by
default) and all syncs inside it end in a single task, queued by a sweep every
`EXTENSION_EVENT_SWEEP_INTERVAL_SECONDS`. Delivery is at least once, so the task must be safe to
run twice for the same user.

## API endpoints

Routers from `routers()` are mounted under `/api/v1/ext/<name>` and require the same
authentication as the core API (an API key or a dashboard token), so an endpoint is never public
by accident and never collides with a core path. A router that must be public, such as a
receiver for a third party's webhooks, goes in `public_routers()` instead:

```python
@dataclass
class MyExtension(OWExtension):
    name: str = "my_extension"

    def routers(self) -> list[APIRouter]:
        return [reports_router]  # GET /api/v1/ext/my_extension/reports, authenticated

    def public_routers(self) -> list[APIRouter]:
        return [webhook_router]  # POST /api/v1/ext/my_extension/webhook, public
```

`name` must be a lowercase identifier (`[a-z][a-z0-9_]*`), since it prefixes the extension's
URLs and tables; an extension with any other name is not loaded.

