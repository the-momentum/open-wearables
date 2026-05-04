"""Tests for the sync status service.

Verifies persistence (Redis history & runs), terminal-event Svix
dispatch, and the SSE replay/streaming generator.
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Generator
from unittest.mock import patch
from uuid import uuid4

import pytest

import app.services.sync_status_service as sync_status_service
from app.integrations.redis_client import get_redis_client
from app.schemas.sync_status import SyncSource, SyncStage, SyncStatus, SyncStatusEvent


@pytest.fixture
def user_id() -> str:
    return str(uuid4())


def _build_event(
    user_id: str,
    *,
    stage: SyncStage = SyncStage.STARTED,
    status: SyncStatus = SyncStatus.IN_PROGRESS,
    run_id: str | None = None,
) -> SyncStatusEvent:
    return SyncStatusEvent(
        run_id=run_id or sync_status_service.new_run_id(),
        user_id=user_id,
        provider="garmin",
        source=SyncSource.PULL,
        stage=stage,
        status=status,
    )


class TestEmitAndPersist:
    def test_emit_persists_event_in_recent_list(self, user_id: str) -> None:
        event = _build_event(user_id)
        sync_status_service.emit(event)

        recent = sync_status_service.get_recent_events(user_id)
        assert len(recent) == 1
        assert recent[0].run_id == event.run_id
        assert recent[0].user_id == event.user_id

    def test_get_recent_events_returns_newest_first(self, user_id: str) -> None:
        first = _build_event(user_id)
        second = _build_event(user_id)
        sync_status_service.emit(first)
        time.sleep(0.005)
        sync_status_service.emit(second)

        recent = sync_status_service.get_recent_events(user_id, limit=10)
        assert [e.run_id for e in recent] == [second.run_id, first.run_id]

    def test_recent_list_is_capped(self, user_id: str) -> None:
        with patch.object(sync_status_service, "MAX_RECENT_EVENTS", 5):
            for _ in range(8):
                sync_status_service.emit(_build_event(user_id))
            recent = sync_status_service.get_recent_events(user_id, limit=20)
            assert len(recent) == 5

    def test_run_summaries_aggregate_per_run(self, user_id: str) -> None:
        run_id = sync_status_service.new_run_id()
        sync_status_service.emit(_build_event(user_id, run_id=run_id, stage=SyncStage.STARTED))
        sync_status_service.emit(
            _build_event(user_id, run_id=run_id, stage=SyncStage.PROCESSING),
        )
        sync_status_service.emit(
            _build_event(
                user_id,
                run_id=run_id,
                stage=SyncStage.COMPLETED,
                status=SyncStatus.SUCCESS,
            ),
        )

        summaries = sync_status_service.get_run_summaries(user_id)
        assert len(summaries) == 1
        summary = summaries[0]
        assert summary.run_id == run_id
        assert summary.stage == SyncStage.COMPLETED.value
        assert summary.status == SyncStatus.SUCCESS.value


class TestTerminalSvixDispatch:
    @pytest.fixture
    def mock_outgoing(self) -> Generator[dict[str, object], None, None]:
        with (
            patch("app.services.outgoing_webhooks.events.on_sync_started") as started,
            patch("app.services.outgoing_webhooks.events.on_sync_completed") as completed,
            patch("app.services.outgoing_webhooks.events.on_sync_failed") as failed,
        ):
            yield {"started": started, "completed": completed, "failed": failed}

    def test_started_dispatches_outgoing_started(
        self,
        user_id: str,
        mock_outgoing: dict[str, object],
    ) -> None:
        sync_status_service.started(user_id, "garmin", SyncSource.PULL, run_id="run_a")
        mock_outgoing["started"].assert_called_once()

    def test_completed_dispatches_outgoing_completed(
        self,
        user_id: str,
        mock_outgoing: dict[str, object],
    ) -> None:
        sync_status_service.completed(user_id, "garmin", SyncSource.PULL, run_id="run_b")
        mock_outgoing["completed"].assert_called_once()

    def test_failed_dispatches_outgoing_failed(
        self,
        user_id: str,
        mock_outgoing: dict[str, object],
    ) -> None:
        sync_status_service.failed(user_id, "garmin", SyncSource.PULL, run_id="run_c", error="boom")
        mock_outgoing["failed"].assert_called_once()

    def test_progress_does_not_fire_outgoing_webhook(
        self,
        user_id: str,
        mock_outgoing: dict[str, object],
    ) -> None:
        sync_status_service.progress(user_id, "garmin", SyncSource.PULL, run_id="run_d")
        for mock in mock_outgoing.values():
            mock.assert_not_called()


class TestStreamUserEvents:
    def test_stream_replays_recent_events(self, user_id: str) -> None:
        sync_status_service.emit(_build_event(user_id))
        sync_status_service.emit(_build_event(user_id))

        gen = sync_status_service.stream_user_events(user_id, replay_last=2)
        chunks: list[str] = []
        # First chunk is the connect comment, then two replayed events
        for _ in range(3):
            chunks.append(next(gen))

        assert chunks[0].startswith(":")  # connected comment
        assert "event: sync.status" in chunks[1]
        assert "event: sync.status" in chunks[2]

    def test_stream_forwards_published_events(self, user_id: str) -> None:
        stop = threading.Event()
        gen = sync_status_service.stream_user_events(user_id, replay_last=0, stop_event=stop)
        # Drain initial connect comment
        next(gen)

        # Publish from another "process"
        run_id = sync_status_service.new_run_id()
        sync_status_service.emit(_build_event(user_id, run_id=run_id))

        chunk: str | None = None
        deadline = time.time() + 3.0
        while time.time() < deadline:
            value = next(gen)
            if "event: sync.status" in value:
                chunk = value
                break
        stop.set()

        assert chunk is not None
        # The data line carries JSON
        data_lines = [line[len("data: ") :] for line in chunk.splitlines() if line.startswith("data: ")]
        assert data_lines
        decoded = json.loads(data_lines[0])
        assert decoded["run_id"] == run_id


class TestEmitResilientToRedisFailure:
    def test_emit_swallows_redis_errors(self, user_id: str) -> None:
        with patch.object(sync_status_service, "get_redis_client") as mock:
            mock.side_effect = RuntimeError("redis down")
            # Should not raise
            sync_status_service.emit(_build_event(user_id))


class TestRedisHistoryTtl:
    def test_keys_have_expiry_set(self, user_id: str) -> None:
        sync_status_service.emit(_build_event(user_id))
        client = get_redis_client()
        ttl = client.ttl(f"sync:status:user:{user_id}:recent")
        assert ttl is not None
        assert int(ttl) > 0
