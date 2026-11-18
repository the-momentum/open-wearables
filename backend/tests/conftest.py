"""
Main pytest configuration for Open Wearables backend tests.

Following patterns from know-how-tests.md:
- PostgreSQL test database with transaction rollback (via testcontainers or external DB)
- Auto-use fixtures for global mocking
- Factory pattern for test data
"""

import ipaddress
import os
import socket
import sys
from collections.abc import Generator
from contextlib import ExitStack
from typing import Any
from unittest.mock import MagicMock, patch
from urllib.parse import urlparse

import pytest
import redis as redis_lib
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, make_url, text
from sqlalchemy.orm import Session, sessionmaker
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer

from app.config import Settings, settings
from app.database import BaseDbModel, _get_db_dependency
from app.integrations.redis_client import get_redis_client
from app.main import api, celery_app
from app.models import SeriesTypeDefinition
from app.schemas.enums import SERIES_TYPE_DEFINITIONS
from app.utils.structured_logging import strict_attributes
from tests import factories

# An unserializable or clashing log attribute fails the test instead of being printed with str().
strict_attributes(True)

# OW_IGNORE_ENV_FILE (tests/__init__.py) covers the global settings only. Tests that build
# their own Settings(...) must not read a developer's config/.env either.
Settings.model_config["env_file"] = None


# ============================================================================
# Infrastructure: containers
# ============================================================================

_containers = ExitStack()
_infrastructure_urls: dict[str, str] = {}


def pytest_sessionstart(session: pytest.Session) -> None:
    """Start the containers before the first test.

    - TEST_DATABASE_URL / TEST_REDIS_URL (e.g. in CI) are used directly.
    - Otherwise Postgres and Redis run in containers via testcontainers.
    """
    if session.config.option.collectonly:
        return

    postgres_url = os.environ.get("TEST_DATABASE_URL")
    if not postgres_url:
        pg = _containers.enter_context(
            PostgresContainer(
                image="postgres:18",
                username="open-wearables",
                password="open-wearables",
                dbname="open_wearables_test",
                driver="psycopg",
            )
            .with_command("postgres -c fsync=off -c synchronous_commit=off -c full_page_writes=off")
            .with_tmpfs_mount("/var/lib/postgresql", size="size=1g")
        )
        postgres_url = pg.get_connection_url()

    redis_url = os.environ.get("TEST_REDIS_URL")
    if not redis_url:
        r = _containers.enter_context(RedisContainer(image="redis:7"))
        redis_url = f"redis://{r.get_container_host_ip()}:{r.get_exposed_port(6379)}/0"

    _infrastructure_urls.update(postgres=postgres_url, redis=redis_url)
    os.environ["TEST_DATABASE_URL"] = postgres_url
    os.environ["TEST_REDIS_URL"] = redis_url


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    _containers.close()


def _xdist_worker_index() -> int | None:
    """0 for pytest-xdist worker gw0, 1 for gw1, ...; None when tests run in a single process."""
    worker = os.environ.get("PYTEST_XDIST_WORKER")
    return int(worker.removeprefix("gw")) if worker else None


