"""
Root conftest for Open Wearables backend tests.

Uses testcontainers-postgres so every test run gets a fresh, disposable
database — no manual ``CREATE DATABASE open_wearables_test`` step required.

Key design decisions
────────────────────
* **session-scoped** Postgres container + engine  →  container starts once per
  ``pytest`` invocation.
* **function-scoped** DB session wrapped in a SAVEPOINT  →  every test is
  automatically rolled back, giving full isolation with near-zero cost.
* ``polyfactory`` factories receive the session through a single autouse
  fixture, so they always flush into the correct transaction.
* Redis, Celery and all external HTTP calls are globally mocked via autouse
  fixtures — tests never touch real infra besides Postgres.
"""

from __future__ import annotations

import os
from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Connection, Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from testcontainers.postgres import PostgresContainer

# ── Set test environment BEFORE any app import ──────────────────────────────
os.environ["ENV"] = "test"
os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only"
os.environ["MASTER_KEY"] = "dGVzdC1tYXN0ZXIta2V5LWZvci10ZXN0aW5nLW9ubHk="  # base64

from app.database import BaseDbModel, _get_db_dependency
from app.main import api

# ════════════════════════════════════════════════════════════════════════════
#  Database infrastructure  (session scope — started once)
# ════════════════════════════════════════════════════════════════════════════

POSTGRES_IMAGE = "postgres:16-alpine"


@pytest.fixture(scope="session")
def postgres_container() -> Generator[PostgresContainer, None, None]:
    """Spin up a throwaway Postgres container for the whole test session."""
    with PostgresContainer(POSTGRES_IMAGE, driver="psycopg") as pg:
        yield pg


@pytest.fixture(scope="session")
def database_url(postgres_container: PostgresContainer) -> str:
    """Return the SQLAlchemy connection URL for the test container."""
    return postgres_container.get_connection_url()


@pytest.fixture(scope="session")
def engine(database_url: str) -> Generator[Engine, None, None]:
    """Create the engine, run DDL and seed reference data."""
    test_engine = create_engine(
        database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )

    # Create all tables
    BaseDbModel.metadata.create_all(bind=test_engine)

    # Seed series-type definitions (required for FK constraints)
    _seed_series_types(test_engine)

    yield test_engine

    BaseDbModel.metadata.drop_all(bind=test_engine)
    test_engine.dispose()


@pytest.fixture(scope="session")
def session_factory(engine: Engine) -> sessionmaker[Session]:
    """Session factory bound to the test engine."""
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ════════════════════════════════════════════════════════════════════════════
#  Per-test database session  (function scope — rolled back after each test)
# ════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def db(engine: Engine, session_factory: sessionmaker[Session]) -> Generator[Session, None, None]:
    """
    Provide a transactional DB session that is rolled back after each test.

    Wraps the session inside ``BEGIN`` → ``SAVEPOINT``.  If application code
    calls ``session.commit()``, only the savepoint is released and a new one
    is created, so the outer transaction stays open and can be rolled back
    cleanly at the end.
    """
    connection: Connection = engine.connect()
    transaction = connection.begin()
    session: Session = session_factory(bind=connection)

    nested = connection.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def _restart_savepoint(sess: Session, trans: Any) -> None:
        nonlocal nested
        if not nested.is_active:
            nested = connection.begin_nested()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


# ════════════════════════════════════════════════════════════════════════════
#  Factory wiring (polyfactory)
# ════════════════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def _wire_factories(db: Session) -> Generator[None, None, None]:
    """Inject the current test session into every polyfactory factory."""
    from tests import factories

    factories.set_session(db)
    yield
    factories.clear_session()


# ════════════════════════════════════════════════════════════════════════════
#  FastAPI test client
# ════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def client(db: Session) -> Generator[TestClient, None, None]:
    """TestClient wired to the per-test DB session."""

    def _override_db() -> Generator[Session, None, None]:
        yield db

    api.dependency_overrides[_get_db_dependency] = _override_db

    with TestClient(api) as c:
        yield c

    api.dependency_overrides.clear()


# ════════════════════════════════════════════════════════════════════════════
#  Global mocks  (autouse — applied to every test)
# ════════════════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def _mock_redis() -> Generator[MagicMock, None, None]:
    """Prevent any real Redis connection."""
    mock = MagicMock()
    mock.lock.return_value.__enter__ = MagicMock(return_value=None)
    mock.lock.return_value.__exit__ = MagicMock(return_value=None)
    for attr in ("get", "set", "setex", "expire", "delete"):
        setattr(mock, attr, MagicMock(return_value=None if attr == "get" else True))
    mock.sadd.return_value = 1
    mock.srem.return_value = 1
    mock.smembers.return_value = set()

    from app.integrations.redis_client import get_redis_client

    get_redis_client.cache_clear()

    with patch("redis.from_url", return_value=mock):
        yield mock


