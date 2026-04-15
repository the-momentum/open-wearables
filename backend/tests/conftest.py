"""
Main pytest configuration for Open Wearables backend tests.

Following patterns from know-how-tests.md:
- PostgreSQL test database with transaction rollback (via testcontainers or external DB)
- Auto-use fixtures for global mocking
- Factory pattern for test data
"""

import os
import sys
from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch
from urllib.parse import urlparse

import pytest
import redis as redis_lib
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer

from app.config import settings
from app.database import BaseDbModel, _get_db_dependency
from app.integrations.redis_client import get_redis_client
from app.main import api
from app.models import SeriesTypeDefinition
from app.schemas.enums import SERIES_TYPE_DEFINITIONS
from tests import factories

# Set test environment before importing app modules
os.environ["ENV"] = "test"
os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only"
os.environ["MASTER_KEY"] = "dGVzdC1tYXN0ZXIta2V5LWZvci10ZXN0aW5nLW9ubHk="  # base64 test key


@pytest.fixture(scope="session")
def _postgres_url() -> Generator[str, None, None]:
    """
    Provide a PostgreSQL connection URL for tests.

    - If TEST_DATABASE_URL is set (e.g. in CI), use it directly.
    - Otherwise, spin up a PostgreSQL container via testcontainers.
    """
    explicit_url = os.environ.get("TEST_DATABASE_URL")
    if explicit_url:
        yield explicit_url
        return

    with PostgresContainer(
        image="postgres:18",
        username="open-wearables",
        password="open-wearables",
        dbname="open_wearables_test",
        driver="psycopg",
    ) as pg:
        yield pg.get_connection_url()


@pytest.fixture(scope="session")
def engine(_postgres_url: str) -> Any:
    """Create test database engine and tables."""
    test_engine = create_engine(
        _postgres_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )
    BaseDbModel.metadata.create_all(bind=test_engine)

    # Seed series type definitions (these need to exist for foreign key constraints)
    with Session(bind=test_engine) as session:
        for type_id, enum, unit in SERIES_TYPE_DEFINITIONS:
            # Skip series types with codes exceeding VARCHAR(32) limit
            if len(enum.value) > 32:
                continue
            existing = session.query(SeriesTypeDefinition).filter(SeriesTypeDefinition.id == type_id).first()
            if not existing:
                series_type = SeriesTypeDefinition(id=type_id, code=enum.value, unit=unit)
                session.add(series_type)
        session.commit()

    yield test_engine
    BaseDbModel.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="session")
