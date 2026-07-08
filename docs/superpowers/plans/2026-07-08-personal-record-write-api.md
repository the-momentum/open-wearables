# Personal Record Write API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an adapter-driven write API for `public.personal_record` so the .NET adapter can populate `birth_date` (and `gender`), letting OW compute HR-zone max HR as `220 − age` at ingest instead of the 190 fallback.

**Architecture:** Follow OW's existing `users.py` → service → repository layering. A new `PersonalRecordRepository` adds a `get_by_user_id` lookup; a new `personal_record_service` performs an idempotent upsert keyed on the 1:1 `user_id`; a new `personal_records.py` route exposes `PUT`/`GET /users/{user_id}/personal-record` behind API-key auth. No new dependencies, no migration (the table already exists).

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy (sync `Session`), Pydantic v2, pytest, `uv`.

## Global Constraints

- Working directory for all commands: `backend/`. Test runner: `cd backend && uv run pytest`.
- Branch: `feat/personal-record-write-api` (already checked out, off `release/0.6.2-syn`). Do NOT push, pull, or rebase — commit locally only.
- Auth dependency for both endpoints: `ApiKeyDep` (header `X-Open-Wearables-API-Key`), matching `POST /users`.
- Route paths are exactly `/users/{user_id}/personal-record` (singular, hyphenated). The `/api/v1` prefix is applied by the app; tests use the `api_v1_prefix` fixture.
- OW remaps `RequestValidationError` → **HTTP 400** (`app/main.py:70` → `app/utils/exceptions.py:84`). Body-validation failures assert **400**, NOT 422. (This corrects the spec, which said 422.)
- `ResourceNotFoundError` (`app/utils/exceptions.py:21`) → HTTP 404.
- `sex` is intentionally excluded from the API (dead column).
- One commit per task.

---

### Task 1: Schemas — upsert body with validator + ORM-serializable response

**Files:**
- Modify: `backend/app/schemas/model_crud/activities/personal_record.py`
- Modify: `backend/app/schemas/model_crud/activities/__init__.py`
- Test: `backend/tests/schemas/test_personal_record_schema.py` (create)

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `PersonalRecordUpsert(PersonalRecordBase)` — body schema; fields `birth_date: date | None`, `gender: Literal[...] | None`; rejects future / implausibly-old `birth_date`.
  - `PersonalRecordCreate(PersonalRecordBase)` — unchanged; fields `id: UUID`, `user_id: UUID`, plus base fields (repository create schema).
  - `PersonalRecordResponse(PersonalRecordBase)` — now `model_config = ConfigDict(from_attributes=True)`; fields `id: UUID`, `user_id: UUID`.
  - `MAX_HUMAN_AGE_YEARS = 120`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/schemas/test_personal_record_schema.py`:

```python
from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from app.schemas.model_crud.activities import PersonalRecordUpsert


def test_upsert_accepts_valid_birth_date_and_gender():
    schema = PersonalRecordUpsert(birth_date=date(1990, 5, 17), gender="male")
    assert schema.birth_date == date(1990, 5, 17)
    assert schema.gender == "male"


def test_upsert_allows_all_fields_none():
    schema = PersonalRecordUpsert()
    assert schema.birth_date is None
    assert schema.gender is None


def test_upsert_rejects_future_birth_date():
    future = date.today() + timedelta(days=1)
    with pytest.raises(ValidationError):
        PersonalRecordUpsert(birth_date=future)


def test_upsert_rejects_implausibly_old_birth_date():
    with pytest.raises(ValidationError):
        PersonalRecordUpsert(birth_date=date(date.today().year - 121, 1, 1))


def test_upsert_rejects_unknown_gender():
    with pytest.raises(ValidationError):
        PersonalRecordUpsert(gender="unknown")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/schemas/test_personal_record_schema.py -v`
Expected: FAIL — `ImportError: cannot import name 'PersonalRecordUpsert'`.

- [ ] **Step 3: Write minimal implementation**

Replace the full contents of `backend/app/schemas/model_crud/activities/personal_record.py` with:

```python
from __future__ import annotations

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_HUMAN_AGE_YEARS = 120


class PersonalRecordBase(BaseModel):
    birth_date: date | None = Field(None, description="Birth date of the user")
    gender: Literal["female", "male", "nonbinary", "other"] | None = Field(
        None,
        description="Optional self-reported gender",
    )


class PersonalRecordCreate(PersonalRecordBase):
    id: UUID
    user_id: UUID


