import base64
import json
from unittest.mock import MagicMock

import pytest

from app.config import settings
from app.integrations import task_dispatcher
from app.integrations.task_dispatcher import (
    RegisteredTask,
    TaskDispatchBackend,
    deserialize_payload,
    dispatch_task,
    serialize_payload,
)


@pytest.mark.asyncio
async def test_serialize_payload_round_trips_bytes() -> None:
    payload = {
        "file_contents": b"<xml>payload</xml>",
        "items": [1, {"binary": b"abc"}],
    }

    serialized = serialize_payload(payload)

    assert serialized["file_contents"] == {"__open_wearables_bytes__": base64.b64encode(b"<xml>payload</xml>").decode("ascii")}
    assert deserialize_payload(serialized) == payload


def test_dispatch_task_uses_celery_send_task(monkeypatch: pytest.MonkeyPatch) -> None:
    send_task_mock = MagicMock()
    send_task_mock.return_value.id = "celery-task-id"

    monkeypatch.setattr(task_dispatcher.current_celery_app, "send_task", send_task_mock)
    monkeypatch.setattr(settings, "task_dispatch_backend", TaskDispatchBackend.CELERY.value)

    handle = dispatch_task(
        RegisteredTask.SYNC_VENDOR_DATA,
        kwargs={"user_id": "user-123"},
    )

    assert handle.id == "celery-task-id"
    assert handle.backend is TaskDispatchBackend.CELERY
    send_task_mock.assert_called_once_with(
        "app.integrations.celery.tasks.sync_vendor_data_task.sync_vendor_data",
        args=[],
        kwargs={"user_id": "user-123"},
        countdown=None,
        queue="default",
    )


def test_dispatch_task_uses_cloud_tasks_http_api(monkeypatch: pytest.MonkeyPatch) -> None:
    metadata_response = MagicMock()
    metadata_response.json.return_value = {"access_token": "metadata-token"}
    metadata_response.raise_for_status.return_value = None

    cloud_tasks_response = MagicMock()
    cloud_tasks_response.json.return_value = {"name": "projects/test/locations/eu/queues/default/tasks/123"}
    cloud_tasks_response.raise_for_status.return_value = None

    httpx_get_mock = MagicMock(return_value=metadata_response)
    httpx_post_mock = MagicMock(return_value=cloud_tasks_response)

    monkeypatch.setattr(task_dispatcher.httpx, "get", httpx_get_mock)
    monkeypatch.setattr(task_dispatcher.httpx, "post", httpx_post_mock)
    monkeypatch.setattr(settings, "task_dispatch_backend", TaskDispatchBackend.CLOUD_TASKS.value)
    monkeypatch.setattr(settings, "task_dispatcher_gcp_project_id", "test-project")
    monkeypatch.setattr(settings, "task_dispatcher_gcp_location", "europe-west1")
    monkeypatch.setattr(settings, "task_dispatcher_worker_base_url", "https://worker.example.run.app")
    monkeypatch.setattr(settings, "task_dispatcher_service_account_email", "api@test-project.iam.gserviceaccount.com")
    monkeypatch.setattr(settings, "task_dispatcher_audience", "https://worker.example.run.app")
    monkeypatch.setattr(settings, "task_dispatcher_default_queue_name", "ow-default")
    monkeypatch.setattr(settings, "task_dispatcher_sdk_sync_queue_name", "ow-sdk")
    monkeypatch.setattr(settings, "task_dispatcher_garmin_backfill_queue_name", "ow-garmin")

    handle = dispatch_task(
        RegisteredTask.PROCESS_XML_UPLOAD,
        kwargs={
            "file_contents": b"<xml/>",
            "filename": "payload.xml",
            "user_id": "user-123",
        },
        countdown=30,
    )

    assert handle.backend is TaskDispatchBackend.CLOUD_TASKS
    assert handle.id == "projects/test/locations/eu/queues/default/tasks/123"

    httpx_get_mock.assert_called_once()
    httpx_post_mock.assert_called_once()

    request_url = httpx_post_mock.call_args.args[0]
    request_json = httpx_post_mock.call_args.kwargs["json"]
    request_headers = httpx_post_mock.call_args.kwargs["headers"]

    assert request_url.endswith("/projects/test-project/locations/europe-west1/queues/ow-default/tasks")
    assert request_headers["Authorization"] == "Bearer metadata-token"
    assert request_json["task"]["httpRequest"]["url"] == "https://worker.example.run.app/api/v1/internal/tasks/process_xml_upload"
    assert request_json["task"]["httpRequest"]["oidcToken"]["serviceAccountEmail"] == "api@test-project.iam.gserviceaccount.com"

    raw_body = base64.b64decode(request_json["task"]["httpRequest"]["body"]).decode("utf-8")
    decoded = json.loads(raw_body)
    assert decoded["kwargs"]["filename"] == "payload.xml"
    assert decoded["kwargs"]["file_contents"]["__open_wearables_bytes__"] == base64.b64encode(b"<xml/>").decode("ascii")
