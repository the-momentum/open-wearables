"""
Main pytest configuration for Open Wearables Agent tests.

Follows the same patterns as the backend test suite:
- PostgreSQL via testcontainers (or TEST_DATABASE_URL)
- Per-test async transaction rollback
- FastAPI TestClient with dependency overrides
- Autouse mocks for Celery, LLM, and external HTTP
"""

from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import AsyncGenerator, Generator
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

# psycopg3 async mode requires SelectorEventLoop on Windows (not the default ProactorEventLoop)
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Must be set before importing any app modules so pydantic-settings picks them up.
# Use `or` instead of setdefault so CI env vars set to "" (missing secrets) are
# overridden with safe test values rather than left as empty strings.
os.environ["SECRET_KEY"] = os.environ.get("SECRET_KEY") or "test-secret-key-for-testing-only"
os.environ["ANTHROPIC_API_KEY"] = os.environ.get("ANTHROPIC_API_KEY") or "sk-ant-test-key"
os.environ["CELERY_BROKER_URL"] = os.environ.get("CELERY_BROKER_URL") or "memory://"
os.environ["CELERY_RESULT_BACKEND"] = os.environ.get("CELERY_RESULT_BACKEND") or "cache+memory://"

import jwt
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.database import BaseDbModel, _get_async_db_dependency
from tests import factories

# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def _postgres_url() -> Generator[str, None, None]:
    """Provide a PostgreSQL connection URL for tests."""
    explicit_url = os.environ.get("TEST_DATABASE_URL")
    if explicit_url:
        yield explicit_url
        return

    from testcontainers.postgres import PostgresContainer

    # Subclass to replace SQLAlchemy-based health check with psycopg3 native sync connect.
    # SQLAlchemy's psycopg3 sync dialect uses the async API internally (via greenlets),
    # which requires a running event loop — unavailable in this sync fixture.
    class _SyncReadyPostgresContainer(PostgresContainer):
        def _connect(self) -> None:  # type: ignore[override]
            import time

            import psycopg  # psycopg3 native sync — no event loop required

            host = self.get_container_host_ip()
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                try:
                    port = int(self.get_exposed_port(self.port))
                    conn = psycopg.connect(
                        host=host,
                        port=port,
                        dbname=self.dbname,
                        user=self.username,
                        password=self.password,
                    )
                    conn.close()
                    return
                except psycopg.OperationalError:
                    time.sleep(0.5)
            raise RuntimeError("Postgres container did not become ready in time")

    with _SyncReadyPostgresContainer(
        image="postgres:16",
        username="open-wearables",
        password="open-wearables",
        dbname="agent_test",
        driver="psycopg",
    ) as pg:
        yield pg.get_connection_url()


@pytest.fixture(scope="session")
def async_engine(_postgres_url: str) -> Any:
    """Create async test engine and schema."""
    return create_async_engine(_postgres_url, pool_pre_ping=True)


@pytest.fixture(scope="session")
def event_loop_policy() -> asyncio.AbstractEventLoopPolicy:
    """Use SelectorEventLoop on Windows — psycopg3 async requires it."""
    if sys.platform == "win32":
        return asyncio.WindowsSelectorEventLoopPolicy()
    return asyncio.DefaultEventLoopPolicy()


@pytest_asyncio.fixture(scope="session")
async def _create_schema(async_engine: Any) -> AsyncGenerator[None, None]:
    """Create all tables once per session."""
    from sqlalchemy import text

    async with async_engine.begin() as conn:
        # MessageRole uses create_type=False so metadata.create_all won't create the PG enum;
        # we must create it explicitly before creating the tables.
        await conn.execute(
            text(
                "DO $$ BEGIN "
                "CREATE TYPE messagerole AS ENUM ('user', 'assistant'); "
                "EXCEPTION WHEN duplicate_object THEN NULL; "
                "END $$"
            )
        )
        await conn.run_sync(BaseDbModel.metadata.create_all)
    yield
    async with async_engine.begin() as conn:
        await conn.run_sync(BaseDbModel.metadata.drop_all)
        await conn.execute(text("DROP TYPE IF EXISTS messagerole"))