class PersonalRecordUpdate(PersonalRecordBase): ...


class PersonalRecordUpsert(PersonalRecordBase):
    """Write body for the upsert endpoint (user_id comes from the path, id is server-generated)."""

    @field_validator("birth_date")
    @classmethod
    def _birth_date_is_plausible(cls, value: date | None) -> date | None:
        if value is None:
            return value
        today = date.today()
        if value > today:
            raise ValueError("birth_date cannot be in the future")
        if value.year < today.year - MAX_HUMAN_AGE_YEARS:
            raise ValueError("birth_date is implausibly old")
        return value


class PersonalRecordResponse(PersonalRecordBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
```

Then add `PersonalRecordUpsert` to `backend/app/schemas/model_crud/activities/__init__.py`. In the existing `from .personal_record import (...)` block add the line `PersonalRecordUpsert,` alongside the other `PersonalRecord*` imports, and add `"PersonalRecordUpsert",` to `__all__` next to `"PersonalRecordUpdate"`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/schemas/test_personal_record_schema.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/model_crud/activities/personal_record.py backend/app/schemas/model_crud/activities/__init__.py backend/tests/schemas/test_personal_record_schema.py
git commit -m "feat(personal-record): upsert schema with birth_date validator + ORM response"
```

---

### Task 2: Repository — `get_by_user_id`

**Files:**
- Create: `backend/app/repositories/personal_record_repository.py`
- Test: `backend/tests/repositories/test_personal_record_repository.py` (create)

**Interfaces:**
- Consumes: `PersonalRecordCreate`, `PersonalRecordUpsert` (Task 1); `CrudRepository` (`app/repositories/repositories.py`); `PersonalRecord` model (`app/models`).
- Produces: `PersonalRecordRepository(model)` with `get_by_user_id(db_session, user_id: UUID) -> PersonalRecord | None`, plus inherited `create`/`update` from `CrudRepository`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/repositories/test_personal_record_repository.py`:

```python
from datetime import date
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models import PersonalRecord
from app.repositories.personal_record_repository import PersonalRecordRepository
from tests.factories import UserFactory


def test_get_by_user_id_returns_none_when_absent(db: Session):
    repo = PersonalRecordRepository(PersonalRecord)
    assert repo.get_by_user_id(db, uuid4()) is None


def test_get_by_user_id_returns_row_when_present(db: Session):
    user = UserFactory()
    record = PersonalRecord(id=uuid4(), user_id=user.id, birth_date=date(1988, 3, 1))
    db.add(record)
    db.commit()

    repo = PersonalRecordRepository(PersonalRecord)
    found = repo.get_by_user_id(db, user.id)
    assert found is not None
    assert found.user_id == user.id
    assert found.birth_date == date(1988, 3, 1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/repositories/test_personal_record_repository.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.repositories.personal_record_repository'`.

- [ ] **Step 3: Write minimal implementation**

Create `backend/app/repositories/personal_record_repository.py`:

```python
from uuid import UUID

from app.database import DbSession
from app.models import PersonalRecord
from app.repositories.repositories import CrudRepository
from app.schemas.model_crud.activities import PersonalRecordCreate, PersonalRecordUpsert


class PersonalRecordRepository(CrudRepository[PersonalRecord, PersonalRecordCreate, PersonalRecordUpsert]):
    def __init__(self, model: type[PersonalRecord]):
        super().__init__(model)

    def get_by_user_id(self, db_session: DbSession, user_id: UUID) -> PersonalRecord | None:
        return db_session.query(self.model).filter(self.model.user_id == user_id).one_or_none()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/repositories/test_personal_record_repository.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/repositories/personal_record_repository.py backend/tests/repositories/test_personal_record_repository.py
git commit -m "feat(personal-record): repository with get_by_user_id lookup"
```

---

### Task 3: Service — idempotent upsert + get_for_user

**Files:**
- Create: `backend/app/services/personal_record_service.py`
- Modify: `backend/app/services/__init__.py`
- Test: `backend/tests/services/test_personal_record_service.py` (create)

**Interfaces:**
- Consumes: `PersonalRecordRepository` (Task 2); `PersonalRecordCreate`, `PersonalRecordUpsert` (Task 1); `AppService` (`app/services/services.py`); `user_service` (`app/services/user_service.py`); `ResourceNotFoundError` (`app/utils/exceptions.py`); `PersonalRecord` model.
- Produces:
  - `personal_record_service` singleton.
  - `personal_record_service.upsert(db, user_id: UUID, payload: PersonalRecordUpsert) -> tuple[PersonalRecord, bool]` — bool is `True` when a row was created, `False` when updated. Raises `ResourceNotFoundError` if the user does not exist.
  - `personal_record_service.get_for_user(db, user_id: UUID, raise_404: bool = False) -> PersonalRecord | None`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/services/test_personal_record_service.py`:

```python
from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.schemas.model_crud.activities import PersonalRecordUpsert
from app.services.personal_record_service import personal_record_service
from app.utils.exceptions import ResourceNotFoundError
from tests.factories import UserFactory


def test_upsert_creates_when_absent(db: Session):
    user = UserFactory()
    record, created = personal_record_service.upsert(
        db, user.id, PersonalRecordUpsert(birth_date=date(1990, 1, 2), gender="female")
    )
    assert created is True
    assert record.user_id == user.id
    assert record.birth_date == date(1990, 1, 2)
    assert record.gender == "female"


def test_upsert_updates_when_present_without_duplicate(db: Session):
    user = UserFactory()
    first, created_first = personal_record_service.upsert(
        db, user.id, PersonalRecordUpsert(birth_date=date(1990, 1, 2))
    )
    second, created_second = personal_record_service.upsert(
        db, user.id, PersonalRecordUpsert(birth_date=date(1985, 6, 6), gender="male")
    )

    assert created_first is True
    assert created_second is False
    assert second.id == first.id  # same row, no duplicate
    assert second.birth_date == date(1985, 6, 6)
    assert second.gender == "male"

    all_for_user = (
        db.query(type(second)).filter(type(second).user_id == user.id).all()
    )
    assert len(all_for_user) == 1


def test_upsert_unknown_user_raises_not_found(db: Session):
    with pytest.raises(ResourceNotFoundError):
        personal_record_service.upsert(db, uuid4(), PersonalRecordUpsert(birth_date=date(1990, 1, 2)))


def test_get_for_user_returns_none_when_absent(db: Session):
    user = UserFactory()
    assert personal_record_service.get_for_user(db, user.id) is None


def test_get_for_user_raise_404_when_absent(db: Session):
    user = UserFactory()
    with pytest.raises(ResourceNotFoundError):
        personal_record_service.get_for_user(db, user.id, raise_404=True)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/services/test_personal_record_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.personal_record_service'`.

- [ ] **Step 3: Write minimal implementation**

Create `backend/app/services/personal_record_service.py`:

```python
from logging import Logger, getLogger
from uuid import UUID, uuid4

from app.database import DbSession
from app.models import PersonalRecord
from app.repositories.personal_record_repository import PersonalRecordRepository
from app.schemas.model_crud.activities import PersonalRecordCreate, PersonalRecordUpsert
from app.services.services import AppService
from app.services.user_service import user_service
from app.utils.exceptions import ResourceNotFoundError


class PersonalRecordService(
    AppService[PersonalRecordRepository, PersonalRecord, PersonalRecordCreate, PersonalRecordUpsert]
):
    def __init__(self, log: Logger, **kwargs):
        super().__init__(
            crud_model=PersonalRecordRepository,
            model=PersonalRecord,
            log=log,
            **kwargs,
        )

    def get_for_user(
        self,
        db_session: DbSession,
        user_id: UUID,
        raise_404: bool = False,
    ) -> PersonalRecord | None:
        record = self.crud.get_by_user_id(db_session, user_id)
        if not record and raise_404:
            raise ResourceNotFoundError(self.name, user_id)
        return record

    def upsert(
        self,
        db_session: DbSession,
        user_id: UUID,
        payload: PersonalRecordUpsert,
    ) -> tuple[PersonalRecord, bool]:
        # 404 if the user does not exist (avoids an opaque FK violation).
        user_service.get(db_session, user_id, raise_404=True)

        existing = self.crud.get_by_user_id(db_session, user_id)
        if existing is None:
            creator = PersonalRecordCreate(id=uuid4(), user_id=user_id, **payload.model_dump())
            return self.crud.create(db_session, creator), True

        return self.crud.update(db_session, existing, payload), False


personal_record_service = PersonalRecordService(log=getLogger(__name__))
```

Then register the singleton in `backend/app/services/__init__.py`: add
`from .personal_record_service import personal_record_service` (alphabetically near the other imports) and add `"personal_record_service",` to `__all__`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/services/test_personal_record_service.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/personal_record_service.py backend/app/services/__init__.py backend/tests/services/test_personal_record_service.py
git commit -m "feat(personal-record): service with idempotent upsert keyed on user_id"
```

---

### Task 4: Route — PUT/GET endpoints + registration + API tests

**Files:**
- Create: `backend/app/api/routes/v1/personal_records.py`
- Modify: `backend/app/api/routes/v1/__init__.py`
- Test: `backend/tests/api/v1/test_personal_records.py` (create)

**Interfaces:**
- Consumes: `personal_record_service` (Task 3); `ApiKeyDep` (`app/services`); `PersonalRecordResponse`, `PersonalRecordUpsert` (Task 1); `DbSession` (`app/database`).
- Produces: `router` exposing `PUT` and `GET /users/{user_id}/personal-record`, registered under the `External: Users` tag.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/api/v1/test_personal_records.py`:

```python
from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.factories import ApiKeyFactory, DeveloperFactory, UserFactory
from tests.utils import api_key_headers


def _headers() -> dict[str, str]:
    developer = DeveloperFactory(email="pr-test@example.com", password="test123")
    api_key = ApiKeyFactory(developer=developer)
    return api_key_headers(api_key.id)


class TestUpsertPersonalRecord:
    def test_creates_when_absent(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        user = UserFactory()
        headers = _headers()
        payload = {"birth_date": "1990-05-17", "gender": "male"}

        response = client.put(
            f"{api_v1_prefix}/users/{user.id}/personal-record", json=payload, headers=headers
        )

        assert response.status_code == 201
        data = response.json()
        assert data["user_id"] == str(user.id)
        assert data["birth_date"] == "1990-05-17"
        assert data["gender"] == "male"
        assert "id" in data

    def test_updates_when_present(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        user = UserFactory()
        headers = _headers()
        url = f"{api_v1_prefix}/users/{user.id}/personal-record"

        first = client.put(url, json={"birth_date": "1990-05-17"}, headers=headers)
        assert first.status_code == 201
        first_id = first.json()["id"]

        second = client.put(url, json={"birth_date": "1985-06-06", "gender": "female"}, headers=headers)
        assert second.status_code == 200
        data = second.json()
        assert data["id"] == first_id  # same row
        assert data["birth_date"] == "1985-06-06"
        assert data["gender"] == "female"

    def test_unknown_user_returns_404(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        headers = _headers()
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = client.put(
            f"{api_v1_prefix}/users/{fake_id}/personal-record",
            json={"birth_date": "1990-05-17"},
            headers=headers,
        )
        assert response.status_code == 404

    def test_future_birth_date_returns_400(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        user = UserFactory()
        headers = _headers()
        future = (date.today() + timedelta(days=1)).isoformat()
        response = client.put(
            f"{api_v1_prefix}/users/{user.id}/personal-record",
            json={"birth_date": future},
            headers=headers,
        )
        assert response.status_code == 400

    def test_unauthorized_without_api_key(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        user = UserFactory()
        response = client.put(
            f"{api_v1_prefix}/users/{user.id}/personal-record",
            json={"birth_date": "1990-05-17"},
        )
        assert response.status_code == 401


class TestGetPersonalRecord:
    def test_returns_record(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        user = UserFactory()
        headers = _headers()
        url = f"{api_v1_prefix}/users/{user.id}/personal-record"
        client.put(url, json={"birth_date": "1990-05-17", "gender": "male"}, headers=headers)

        response = client.get(url, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == str(user.id)
        assert data["birth_date"] == "1990-05-17"

    def test_404_when_no_record(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        user = UserFactory()
        headers = _headers()
        response = client.get(f"{api_v1_prefix}/users/{user.id}/personal-record", headers=headers)
        assert response.status_code == 404

    def test_unauthorized_without_api_key(self, client: TestClient, db: Session, api_v1_prefix: str) -> None:
        user = UserFactory()
        response = client.get(f"{api_v1_prefix}/users/{user.id}/personal-record")
        assert response.status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/api/v1/test_personal_records.py -v`
Expected: FAIL — 404 on every call (route not registered yet).

- [ ] **Step 3: Write minimal implementation**

Create `backend/app/api/routes/v1/personal_records.py`:

```python
from uuid import UUID

from fastapi import APIRouter, Response, status

from app.database import DbSession
from app.schemas.model_crud.activities import PersonalRecordResponse, PersonalRecordUpsert
from app.services import ApiKeyDep, personal_record_service

router = APIRouter()


@router.get("/users/{user_id}/personal-record", response_model=PersonalRecordResponse)
def get_personal_record(user_id: UUID, db: DbSession, _api_key: ApiKeyDep):
    """Return the user's personal_record (404 if none exists)."""
    return personal_record_service.get_for_user(db, user_id, raise_404=True)


@router.put("/users/{user_id}/personal-record", response_model=PersonalRecordResponse)
def upsert_personal_record(
    user_id: UUID,
    payload: PersonalRecordUpsert,
    db: DbSession,
    response: Response,
    _api_key: ApiKeyDep,
):
    """Create or update the user's personal_record. 201 on create, 200 on update."""
    record, created = personal_record_service.upsert(db, user_id, payload)
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return record
```

Then register it in `backend/app/api/routes/v1/__init__.py`:
- Add the import near the other route imports: `from .personal_records import router as personal_records_router`
- Add the include right after the `users_router` include, keeping the same tag:
  `v1_router.include_router(personal_records_router, tags=["External: Users"])`

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/api/v1/test_personal_records.py -v`
Expected: PASS (8 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/routes/v1/personal_records.py backend/app/api/routes/v1/__init__.py backend/tests/api/v1/test_personal_records.py
git commit -m "feat(personal-record): PUT/GET /users/{user_id}/personal-record write API"
```

---

### Task 5: Record the fork DELTA

**Files:**
- Modify: `FORK-DELTA.md` (repo root)

**Interfaces:**
- Consumes: nothing. Documentation only.
- Produces: nothing consumed by later tasks.

- [ ] **Step 1: Add the DELTA entry**

Append a new section to `FORK-DELTA.md` (match the file's existing heading style; place it with the other endpoint DELTAs):

```markdown
## Personal Record write API (net-new)

`PUT` / `GET /api/v1/users/{user_id}/personal-record` — adapter-driven write
API for `public.personal_record`. Upsert keyed on the 1:1 `user_id`
(`ApiKeyDep`, 201 create / 200 update). Body = `birth_date` + `gender`
(`sex` intentionally omitted — read by nothing in OW).

Purpose: let the .NET adapter set `birth_date` so OW computes HR-zone max HR as
`220 − age` (`estimate_max_hr`) at workout ingest instead of the
`DEFAULT_MAX_HR = 190` fallback.

Boundary: OW computes zones ONCE at ingest, so a populated `birth_date` only
affects workouts ingested afterward. Historical workouts keep their maxHr-190
zones and continue to be handled by the .NET adapter's
`WorkoutHrZoneHealService`.

Upstream OW has no write path for `personal_record` (only seed data writes it).
```

- [ ] **Step 2: Run the full suite for this feature to confirm nothing regressed**

Run: `cd backend && uv run pytest tests/schemas/test_personal_record_schema.py tests/repositories/test_personal_record_repository.py tests/services/test_personal_record_service.py tests/api/v1/test_personal_records.py -v`
Expected: PASS (all tasks' tests green together — 20 passed).

- [ ] **Step 3: Commit**

```bash
git add FORK-DELTA.md
git commit -m "docs(personal-record): record write API as a fork DELTA"
```

---

## Self-Review

**Spec coverage:**
- Endpoint `PUT`/`GET /users/{user_id}/personal-record`, `ApiKeyDep`, 201/200 → Task 4. ✅
- Upsert keyed on `user_id`, no duplicate row → Task 3 (+ verified in Tasks 3 & 4 tests). ✅
- Body = `PersonalRecordBase` (`birth_date` + `gender`); `sex` excluded → Task 1. ✅
- `birth_date` future/implausible-age validation → Task 1 (unit) + Task 4 (API, asserts **400** per OW's remap — spec's 422 corrected in Global Constraints). ✅
- Unknown user → 404; GET no row → 404; missing key → 401 → Task 4. ✅
- ORM serialization via `from_attributes` → Task 1. ✅
- Wiring mirrors `users.py` → service → repository → Tasks 2–4. ✅
- Fork DELTA record + future-workouts-only boundary → Task 5. ✅
- Behavioral "workout zones use 220−age after birth_date set": documented as the purpose/boundary; not automated here because it requires the full workout-ingest path — left to live verification post-merge (noted in Task 5 DELTA). ✅

**Placeholder scan:** No TBD/TODO; every code and test step is complete. ✅

**Type consistency:** `PersonalRecordUpsert`, `PersonalRecordCreate`, `PersonalRecordResponse`, `get_by_user_id`, `upsert(...) -> tuple[PersonalRecord, bool]`, `get_for_user(...)`, `personal_record_service`, `personal_records_router` are named identically across all tasks. ✅
