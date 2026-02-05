---
name: code-review
description: Review code changes for compliance with project conventions - Pydantic v2 syntax, layer separation (repositories vs services), type hints
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash(git *)
---

# Code Review

Review the code changes for compliance with project conventions defined in AGENTS.md files.

## Instructions

1. **Identify changed files** - Determine what to review:
   - If on a feature branch: `git diff main...HEAD` to see all changes vs main
   - If reviewing staged changes: `git diff --cached`
   - If user specifies files in `$ARGUMENTS`: review those directly

   To list only changed file paths: `git diff main...HEAD --name-only`

2. **Read and check each changed file** against the relevant checklist below
3. **Report violations** with specific line numbers and fix suggestions
4. **Praise compliant code** briefly when patterns are followed correctly

---

## Backend Checklist (Python files in `backend/`)

### Pydantic v2 Syntax (CRITICAL)

Pydantic v1 syntax is **DEPRECATED**. Always use v2 patterns:

| Deprecated (v1) | Required (v2) |
|-----------------|---------------|
| `class Config:` inner class | `model_config = ConfigDict(...)` |
| `orm_mode = True` | `from_attributes=True` in ConfigDict |
| `@validator` | `@field_validator` |
| `@root_validator` | `@model_validator` |
| `schema_extra` | `json_schema_extra` |
| `.dict()` | `.model_dump()` |
| `.json()` | `.model_dump_json()` |
| `.parse_obj()` | `.model_validate()` |
| `.parse_raw()` | `.model_validate_json()` |
| `Field(regex=...)` | `Field(pattern=...)` |

**Correct example:**
```python
from pydantic import BaseModel, ConfigDict, Field, field_validator

class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str | None = None
    tags: list[str] = Field(default_factory=list)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str | None) -> str | None:
        if v and "@" not in v:
            raise ValueError("Invalid email")
        return v
```

### Layer Separation (CRITICAL)

#### Repositories (`app/repositories/`)
- **ONLY** database operations (queries, inserts, updates, deletes)
- Input/output: SQLAlchemy models only, **NEVER Pydantic schemas**
- **NO** business logic, validation, or external API calls
- Methods should be simple, focused CRUD operations

**Correct:**
```python
class UserRepository(CrudRepository[User, UserCreate, UserUpdate]):
    def get_by_email(self, db: DbSession, email: str) -> User | None:
        return db.query(self.model).filter(self.model.email == email).one_or_none()

    def get_active_users(self, db: DbSession) -> list[User]:
        return db.query(self.model).filter(self.model.is_active == True).all()
```

#### Services (`app/services/`)
- Contains **ALL** business logic
- **NEVER** performs database operations directly (use repositories)
- Coordinates between repositories, external APIs, and other services
- Handles validation beyond Pydantic schema validation and error handling

**Correct:**
```python
class UserService(AppService[UserRepository, User, UserCreate, UserUpdate]):
    def create_with_welcome_email(self, db: DbSession, data: UserCreate) -> User:
        user = self.crud.create(db, data)  # Delegates to repository
        email_service.send_welcome(user.email)  # Business logic here
        return user

    def get_premium_users_with_discount(self, db: DbSession) -> list[UserWithDiscount]:
        users = self.crud.get_premium(db)  # Repository handles query
        return [self._apply_discount(u) for u in users]  # Logic in service
```

### Modern Python Syntax

Use modern Python 3.10+ and 3.12+ syntax:

| Deprecated | Modern |
|------------|--------|
| `Optional[X]` | `X \| None` |
| `Union[X, Y]` | `X \| Y` |
| `List[X]` | `list[X]` |
| `Dict[K, V]` | `dict[K, V]` |
| `Tuple[X, ...]` | `tuple[X, ...]` |
| `Set[X]` | `set[X]` |

**Generics (Python 3.12+):**
```python
# Deprecated - using TypeVar
from typing import TypeVar, Generic

T = TypeVar("T")

class Repository(Generic[T]):
    def get(self, id: int) -> T: ...

# Modern - using type parameter syntax
class Repository[T]:
    def get(self, id: int) -> T: ...

# Function generics
def first[T](items: list[T]) -> T | None:
    return items[0] if items else None
```

**Type hints are required** - all functions must have type annotations:
```python
# Correct
def process_user(db: DbSession, user_id: UUID, active: bool = True) -> User | None:

# Incorrect
def process_user(db, user_id, active=True):
```

### Error Handling

- Use `raise_404=True` in service methods instead of manual checks
- Let exceptions propagate to global handlers
- Use `log_and_capture_error` for caught exceptions in background tasks

---

## Review Output Format

For each violation found, report:

```
### [VIOLATION] {Category}

**File:** `path/to/file.py:{line_number}`
**Issue:** {Brief description}

**Current code:**
```python
{offending code}
```

**Should be:**
```python
{corrected code}
```
```

At the end, provide a summary:
- Total violations found
- Breakdown by category (Pydantic v2, Layer Separation, Type Hints, etc.)
- Overall assessment (PASS / NEEDS FIXES)
