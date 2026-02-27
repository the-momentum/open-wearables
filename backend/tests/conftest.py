"""
Main pytest configuration for Open Wearables backend tests.

Following patterns from know-how-tests.md:
- PostgreSQL test database with transaction rollback
- Auto-use fixtures for global mocking
- Factory pattern for test data
"""

import os
from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

# Set test environment before importing app modules
os.environ["ENV"] = "test"
os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only"
os.environ["MASTER_KEY"] = "dGVzdC1tYXN0ZXIta2V5LWZvci10ZXN0aW5nLW9ubHk="  # base64 test key

from app.database import BaseDbModel, _get_db_dependency
from app.main import api

# Test database URL - uses test PostgreSQL database
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://open-wearables:open-wearables@localhost:5432/open_wearables_test",
)


@pytest.fixture(scope="session")
def engine() -> Any:
    """Create test database engine and tables."""
    test_engine = create_engine(
        TEST_DATABASE_URL,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )
    BaseDbModel.metadata.create_all(bind=test_engine)

    # Seed series type definitions (these need to exist for foreign key constraints)
    from sqlalchemy.orm import Session as SessionClass

    from app.models import SeriesTypeDefinition
    from app.schemas.series_types import SERIES_TYPE_DEFINITIONS

    with SessionClass(bind=test_engine) as session:
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
    from tests import factories

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
# Auto-use fixtures for global mocking
# ============================================================================


@pytest.fixture(autouse=True)
def mock_redis(monkeypatch: pytest.MonkeyPatch) -> Generator[MagicMock, None, None]:
    """Globally mock Redis to prevent connection errors in tests."""
    mock = MagicMock()
    mock.lock.return_value.__enter__ = MagicMock(return_value=None)
    mock.lock.return_value.__exit__ = MagicMock(return_value=None)
    mock.get.return_value = None
    mock.set.return_value = True
    mock.setex.return_value = True
    mock.expire.return_value = True
    mock.delete.return_value = True
    mock.sadd.return_value = 1
    mock.srem.return_value = 1
    mock.smembers.return_value = set()

    # Return mock for redis.from_url (used by get_redis_client)
    # We also need to clear lru_cache of get_redis_client to ensure it picks up the mock
    from app.integrations.redis_client import get_redis_client

    get_redis_client.cache_clear()

    with patch("redis.from_url", return_value=mock):
        yield mock


@pytest.fixture(autouse=True)
def mock_celery_tasks(monkeypatch: pytest.MonkeyPatch) -> Generator[MagicMock, None, None]:
    """Mock Celery tasks to run synchronously."""
    # Mock the poll_sqs_task specifically
    mock_task = MagicMock()
    mock_task.delay.return_value = MagicMock()
    mock_task.apply_async.return_value = MagicMock()

    with (
        patch("celery.current_app") as mock_celery,
        patch("app.integrations.celery.tasks.poll_sqs_task.poll_sqs_task", mock_task),
        patch("app.api.routes.v1.import_xml.poll_sqs_task", mock_task),
        # Patch the new finalize_stale_sleeps task that was added in this PR
        patch("app.integrations.celery.tasks.process_sdk_upload_task.finalize_stale_sleeps", mock_task),
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

    webhook_module = "app.api.routes.v1.garmin_webhooks"

    with (
        patch("httpx.AsyncClient") as mock_httpx,
        patch("boto3.client", return_value=mock_s3) as mock_boto3,
        patch("requests.Session") as mock_requests,
        patch("app.services.apple.apple_xml.aws_service.AWS_BUCKET_NAME", "test-bucket"),
        patch("app.services.apple.apple_xml.presigned_url_service.AWS_BUCKET_NAME", "test-bucket"),
        patch("app.services.apple.apple_xml.aws_service.s3_client", mock_s3),
        patch("app.services.apple.apple_xml.presigned_url_service.s3_client", mock_s3),
        patch(f"{webhook_module}.get_trace_id", return_value=None),
        patch(f"{webhook_module}.mark_type_success", return_value=False),
        patch(
            f"{webhook_module}.get_backfill_status",
            return_value={"overall_status": "complete", "current_window": 0, "total_windows": 0},
        ),
        patch(f"{webhook_module}.trigger_next_pending_type", return_value={}),
    ):
        mocks["httpx"] = mock_httpx
        mocks["boto3"] = mock_boto3
        mocks["requests"] = mock_requests
        mocks["s3"] = mock_s3

        yield mocks


@pytest.fixture(autouse=True)
def fast_password_hashing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Speed up tests by using simple password hashing."""
    import sys

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
