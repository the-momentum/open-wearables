"""Tests for the sync status SSE / history API endpoints."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from fastapi.dependencies.models import Dependant
from fastapi.dependencies.utils import get_dependant
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import app.services.sync_status_service as sync_status_service
from app.api.routes.v1.sync_status import (
    _ensure_user_exists_detached,
    list_recent_sync_events,
    stream_user_sync_status,
)
from app.database import _get_db_dependency
from app.schemas.sync_status import SyncScope, SyncSource, SyncStage, SyncStatus, SyncStatusEvent
from app.services.api_key_service import _require_api_key, _require_api_key_detached
from tests.factories import UserFactory


def _dependency_calls(endpoint: Callable) -> list:
    """Every dependency an endpoint resolves, nested ones included.

    Built the way FastAPI builds it for the route, so the answer is the one the framework
    acts on rather than a re-reading of the signature.
    """
    calls: list = []

    def walk(dependant: Dependant) -> None:
        for sub in dependant.dependencies:
            calls.append(sub.call)
            walk(sub)

    walk(get_dependant(path="/", call=endpoint))
    return calls


def _emit(user_id: UUID, *, run_id: str | None = None) -> SyncStatusEvent:
    event = SyncStatusEvent(
        run_id=run_id or sync_status_service.new_run_id(),
        user_id=user_id,
        provider="garmin",
        source=SyncSource.PULL,
        stage=SyncStage.STARTED,
        status=SyncStatus.IN_PROGRESS,
    )
    sync_status_service.emit(event)
    return event


class TestRecentEndpoint:
    def test_returns_recent_events_newest_first(
        self,
        client: TestClient,
        api_key_header: dict[str, str],
    ) -> None:
        user = UserFactory()
        first = _emit(user.id)
        second = _emit(user.id)

        response = client.get(
            f"/api/v1/users/{user.id}/sync/recent",
            headers=api_key_header,
        )
        assert response.status_code == 200
        body = response.json()
        assert [e["run_id"] for e in body[:2]] == [second.run_id, first.run_id]

    def test_returns_empty_for_user_with_no_events(
        self,
        client: TestClient,
        api_key_header: dict[str, str],
    ) -> None:
        user = UserFactory()
        response = client.get(
            f"/api/v1/users/{user.id}/sync/recent",
            headers=api_key_header,
        )
        assert response.status_code == 200
        assert response.json() == []

    def test_404_for_unknown_user(
        self,
        client: TestClient,
        api_key_header: dict[str, str],
    ) -> None:
        response = client.get(
            f"/api/v1/users/{uuid4()}/sync/recent",
            headers=api_key_header,
        )
        assert response.status_code == 404

    def test_unauthorized_without_api_key(self, client: TestClient) -> None:
        user = UserFactory()
        response = client.get(f"/api/v1/users/{user.id}/sync/recent")
        assert response.status_code in (401, 403)


class TestRunsEndpoint:
    def test_aggregates_per_run(
        self,
        client: TestClient,
        api_key_header: dict[str, str],
    ) -> None:
        user = UserFactory()
        run_id = sync_status_service.new_run_id()
        _emit(user.id, run_id=run_id)
        sync_status_service.emit_sync_completed(
            user.id,
            "garmin",
            SyncSource.PULL,
            run_id=run_id,
            status=SyncStatus.SUCCESS,
        )

        response = client.get(
            f"/api/v1/users/{user.id}/sync/runs",
            headers=api_key_header,
        )
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["run_id"] == run_id
        assert body[0]["status"] == SyncStatus.SUCCESS.value


# Note: The actual streaming endpoint behaviour (replay + heartbeat + pubsub
# forwarding) is exercised against the underlying generator in
# tests/services/test_sync_status_service.py — TestClient.stream + a
# long-lived generator interact poorly with pytest's lifespan fixtures.


class TestHistoryEndpointFilters:
    """The drill-down from a gap in the data to the run that was meant to cover it."""

    def _persist(self, user_id: UUID, run_key: str, provider: str, window: tuple | None) -> None:
        window_start, window_end = window or (None, None)
        sync_status_service.try_persist_run(
            SyncStatusEvent(
                run_id=run_key,
                user_id=user_id,
                provider=provider,
                source=SyncSource.BACKFILL,
                scope=SyncScope.HISTORICAL,
                stage=SyncStage.STARTED,
                status=SyncStatus.IN_PROGRESS,
                started_at=datetime.now(timezone.utc),
                window_start=window_start,
                window_end=window_end,
            )
        )

    @patch("app.services.sync_status_service.SessionLocal")
    def test_filters_by_provider_and_covered_window(
        self,
        mock_session_local: MagicMock,
        client: TestClient,
        api_key_header: dict[str, str],
        db: Session,
    ) -> None:
        mock_session_local.return_value.__enter__.return_value = db
        user = UserFactory()
        march = (datetime(2026, 3, 1, tzinfo=timezone.utc), datetime(2026, 4, 1, tzinfo=timezone.utc))
        january = (datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2026, 2, 1, tzinfo=timezone.utc))
        self._persist(user.id, "garmin_march", "garmin", march)
        self._persist(user.id, "garmin_january", "garmin", january)
        self._persist(user.id, "oura_march", "oura", march)

        response = client.get(
            f"/api/v1/users/{user.id}/sync/history",
            headers=api_key_header,
            params={
                "provider": "garmin",
                "covered_from": "2026-03-10T00:00:00Z",
                "covered_to": "2026-03-20T00:00:00Z",
            },
        )

        assert response.status_code == 200
        assert [r["run_key"] for r in response.json()] == ["garmin_march"]


class TestStreamHoldsNoDbSession:
    """A stream must not park a pooled connection for as long as the client stays connected."""

    def test_no_dependency_of_the_stream_declares_the_request_session(self) -> None:
        """DbSession is a yield dependency, released only once the response completes.

        For an SSE response that is at client disconnect, so ~50 open admin tabs would take
        the whole pool. The non-streaming sibling is checked too, so a broken walk over the
        dependency tree cannot make this pass by accident.
        """
        stream_deps = _dependency_calls(stream_user_sync_status)
        assert _get_db_dependency not in stream_deps
        assert _require_api_key not in stream_deps
        assert _require_api_key_detached in stream_deps

        assert _get_db_dependency in _dependency_calls(list_recent_sync_events)

    def test_checks_the_user_without_the_request_session(self, db: Session) -> None:
        user = UserFactory()
        with patch("app.api.routes.v1.sync_status.SessionLocal") as mock_session_local:
            mock_session_local.return_value.__enter__.return_value = db
            _ensure_user_exists_detached(user.id)
            with pytest.raises(HTTPException) as exc_info:
                _ensure_user_exists_detached(uuid4())
        assert exc_info.value.status_code == 404