@pytest.fixture(scope="session")
def _postgres_url() -> Generator[str, None, None]:
    """Each xdist worker gets its own database, so workers don't drop each other's tables."""
    base_url = _infrastructure_urls["postgres"]
    worker = _xdist_worker_index()
    if worker is None:
        yield base_url
        return

    base = make_url(base_url)
    db_name = f"{base.database}_gw{worker}"
    admin = create_engine(base, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{db_name}" WITH (FORCE)'))  # left over by a killed run
        conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    yield base.set(database=db_name).render_as_string(hide_password=False)
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{db_name}" WITH (FORCE)'))
    admin.dispose()


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
        # Reset the sequence so auto-generated IDs don't collide with seeded ones
        session.execute(
            text("SELECT setval('series_type_definition_id_seq', (SELECT MAX(id) FROM series_type_definition))")
        )
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
def _redis_url() -> str:
    """Each xdist worker gets its own Redis database number, so flush_redis stays per worker."""
    base_url = _infrastructure_urls["redis"]
    worker = _xdist_worker_index()
    if worker is None:
        return base_url
    parsed = urlparse(base_url)
    db = int(parsed.path.lstrip("/") or 0) + worker
    if db > 15:  # Redis ships with databases 0-15
        pytest.exit(f"Redis has no database {db} for xdist worker gw{worker}; run with fewer workers (-n)", 2)
    return parsed._replace(path=f"/{db}").geturl()


@pytest.fixture(scope="session", autouse=True)
def _configure_redis(_redis_url: str) -> Generator[None, None, None]:
    """
    Point app settings at the test Redis instance for the whole session.

    Uses patch.object instead of env vars because settings is already
    instantiated at import time.
    """
    parsed = urlparse(_redis_url)
    with (
        patch.object(settings, "redis_host", parsed.hostname or "localhost"),
        patch.object(settings, "redis_port", parsed.port or 6379),
        patch.object(settings, "redis_db", int(parsed.path.lstrip("/") or 0)),
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
# Network isolation
# ============================================================================

_real_connect = socket.socket.connect
_real_connect_ex = socket.socket.connect_ex
_real_getaddrinfo = socket.getaddrinfo
_allowed_addresses: set[tuple[str, int]] = set()  # (IP, port) of the test Postgres/Redis
_blocked_connections: list[str] = []
_resolved_names: dict[str, str] = {}  # IP -> hostname, so failures name the host, not just an IP


def _recording_getaddrinfo(host: Any, *args: Any, **kwargs: Any) -> Any:
    results = _real_getaddrinfo(host, *args, **kwargs)
    if isinstance(host, str):
        for *_, sockaddr in results:
            _resolved_names[str(sockaddr[0])] = host
    return results


def _describe(address: tuple[Any, ...]) -> str:
    host = _resolved_names.get(address[0], address[0])
    return f"{host}:{address[1]}"


def _connection_allowed(address: Any) -> bool:
    if not isinstance(address, tuple):  # AF_UNIX, e.g. the Docker socket used by testcontainers
        return True
    host, port = address[0], address[1]
    try:
        if ipaddress.ip_address(host).is_loopback:
            return True
    except ValueError:
        pass
    return (host, port) in _allowed_addresses


def _guarded_connect(self: socket.socket, address: Any) -> None:
    if not _connection_allowed(address):
        _blocked_connections.append(_describe(address))
        raise ConnectionRefusedError(f"Network access is blocked in tests: {_describe(address)}")
    _real_connect(self, address)


def _guarded_connect_ex(self: socket.socket, address: Any) -> int:
    if not _connection_allowed(address):
        _blocked_connections.append(_describe(address))
        return 111  # ECONNREFUSED
    return _real_connect_ex(self, address)


@pytest.fixture(scope="session", autouse=True)
def _block_network(_postgres_url: str, _redis_url: str) -> Generator[None, None, None]:
    """Refuse TCP connections to anything but loopback and the test Postgres/Redis."""
    for url, default_port in ((_postgres_url, 5432), (_redis_url, 6379)):
        parsed = urlparse(url)
        if not parsed.hostname:
            continue
        port = parsed.port or default_port
        for *_, sockaddr in socket.getaddrinfo(parsed.hostname, port, type=socket.SOCK_STREAM):
            _allowed_addresses.add((str(sockaddr[0]), port))
    with (
        patch.object(socket.socket, "connect", _guarded_connect),
        patch.object(socket.socket, "connect_ex", _guarded_connect_ex),
        patch.object(socket, "getaddrinfo", _recording_getaddrinfo),
    ):
        yield


@pytest.fixture(autouse=True)
def _fail_on_network_access(_block_network: None) -> Generator[None, None, None]:
    """Fail a test that tried to reach the network, even if the code under test swallowed the error.

    Mock the HTTP call (e.g. ``@patch("httpx.delete")``) in tests that exercise provider APIs.
    """
    _blocked_connections.clear()
    yield
    if _blocked_connections:
        pytest.fail(f"Test tried to reach the network: {', '.join(sorted(set(_blocked_connections)))}")


# ============================================================================
# Auto-use fixtures for global mocking
# ============================================================================


@pytest.fixture(scope="session", autouse=True)
def mock_svix_lifespan() -> Generator[MagicMock, None, None]:
    """Prevent register_event_types() from making ~170 HTTP calls to Svix on
    every TestClient lifespan startup during tests."""
    with patch("app.services.outgoing_webhooks.svix.register_event_types") as mock:
        yield mock


@pytest.fixture(autouse=True)
def _celery_in_memory_broker() -> None:
    """Keep task dispatch inside the process.
    Re-applied per test because ``create_celery()`` resets the broker URL.
    """
    celery_app.conf.update(broker_url="memory://", result_backend="cache+memory://")


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
    mock_s3.create_multipart_upload.return_value = {"UploadId": "test-upload-id"}
    mock_s3.list_parts.return_value = {
        "Parts": [{"PartNumber": 1, "ETag": "e1"}],
        "IsTruncated": False,
    }
    mock_s3.complete_multipart_upload.return_value = {"ETag": "test-etag", "Key": "test-user/raw/test.xml"}
    mock_s3.abort_multipart_upload.return_value = {}

    garmin_handler = "app.services.providers.garmin.webhook_handler"

    with (
        patch("httpx.AsyncClient") as mock_httpx,
        patch("boto3.client", return_value=mock_s3) as mock_boto3,
        patch("requests.Session") as mock_requests,
        patch.object(settings, "aws_bucket_name", "test-bucket"),
        patch("app.services.providers.apple.apple_xml.aws_service.get_s3_client", return_value=mock_s3),
        patch("app.services.providers.apple.apple_xml.presigned_url_service.get_s3_client", return_value=mock_s3),
        patch("app.services.providers.apple.apple_xml.multipart_upload_service.get_s3_client", return_value=mock_s3),
        patch(
            "app.services.providers.apple.apple_xml.presigned_url_service.get_public_s3_client", return_value=mock_s3
        ),
        patch(
            "app.services.providers.apple.apple_xml.multipart_upload_service.get_public_s3_client", return_value=mock_s3
        ),
        patch("app.integrations.celery.tasks.process_aws_upload_task.get_s3_client", return_value=mock_s3),
        patch(
            "app.services.providers.apple.apple_xml.presigned_url_service.presigned_url_service.s3_client",
            mock_s3,
            create=True,
        ),
        patch(
            "app.services.providers.apple.apple_xml.presigned_url_service.presigned_url_service.public_s3_client",
            mock_s3,
            create=True,
        ),
        patch(
            "app.services.providers.apple.apple_xml.multipart_upload_service.multipart_upload_service.s3_client",
            mock_s3,
            create=True,
        ),
        patch(
            "app.services.providers.apple.apple_xml.multipart_upload_service.multipart_upload_service.public_s3_client",
            mock_s3,
            create=True,
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
