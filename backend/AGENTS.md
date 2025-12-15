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
async def list_users(db: DbSession, _api_key: ApiKeyDep):
    """List all users."""
    return db.query(user_service.crud.model).all()

@router.post("/users", status_code=status.HTTP_201_CREATED, response_model=UserRead)
async def create_user(payload: UserCreate, db: DbSession, _api_key: ApiKeyDep):
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
            .scalar() or 0
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

```python
# In services - use raise_404=True
user = user_service.get(db, user_id, raise_404=True)

# In routes - raise HTTPException directly
from fastapi import HTTPException, status

if not user:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
```

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

```bash
make create_migration m="Add user table"  # Create
make migrate                               # Apply
make downgrade                             # Rollback
```

## Code Style
- Line length: 120 characters
- Type hints required on all functions
- Imports sorted by isort
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

Run `uv run ruff check . --fix && uv run ruff format .` after making changes.