@pytest_asyncio.fixture
async def db(_create_schema: None, async_engine: Any) -> AsyncGenerator[AsyncSession, None]:
    """
    Per-test async session with savepoint-based rollback.

    The outer connection holds an open transaction that is rolled back at teardown.
    Whenever the session commits it releases a SAVEPOINT, and the sync-session event
    listener immediately opens a new one so the next operation stays within the same
    outer (never-committed) transaction.
    """
    async with async_engine.connect() as conn:
        await conn.begin()

        session_factory = async_sessionmaker(conn, class_=AsyncSession, expire_on_commit=False)
        session = session_factory()

        # Create an initial SAVEPOINT via the underlying sync session.
        session.sync_session.begin_nested()

        @event.listens_for(session.sync_session, "after_transaction_end")
        def _restart_savepoint(sync_session: Any, transaction: Any) -> None:
            # After each SAVEPOINT is released (on flush/commit), open a new one so
            # subsequent writes stay inside the outer rollback-able transaction.
            if transaction.nested and not transaction._parent.nested:
                sync_session.begin_nested()

        try:
            yield session
        finally:
            await session.close()
            await conn.rollback()


@pytest.fixture(autouse=True)
def set_factory_session(db: AsyncSession) -> Generator[None, None, None]:
    """Inject the per-test DB session into all factories."""
    for name in dir(factories):
        obj = getattr(factories, name)
        if isinstance(obj, type) and hasattr(obj, "_meta") and hasattr(obj._meta, "sqlalchemy_session"):
            obj._meta.sqlalchemy_session = db
    yield
    for name in dir(factories):
        obj = getattr(factories, name)
        if isinstance(obj, type) and hasattr(obj, "_meta") and hasattr(obj._meta, "sqlalchemy_session"):
            obj._meta.sqlalchemy_session = None


# ---------------------------------------------------------------------------
# FastAPI TestClient
# ---------------------------------------------------------------------------


@pytest.fixture
def client(db: AsyncSession) -> Generator[TestClient, None, None]:
    """TestClient with async DB dependency overridden."""
    from app.main import api

    async def override_db() -> AsyncGenerator[AsyncSession, None]:
        yield db

    api.dependency_overrides[_get_async_db_dependency] = override_db

    with TestClient(api) as c:
        yield c

    api.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def user_id() -> Any:
    return uuid4()


@pytest.fixture
def auth_token(user_id: Any) -> str:
    """Generate a valid JWT for the test user."""
    payload = {
        "sub": str(user_id),
        "exp": int((datetime(2099, 1, 1, tzinfo=timezone.utc)).timestamp()),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


@pytest.fixture
def auth_headers(auth_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {auth_token}"}


# ---------------------------------------------------------------------------
# Global autouse mocks
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def mock_validate_llm_config() -> Generator[None, None, None]:
    """Suppress LLM provider validation so tests never need a real API key."""
    with patch("app.main.validate_llm_config"):
        yield


@pytest.fixture(autouse=True)
def mock_celery(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Prevent Celery tasks from actually dispatching."""
    mock_task = MagicMock()
    mock_task.delay.return_value = MagicMock(id="test-task-id")
    mock_task.apply_async.return_value = MagicMock(id="test-task-id")

    with (
        patch("app.integrations.celery.tasks.process_message.process_message", mock_task),
        patch("app.api.routes.v1.chat.process_message", mock_task),
    ):
        yield mock_task


@pytest.fixture(autouse=True)
def mock_llm() -> Generator[dict[str, MagicMock], None, None]:
    """Mock pygentic-ai graph and pydantic-ai Agent to avoid real LLM calls."""
    mock_run_result = MagicMock()
    mock_run_result.output = "This is a test assistant response."

    mock_graph_run = AsyncMock(return_value=mock_run_result)

    mock_pydantic_agent = MagicMock()
    mock_pydantic_agent.run = AsyncMock(return_value=mock_run_result)

    with (
        patch(
            "app.agent.workflows.agent_workflow.user_assistant_graph.run",
            mock_graph_run,
        ) as mock_graph,
        patch(
            "pydantic_ai.Agent",
            return_value=mock_pydantic_agent,
        ) as mock_summarizer,
    ):
        yield {
            "agent": mock_pydantic_agent,
            "graph_run": mock_graph,
            "summarizer": mock_summarizer,
            "run_result": mock_run_result,
        }


@pytest.fixture(autouse=True)
def mock_ow_client() -> Generator[MagicMock, None, None]:
    """Mock the OW backend REST client."""
    with patch("app.integrations.ow_backend.client.ow_client") as mock:
        mock.get_user_profile = AsyncMock(return_value={"id": str(uuid4()), "first_name": "Test"})
        mock.get_body_summary = AsyncMock(return_value={"slow_changing": {}, "averaged": {}})
        mock.get_activity_summaries = AsyncMock(return_value={"data": []})
        mock.get_sleep_summaries = AsyncMock(return_value={"data": []})
        mock.get_recovery_summaries = AsyncMock(return_value={"data": []})
        mock.get_workout_events = AsyncMock(return_value={"data": []})
        mock.get_sleep_events = AsyncMock(return_value={"data": []})
        mock.get_timeseries = AsyncMock(return_value={"data": []})
        yield mock
