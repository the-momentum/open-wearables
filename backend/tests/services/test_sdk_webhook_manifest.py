from datetime import datetime
from unittest.mock import patch
from uuid import uuid4

from app.services.outgoing_webhooks.events import on_sleep_created, on_timeseries_batch_saved
from app.services.sdk_ingestion_context import sdk_ingestion_context


def test_sdk_manifest_is_added_to_timeseries_and_event_webhooks() -> None:
    manifest = {
        "client_sync_id": "sync-123",
        "batch_id": "batch-9",
        "chunk_index": 4,
    }
    with patch("app.services.outgoing_webhooks.events._dispatch") as dispatch:
        on_timeseries_batch_saved(
            user_id=uuid4(),
            provider="apple",
            series_type="heart_rate",
            sample_count=1,
            samples=[{"timestamp": "2026-09-02T12:00:00Z", "value": 61}],
            sync_manifest=manifest,
        )
        with sdk_ingestion_context(manifest):
            on_sleep_created(
                record_id=uuid4(),
                user_id=uuid4(),
                provider="apple",
                device="iPhone",
                start_time="2026-09-01T23:00:00Z",
                end_time="2026-09-02T07:00:00Z",
                zone_offset="+08:00",
                duration_seconds=28_800,
            )

    assert dispatch.call_count >= 2
    for call in dispatch.call_args_list:
        payload_data = call.args[1]["data"]
        assert payload_data["client_sync_id"] == "sync-123"
        assert payload_data["batch_id"] == "batch-9"
        assert payload_data["client_chunk_index"] == 4


def test_dispatch_stamps_event_creation_time() -> None:
    with (
        patch("app.services.outgoing_webhooks.events.svix_service.is_enabled", return_value=True),
        patch("app.integrations.celery.tasks.emit_webhook_event_task.emit_webhook_event.delay") as delay,
    ):
        on_sleep_created(
            record_id=uuid4(),
            user_id=uuid4(),
            provider="apple",
            device="iPhone",
            start_time="2026-09-01T23:00:00Z",
            end_time="2026-09-02T07:00:00Z",
            zone_offset="+08:00",
            duration_seconds=28_800,
        )

    payload = delay.call_args.args[1]
    assert datetime.fromisoformat(payload["event_created_at"]).tzinfo is not None