@pytest.fixture(autouse=True)
def _mock_celery() -> Generator[MagicMock, None, None]:
    """Run Celery tasks synchronously via mocks."""
    mock_task = MagicMock()
    mock_task.delay.return_value = MagicMock()
    mock_task.apply_async.return_value = MagicMock()

    with (
        patch("celery.current_app") as mock_celery,
        patch(
            "app.integrations.celery.tasks.poll_sqs_task.poll_sqs_task",
            mock_task,
        ),
        patch("app.api.routes.v1.import_xml.poll_sqs_task", mock_task),
        patch(
            "app.integrations.celery.tasks.process_apple_upload_task.finalize_stale_sleeps",
            mock_task,
        ),
    ):
        mock_conf = MagicMock()
        mock_conf.__getitem__ = lambda s, k: {
            "task_always_eager": True,
            "task_eager_propagates": True,
            "broker_url": "memory://",
            "result_backend": "cache+memory://",
        }.get(k)
        mock_conf.update = MagicMock()
        mock_celery.conf = mock_conf
        yield mock_task


@pytest.fixture(autouse=True)
def _mock_external_apis() -> Generator[dict[str, MagicMock], None, None]:
    """Prevent any real HTTP call to Garmin / Polar / Suunto / AWS."""
    mock_s3 = MagicMock()
    mock_s3.generate_presigned_url.return_value = "https://test-bucket.s3.amazonaws.com/test-key"
    mock_s3.generate_presigned_post.return_value = {
        "url": "https://test-bucket.s3.amazonaws.com",
        "fields": {
            "key": "test-user/raw/test.xml",
            "Content-Type": "application/xml",
        },
    }
    mock_s3.head_bucket.return_value = {}
    mock_s3.put_object.return_value = {"ETag": "test-etag"}

    mocks: dict[str, MagicMock] = {}
    with (
        patch("httpx.AsyncClient") as mock_httpx,
        patch("boto3.client", return_value=mock_s3) as mock_boto3,
        patch("requests.Session") as mock_requests,
        patch(
            "app.services.apple.apple_xml.aws_service.AWS_BUCKET_NAME",
            "test-bucket",
        ),
        patch(
            "app.services.apple.apple_xml.presigned_url_service.AWS_BUCKET_NAME",
            "test-bucket",
        ),
        patch(
            "app.services.apple.apple_xml.aws_service.s3_client",
            mock_s3,
        ),
        patch(
            "app.services.apple.apple_xml.presigned_url_service.s3_client",
            mock_s3,
        ),
    ):
        mocks["httpx"] = mock_httpx
        mocks["boto3"] = mock_boto3
        mocks["requests"] = mock_requests
        mocks["s3"] = mock_s3
        yield mocks


@pytest.fixture(autouse=True)
def _fast_password_hashing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace bcrypt with trivial hash / verify for speed."""
    import sys

    def _hash(password: str) -> str:
        return f"hashed_{password}"

    def _verify(plain: str, hashed: str) -> bool:
        return hashed == f"hashed_{plain}"

    monkeypatch.setattr("app.utils.security.get_password_hash", _hash)
    monkeypatch.setattr("app.utils.security.verify_password", _verify)
    if "app.services.developer_service" in sys.modules:
        monkeypatch.setattr(
            sys.modules["app.services.developer_service"],
            "get_password_hash",
            _hash,
        )
    monkeypatch.setattr("app.api.routes.v1.auth.verify_password", _verify)


# ════════════════════════════════════════════════════════════════════════════
#  Shared convenience fixtures
# ════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def api_v1_prefix() -> str:
    return "/api/v1"


# ════════════════════════════════════════════════════════════════════════════
#  Internal helpers
# ════════════════════════════════════════════════════════════════════════════


def _seed_series_types(test_engine: Engine) -> None:
    """Insert canonical series-type definitions once per session."""
    from app.models import SeriesTypeDefinition
    from app.schemas.series_types import SERIES_TYPE_DEFINITIONS

    with Session(bind=test_engine) as session:
        for type_id, enum_member, unit in SERIES_TYPE_DEFINITIONS:
            if len(enum_member.value) > 32:
                continue
            if not session.get(SeriesTypeDefinition, type_id):
                session.add(
                    SeriesTypeDefinition(id=type_id, code=enum_member.value, unit=unit),
                )
        session.commit()
