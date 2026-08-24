# Backend Development Guide

This file extends the root AGENTS.md with backend-specific patterns.

## Tech Stack
- Python 3.13+
- FastAPI for API framework
- SQLAlchemy 2.0 for ORM
- PostgreSQL for database
- Alembic for migrations
- Celery + Redis for background jobs
- Ruff for linting/formatting

## Project Structure

```
app/
├── api/
│   └── routes/v1/       # API endpoints
├── models/              # SQLAlchemy models
├── schemas/             # Pydantic schemas
├── services/            # Business logic
│   └── providers/       # Wearable provider integrations
├── repositories/        # Data access layer
├── integrations/        # External services (Celery, Redis)
├── utils/               # Utilities and helpers
└── config.py            # Settings
migrations/              # Alembic migrations
scripts/                 # Utility scripts
```

## Common Patterns

### Creating New Endpoints

```python
# app/api/routes/v1/users.py
from uuid import UUID
from fastapi import APIRouter, status
from app.database import DbSession
from app.schemas.user import UserCreate, UserRead, UserUpdate
from app.services import ApiKeyDep, user_service

router = APIRouter()


@router.get("/users", response_model=list[UserRead])
def list_users(db: DbSession, _api_key: ApiKeyDep):
    """List all users."""
    return db.query(user_service.crud.model).all()


@router.post("/users", status_code=status.HTTP_201_CREATED, response_model=UserRead)
def create_user(payload: UserCreate, db: DbSession, _api_key: ApiKeyDep):
    """Create a new user."""
    return user_service.create(db, payload)
```

### Service Pattern

```python
# app/services/user_service.py
from logging import Logger, getLogger
from app.database import DbSession
from app.models import User
from app.repositories.user_repository import UserRepository
from app.schemas import UserCreate, UserCreateInternal
from app.services.services import AppService


class UserService(AppService[UserRepository, User, UserCreateInternal, UserUpdateInternal]):
    def __init__(self, log: Logger, **kwargs):
        super().__init__(crud_model=UserRepository, model=User, log=log, **kwargs)

    def create(self, db_session: DbSession, creator: UserCreate) -> User:
        """Create user with server-generated id and created_at."""
        internal_creator = UserCreateInternal(**creator.model_dump())
        return super().create(db_session, internal_creator)


# Instantiate as singleton
user_service = UserService(log=getLogger(__name__))
```

### Repository Pattern

```python
# app/repositories/user_repository.py
from datetime import datetime
from sqlalchemy import func
from app.database import DbSession
from app.repositories.repositories import CrudRepository


class UserRepository(CrudRepository[User, UserCreateInternal, UserUpdateInternal]):
    def get_count_in_range(self, db: DbSession, start: datetime, end: datetime) -> int:
        return (
            db.query(func.count(self.model.id))
            .filter(self.model.created_at >= start, self.model.created_at < end)
            .scalar()
            or 0
        )
```

### Database Models

```python
# app/models/user.py
from uuid import UUID
from sqlalchemy.orm import Mapped, relationship
from app.database import BaseDbModel
from app.mappings import PrimaryKey, datetime_tz, str_100


class User(BaseDbModel):
    id: Mapped[PrimaryKey[UUID]]
    created_at: Mapped[datetime_tz]
    first_name: Mapped[str_100 | None]
    last_name: Mapped[str_100 | None]
```

### Pydantic Schemas

```python
# app/schemas/user.py
from datetime import datetime, timezone
from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, Field


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    created_at: datetime
    first_name: str | None = None


class UserCreate(BaseModel):
    first_name: str | None = Field(None, max_length=100)


class UserCreateInternal(UserCreate):
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```

### Error Handling

**General rule:** Let exceptions propagate up to global handlers when possible.

```python
# In services - use raise_404=True
user = user_service.get(db, user_id, raise_404=True)

# In routes - raise HTTPException directly
from fastapi import HTTPException, status

if not user:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
```

**Handled exceptions in background tasks:**

When catching exceptions that are intentionally not propagated (e.g., to collect partial errors), use `log_and_capture_error` to ensure they're reported to Sentry:

```python
from app.utils.sentry_helpers import log_and_capture_error

# DON'T - error never reaches Sentry
try:
    process_item(item)
except Exception as e:
    logger.error(f"Failed to process: {e}")
    continue

# DO - error is logged AND captured in Sentry
try:
    process_item(item)
except Exception as e:
    log_and_capture_error(
        e, logger, "Failed to process item", extra={"item_id": item.id, "user_id": user_id, "error": str(e)}
    )
    continue
```