def session_factory(engine: Any) -> Any:
    """Create session factory bound to test engine."""
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def db(engine: Any, session_factory: Any) -> Generator[Session, None, None]:
    """
    Create a test database session with transaction rollback.
    Each test runs in its own transaction that gets rolled back.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = session_factory(bind=connection)

    # Begin a nested transaction (savepoint)
    nested = connection.begin_nested()

    # If the application code calls commit, restart the savepoint
    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(session: Session, transaction: Any) -> None:
        nonlocal nested
        if not nested.is_active:
            nested = connection.begin_nested()

    yield session

    # Rollback everything
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(autouse=True)
def set_factory_session(db: Session) -> Generator[None, None, None]:
    """Set database session for all factory-boy factories."""
    for name, obj in vars(factories).items():
        if isinstance(obj, type) and hasattr(obj, "_meta") and hasattr(obj._meta, "sqlalchemy_session"):
            obj._meta.sqlalchemy_session = db
    yield
    # Clear session after test
    for name, obj in vars(factories).items():
        if isinstance(obj, type) and hasattr(obj, "_meta") and hasattr(obj._meta, "sqlalchemy_session"):
            obj._meta.sqlalchemy_session = None


@pytest.fixture
def client(db: Session) -> Generator[TestClient, None, None]:
    """
    Create a test client with database dependency override.
    """

    def override_get_db() -> Generator[Session, None, None]:
        yield db

    api.dependency_overrides[_get_db_dependency] = override_get_db

    with TestClient(api) as test_client:
        yield test_client

    api.dependency_overrides.clear()


# ============================================================================
# Infrastructure: Redis
# ============================================================================


@pytest.fixture(scope="session")
def _redis_url() -> Generator[str, None, None]:
    """
    Provide a Redis connection URL for tests.

    - If TEST_REDIS_URL is set (e.g. in CI), use it directly.
    - Otherwise, spin up a Redis container via testcontainers.
    """
    explicit_url = os.environ.get("TEST_REDIS_URL")
    if explicit_url:
        yield explicit_url
        return

    with RedisContainer(image="redis:7") as r:
        host = r.get_container_host_ip()
        port = r.get_exposed_port(6379)
        yield f"redis://{host}:{port}/0"


@pytest.fixture(scope="session", autouse=True)
def _configure_redis(_redis_url: str) -> Generator[None, None, None]:
    """
    Point app settings at the test Redis instance for the whole session.

    Uses patch.object instead of env vars because settings is already
    instantiated from config/.env at import time.
    """
    parsed = urlparse(_redis_url)
    with (
        patch.object(settings, "redis_host", parsed.hostname or "localhost"),
        patch.object(settings, "redis_port", parsed.port or 6379),
    ):
        yield


@pytest.fixture(autouse=True)
def flush_redis(_redis_url: str) -> Generator[None, None, None]:
    """Flush Redis state before each test to ensure isolation."""
    redis_lib.from_url(_redis_url).flushdb()
    get_redis_client.cache_clear()
    yield
    redis_lib.from_url(_redis_url).flushdb()
    get_redis_client.cache_clear()


# ============================================================================
# Auto-use fixtures for global mocking
# ============================================================================


@pytest.fixture(autouse=True)
def mock_webhook_dispatch() -> Generator[MagicMock, None, None]:
    """Prevent outgoing webhook tasks from attempting real Redis/Celery connections.

    Patches the Celery task's delay so tests that don't care about webhook
    emission never hang on a missing broker.  Tests that DO verify dispatch
    behaviour override this via their own @patch decorator (innermost wins).
    """
    with patch("app.integrations.celery.tasks.emit_webhook_event_task.emit_webhook_event") as mock:
        mock.delay.return_value = None
        yield mock


@pytest.fixture(autouse=True)
def mock_celery_tasks(monkeypatch: pytest.MonkeyPatch) -> Generator[MagicMock, None, None]:
    """Mock Celery tasks to run synchronously."""
    mock_task = MagicMock()
    mock_task.delay.return_value = MagicMock()
    mock_task.apply_async.return_value = MagicMock()

    mock_handler_celery = MagicMock()
    mock_handler_celery.send_task.return_value.id = "mock-task-id"

    with (
        patch("celery.current_app") as mock_celery,
        # Prevent webhook handler from dispatching the backfill Celery task
        patch("app.services.providers.garmin.webhook_handler.celery_app", mock_handler_celery),
    ):
        # Configure Celery to use in-memory broker and result backend
        # We Mock the conf object to return our test settings
        mock_conf = MagicMock()
        mock_conf.__getitem__ = lambda s, k: {
            "task_always_eager": True,
            "task_eager_propagates": True,
            "broker_url": "memory://",
            "result_backend": "cache+memory://",
        }.get(k)

        # When update is called, we don't want to actually connect to Redis
        mock_conf.update = MagicMock()
        mock_celery.conf = mock_conf

        yield mock_task


@pytest.fixture(autouse=True)
def mock_external_apis() -> Generator[dict[str, MagicMock], None, None]:
    """Mock external API calls (Garmin, Polar, Suunto, AWS)."""
    mocks: dict[str, MagicMock] = {}

    # Configure boto3 S3 mock
    mock_s3 = MagicMock()
    mock_s3.generate_presigned_url.return_value = "https://test-bucket.s3.amazonaws.com/test-key"
    mock_s3.generate_presigned_post.return_value = {
        "url": "https://test-bucket.s3.amazonaws.com",
        "fields": {
            "key": "test-user/raw/test.xml",
            "Content-Type": "application/xml",
            "policy": "test-policy",
            "x-amz-algorithm": "AWS4-HMAC-SHA256",
            "x-amz-credential": "test-credential",
            "x-amz-date": "20251217T000000Z",
            "x-amz-signature": "test-signature",
        },
    }
    mock_s3.head_bucket.return_value = {}
    mock_s3.put_object.return_value = {"ETag": "test-etag"}

    garmin_handler = "app.services.providers.garmin.webhook_handler"

    with (
        patch("httpx.AsyncClient") as mock_httpx,
        patch("boto3.client", return_value=mock_s3) as mock_boto3,
        patch("requests.Session") as mock_requests,
        patch("app.services.apple.apple_xml.aws_service.AWS_BUCKET_NAME", "test-bucket"),
        patch("app.services.apple.apple_xml.presigned_url_service.AWS_BUCKET_NAME", "test-bucket"),
        patch("app.services.apple.apple_xml.aws_service.get_s3_client", return_value=mock_s3),
        patch("app.services.apple.apple_xml.presigned_url_service.get_s3_client", return_value=mock_s3),
        patch("app.integrations.celery.tasks.process_aws_upload_task.get_s3_client", return_value=mock_s3),
        patch(
            "app.services.apple.apple_xml.presigned_url_service.presigned_url_service.s3_client", mock_s3, create=True
        ),
        patch(f"{garmin_handler}.mark_type_success", return_value=False),
        patch(
            f"{garmin_handler}.get_backfill_status",
            return_value={"overall_status": "complete", "current_window": 0, "total_windows": 0},
        ),
    ):
        mocks["httpx"] = mock_httpx
        mocks["boto3"] = mock_boto3
        mocks["requests"] = mock_requests
        mocks["s3"] = mock_s3

        yield mocks


@pytest.fixture(autouse=True)
def fast_password_hashing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Speed up tests by using simple password hashing."""

    def simple_hash(password: str) -> str:
        return f"hashed_{password}"

    def simple_verify(plain: str, hashed: str) -> bool:
        return hashed == f"hashed_{plain}"

    # Patch in the source module
    monkeypatch.setattr("app.utils.security.get_password_hash", simple_hash)
    monkeypatch.setattr("app.utils.security.verify_password", simple_verify)
    # Also patch in modules that import these functions directly (use sys.modules to avoid name shadowing)
    if "app.services.developer_service" in sys.modules:
        monkeypatch.setattr(sys.modules["app.services.developer_service"], "get_password_hash", simple_hash)
    monkeypatch.setattr("app.api.routes.v1.auth.verify_password", simple_verify)


# ============================================================================
# Shared test utilities
# ============================================================================


@pytest.fixture
def api_v1_prefix() -> str:
    """Return the API v1 prefix."""
    return "/api/v1"
