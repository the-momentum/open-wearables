"""Tests for the sync status SSE / history API endpoints."""

from __future__ import annotations

from uuid import UUID, uuid4

from fastapi.testclient import TestClient

import app.services.sync_status_service as sync_status_service
from app.schemas.sync_status import SyncSource, SyncStage, SyncStatus, SyncStatusEvent
from tests.factories import UserFactory


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
        sync_status_service.completed(
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