**When to use `log_and_capture_error`:**
- ✅ Celery tasks that catch exceptions and return error responses instead of failing
- ✅ Batch processing where you want to continue despite errors
- ✅ Multi-provider sync where one provider failure shouldn't stop others
- ❌ Don't use if exception is re-raised or allowed to propagate naturally

### Logging

**Default rule:** Use `log_structured` instead of raw `logger.info/warning/error/...`. Structured logs are emitted as single-line JSON, making them queryable by attribute (`@user_id:...`, `@action:...`) in Railway, GCP, Vercel, etc. This is the established standard in the codebase - prefer it even when editing an existing file that still uses the raw logger.

```python
from app.utils.structured_logging import log_structured

# DON'T - unstructured, not queryable by attribute
self.logger.warning(f"Failed to save {key} sample for user {user_id} at {recorded_at}: {e}")

# DO - structured, queryable
log_structured(
    self.logger,
    "warning",
    "Failed to save activity sample",
    provider=self.provider_name,
    action="save_activity_sample_failed",
    user_id=str(user_id),
    series=key,
    recorded_at=recorded_at,
    error=str(e),
)
```

- Pass the message as a stable, human-readable string and put the variable parts in `**attributes` (don't f-string them into the message).
- `trace_id` is injected automatically from context when not supplied.
- For handled exceptions in background tasks you still want in Sentry, use `log_and_capture_error` (see above) rather than plain `logger.error`. Keep its `message` stable there too and pass variables via `extra` - note that `extra` becomes Sentry event context, not queryable log attributes.

### Provider Strategy Pattern

See `docs/dev-guides/how-to-add-new-provider.mdx` for the full guide.

```python
# app/services/providers/garmin/strategy.py
class GarminStrategy(BaseProviderStrategy):
    @property
    def name(self) -> str:
        return "garmin"

    @property
    def api_base_url(self) -> str:
        return "https://apis.garmin.com"
```

## Database Migrations

Schema changes use Alembic:

```bash
make create_migration m="Add user table"  # Create
make migrate                               # Apply
make downgrade                             # Rollback
```

### Data migrations

One-off data corrections, backfills, or clean-ups that can't be expressed as a
zero-downtime Alembic migration live in `scripts/data_migrations/`. Each must be
idempotent and support a `--dry-run` flag, and its **module docstring is the source
of truth** for the rationale (the problem it fixes, what it changes, and any details
such as conflict handling) — put it there, not in the docs.

See `docs/dev-guides/data-migrations.mdx` for how to run them and how they're wired
into startup.

## Code Style
- Line length: 120 characters
- Type hints required on all functions
- Imports sorted by isort
- All imports at module level — never inside functions or methods
- PEP 8 naming conventions

## Commands

```bash
cd backend

# Lint and format (run after changes)
uv run ruff check . --fix && uv run ruff format .

# Type check
uv run ty check .

# Run tests
uv run pytest -v --cov=app
```

Use `uv add <package-name>` to add new dependencies (automatically updates pyproject.toml, lockfile, and venv).
Run `uv run ruff check . --fix && uv run ruff format .` after making changes.

## Detailed Layer Rules

### Models Layer (`app/models/`)

Models define SQL table structure using SQLAlchemy. Each model represents one table.

**Required files:**
- `app/database.py` - Contains `BaseDbModel` class with `type_annotation_map`, custom Python to SQL type mappings
- `app/mappings.py` - Defines custom Python types with `Annotated` syntax, relationship types and foreign keys

**Model structure:**
```python
from sqlalchemy.orm import Mapped
from app.database import BaseDbModel
from app.mappings import PrimaryKey, Unique, datetime_tz, email, OneToMany, ManyToOne, FKUser


class User(BaseDbModel):
    id: Mapped[PrimaryKey[UUID]]
    email: Mapped[Unique[email]]
    created_at: Mapped[datetime_tz]
    workouts: Mapped[OneToMany["Workout"]]


class Workout(BaseDbModel):
    user_id: Mapped[FKUser]
    user: Mapped[ManyToOne["User"]]
```

**Custom types:**
- `PrimaryKey[T]`, `Unique[T]`, `UniqueIndex[T]`, `Indexed[T]` - Constraints with generic type
- `str_10`, `str_50`, `str_100`, `str_255` - String length limits
- `email`, `numeric_10_2`, `numeric_15_5`, `datetime_tz` - Specialized types
- `FKUser` - Pre-defined foreign key relationships
- `OneToMany[T]`, `ManyToOne[T]` - Relationship types

### Repositories Layer (`app/repositories/`)

Repositories handle **ONLY** database operations. Input/output must be SQLAlchemy models only (no Pydantic schemas).

**CRUD repository:**
```python
from app.repositories.repositories import CrudRepository


class UserRepository(CrudRepository[User, UserCreate, UserUpdate]):
    def __init__(self, model: type[User]):
        super().__init__(model)

    def get_by_email(self, db_session: DbSession, email: str) -> User | None:
        return db_session.query(self.model).filter(self.model.email == email).one_or_none()
```

**Flow:** database → SQLAlchemy model → repository → SQLAlchemy model → service

### Schemas Layer (`app/schemas/`)

Schemas define API data format through Pydantic models. Handle validation and serialization.

- Use **Pydantic 2+ syntax** exclusively
- Implement validation in schemas, not database models
- Set default values in schemas to avoid database-level defaults
- `response_model` automatically converts SQLAlchemy to Pydantic

### Services Layer (`app/services/`)

Services contain business logic. They **NEVER** perform database operations directly.

**Type annotations are mandatory for all parameters and return types.**

```python
from app.services.services import AppService
from app.utils.exceptions import handle_exceptions


class UserService(AppService[UserRepository, User, UserCreate, UserUpdate]):
    def __init__(self, crud_model: type[UserRepository], model: type[User], log: Logger, **kwargs):
        super().__init__(crud_model, model, log, **kwargs)


# Mixin pattern for additional functionality
class ActivityMixin:
    def __init__(self, activity_repository: ActivityRepository = Depends(), **kwargs):
        self.activity_repository = activity_repository
        super().__init__(**kwargs)

    @handle_exceptions
    def is_user_active(self: "UserService", object_id: UUID) -> bool:
        return self.activity_repository.is_user_active(object_id)
```

**Error handling:** Use `@handle_exceptions` decorator from `app.utils.exceptions`

**Flow:** repository → SQLAlchemy model → service → SQLAlchemy model → route

### Routes Layer (`app/api/routes/`)

**Directory structure:**
```
app/api/routes/
├── __init__.py          # Head router (imports all versions)
├── v1/                  # API version 1
│   ├── __init__.py      # Version router (includes all v1 routes)
│   └── example.py       # Specific routes
```

**Router hierarchy:**
1. Module routers - `router = APIRouter()` without prefixes or tags
2. Version router (`v1/__init__.py`) - Includes module routers with tags (singular + kebab-case), NO prefix
3. Head router (`routes/__init__.py`) - Includes version routers with version prefix from settings
4. Main router (`main.py`) - Includes head_router, NO prefix

**Route implementation:**
- Use `@router.method()` decorator with HTTP method and path
- Add `response_model` (Pydantic) and `status_code` (fastapi.status)
- Define functions as `async` by default
- Use **kebab-case** for paths: `/heart-rate`, `/import-data`
- Keep route code minimal, delegate to services
- **Never call repositories directly from routes** - always go through a service layer
- **No trailing slashes:** Use `""` (empty string) instead of `"/"` for root routes on prefixed routers. A `"/"` path creates a trailing-slash canonical URL, causing FastAPI 307 redirects that break behind HTTPS reverse proxies.

**Flow:**
- Request: request → main.py → head_router → version_router → router → endpoint → service
- Response: service → response_model validation → router → version_router → head_router → main.py → client

## Verifying Changes

When asked or when you consider it appropriate, you can verify changes in several ways:

### API Testing
```bash
# Test endpoints with curl (app runs on localhost:8000)
curl -X GET http://localhost:8000/api/v1/endpoint
curl -X POST http://localhost:8000/api/v1/endpoint -H "Content-Type: application/json" -d '{"key": "value"}'
```

### Database Verification
```bash
# Connect to PostgreSQL
docker exec -it postgres__open-wearables psql -U open-wearables -d open-wearables

# Example queries
SELECT * FROM table_name LIMIT 5;
\dt  # list tables
```

### Logs
```bash
docker compose logs -f app          # API logs
docker compose logs -f celery-worker # Worker logs
```
