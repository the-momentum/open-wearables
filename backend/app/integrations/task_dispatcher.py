import base64
import importlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

import httpx
from celery import current_app as current_celery_app

from app.config import settings
from app.integrations.google_auth import get_google_access_token
from app.services.task_payload_storage import store_task_payload

_CLOUD_TASKS_API_BASE_URL = "https://cloudtasks.googleapis.com/v2"
_BYTES_MARKER = "__open_wearables_bytes__"


class TaskDispatchBackend(str, Enum):
    CELERY = "celery"
    CLOUD_TASKS = "cloud_tasks"


class RegisteredTask(str, Enum):
    CHECK_GARMIN_TRIGGERED_TIMEOUT = "check_garmin_triggered_timeout"
    FINALIZE_STALE_SLEEPS = "finalize_stale_sleeps"
    GC_STUCK_BACKFILLS = "gc_stuck_backfills"
    POLL_SQS_TASK = "poll_sqs_task"
    PROCESS_AWS_UPLOAD = "process_aws_upload"
    PROCESS_SDK_UPLOAD = "process_sdk_upload"
    PROCESS_SDK_UPLOAD_REFERENCE = "process_sdk_upload_reference"
    PROCESS_XML_UPLOAD = "process_xml_upload"
    PROCESS_XML_UPLOAD_REFERENCE = "process_xml_upload_reference"
    SEND_INVITATION_EMAIL = "send_invitation_email"
    START_GARMIN_FULL_BACKFILL = "start_garmin_full_backfill"
    SYNC_ALL_USERS = "sync_all_users"
    SYNC_VENDOR_DATA = "sync_vendor_data"
    TRIGGER_GARMIN_BACKFILL_FOR_TYPE = "trigger_garmin_backfill_for_type"
    TRIGGER_GARMIN_NEXT_PENDING_TYPE = "trigger_garmin_next_pending_type"


@dataclass(frozen=True)
class TaskDefinition:
    task_name: str
    callable_path: str
    celery_queue: str = "default"
    cloud_tasks_queue: str = "default"


@dataclass(frozen=True)
class TaskDispatchHandle:
    id: str | None
    backend: TaskDispatchBackend
    target: str


TASK_DEFINITIONS: dict[RegisteredTask, TaskDefinition] = {
    RegisteredTask.CHECK_GARMIN_TRIGGERED_TIMEOUT: TaskDefinition(
        task_name="app.integrations.celery.tasks.garmin_backfill_task.check_triggered_timeout",
        callable_path="app.integrations.celery.tasks.garmin_backfill_task.check_triggered_timeout",
        cloud_tasks_queue="garmin_backfill",
    ),
    RegisteredTask.FINALIZE_STALE_SLEEPS: TaskDefinition(
        task_name="app.integrations.celery.tasks.finalize_stale_sleep_task.finalize_stale_sleeps",
        callable_path="app.integrations.celery.tasks.finalize_stale_sleep_task.finalize_stale_sleeps",
    ),
    RegisteredTask.GC_STUCK_BACKFILLS: TaskDefinition(
        task_name="app.integrations.celery.tasks.garmin_gc_task.gc_stuck_backfills",
        callable_path="app.integrations.celery.tasks.garmin_gc_task.gc_stuck_backfills",
    ),
    RegisteredTask.POLL_SQS_TASK: TaskDefinition(
        task_name="app.integrations.celery.tasks.poll_sqs_task.poll_sqs_task",
        callable_path="app.integrations.celery.tasks.poll_sqs_task.poll_sqs_task",
    ),
    RegisteredTask.PROCESS_AWS_UPLOAD: TaskDefinition(
        task_name="app.integrations.celery.tasks.process_aws_upload_task.process_aws_upload",
        callable_path="app.integrations.celery.tasks.process_aws_upload_task.process_aws_upload",
    ),
    RegisteredTask.PROCESS_SDK_UPLOAD: TaskDefinition(
        task_name="app.integrations.celery.tasks.process_sdk_upload_task.process_sdk_upload",
        callable_path="app.integrations.celery.tasks.process_sdk_upload_task.process_sdk_upload",
        celery_queue="sdk_sync",
        cloud_tasks_queue="sdk_sync",
    ),
    RegisteredTask.PROCESS_SDK_UPLOAD_REFERENCE: TaskDefinition(
        task_name="app.integrations.celery.tasks.process_sdk_upload_reference_task.process_sdk_upload_reference",
        callable_path="app.integrations.celery.tasks.process_sdk_upload_reference_task.process_sdk_upload_reference",
        celery_queue="sdk_sync",
        cloud_tasks_queue="sdk_sync",
    ),
    RegisteredTask.PROCESS_XML_UPLOAD: TaskDefinition(
        task_name="app.integrations.celery.tasks.process_xml_upload_task.process_xml_upload",
        callable_path="app.integrations.celery.tasks.process_xml_upload_task.process_xml_upload",
    ),
    RegisteredTask.PROCESS_XML_UPLOAD_REFERENCE: TaskDefinition(
        task_name="app.integrations.celery.tasks.process_xml_upload_reference_task.process_xml_upload_reference",
        callable_path="app.integrations.celery.tasks.process_xml_upload_reference_task.process_xml_upload_reference",
    ),
    RegisteredTask.SEND_INVITATION_EMAIL: TaskDefinition(
        task_name="app.integrations.celery.tasks.send_email_task.send_invitation_email_task",
        callable_path="app.integrations.celery.tasks.send_email_task.send_invitation_email_task",
    ),
    RegisteredTask.START_GARMIN_FULL_BACKFILL: TaskDefinition(
        task_name="app.integrations.celery.tasks.garmin_backfill_task.start_full_backfill",
        callable_path="app.integrations.celery.tasks.garmin_backfill_task.start_full_backfill",
        cloud_tasks_queue="garmin_backfill",
    ),
    RegisteredTask.SYNC_ALL_USERS: TaskDefinition(
        task_name="app.integrations.celery.tasks.periodic_sync_task.sync_all_users",
        callable_path="app.integrations.celery.tasks.periodic_sync_task.sync_all_users",
    ),
    RegisteredTask.SYNC_VENDOR_DATA: TaskDefinition(
        task_name="app.integrations.celery.tasks.sync_vendor_data_task.sync_vendor_data",
        callable_path="app.integrations.celery.tasks.sync_vendor_data_task.sync_vendor_data",
    ),
    RegisteredTask.TRIGGER_GARMIN_BACKFILL_FOR_TYPE: TaskDefinition(
        task_name="app.integrations.celery.tasks.garmin_backfill_task.trigger_backfill_for_type",
        callable_path="app.integrations.celery.tasks.garmin_backfill_task.trigger_backfill_for_type",
        cloud_tasks_queue="garmin_backfill",
    ),
    RegisteredTask.TRIGGER_GARMIN_NEXT_PENDING_TYPE: TaskDefinition(
        task_name="app.integrations.celery.tasks.garmin_backfill_task.trigger_next_pending_type",
        callable_path="app.integrations.celery.tasks.garmin_backfill_task.trigger_next_pending_type",
        cloud_tasks_queue="garmin_backfill",
    ),
}


def dispatch_task(
    task: RegisteredTask | str,
    *,
    args: list[Any] | None = None,
    kwargs: dict[str, Any] | None = None,
    countdown: int | None = None,
) -> TaskDispatchHandle:
    task_key = _normalize_task(task)
    task_args = args or []
    task_kwargs = kwargs or {}
    backend = TaskDispatchBackend(settings.task_dispatch_backend)

    # Automatic offloading for large payloads
    task_key, task_kwargs = _maybe_offload_payload(task_key, task_kwargs)

    definition = TASK_DEFINITIONS[task_key]

    if backend is TaskDispatchBackend.CELERY:
        result = current_celery_app.send_task(
            definition.task_name,
            args=task_args,
            kwargs=task_kwargs,
            countdown=countdown,
            queue=definition.celery_queue,
        )
        return TaskDispatchHandle(id=result.id, backend=backend, target=definition.task_name)

    if backend is TaskDispatchBackend.CLOUD_TASKS:
        return _dispatch_cloud_task(
            definition=definition,
            task_key=task_key,
            args=task_args,
            kwargs=task_kwargs,
            countdown=countdown,
        )

    raise ValueError(f"Unsupported task dispatch backend: {settings.task_dispatch_backend}")


def _maybe_offload_payload(task_key: RegisteredTask, kwargs: dict[str, Any]) -> tuple[RegisteredTask, dict[str, Any]]:
    """Automatically offload large payloads to storage and switch to reference tasks."""
    # Map of standard tasks to their reference-aware counterparts and the key to offload
    offload_map = {
        RegisteredTask.PROCESS_XML_UPLOAD: (
            "file_contents",
            RegisteredTask.PROCESS_XML_UPLOAD_REFERENCE,
            "application/xml",
            "apple-xml",
        ),
        RegisteredTask.PROCESS_SDK_UPLOAD: (
            "content",
            RegisteredTask.PROCESS_SDK_UPLOAD_REFERENCE,
            "application/json",
            "sdk-sync",
        ),
    }

    if task_key not in offload_map:
        return task_key, kwargs

    payload_key, ref_task_key, content_type, prefix = offload_map[task_key]
    payload = kwargs.get(payload_key)

    if not payload:
        return task_key, kwargs

    # Convert string to bytes if needed
    payload_bytes = payload.encode("utf-8") if isinstance(payload, str) else payload

    if len(payload_bytes) <= settings.task_payload_inline_max_bytes:
        return task_key, kwargs

    # Payload too large, store it
    payload_ref = store_task_payload(
        payload_bytes,
        content_type=content_type,
        prefix=prefix,
        filename=kwargs.get("filename") or f"{kwargs.get('batch_id', 'payload')}.data",
    )

    # Create new kwargs for the reference task
    new_kwargs = {k: v for k, v in kwargs.items() if k != payload_key}
    new_kwargs["payload_reference"] = payload_ref

    return ref_task_key, new_kwargs


def invoke_registered_task(
    task: RegisteredTask | str,
    *,
    args: list[Any] | None = None,
    kwargs: dict[str, Any] | None = None,
) -> Any:
    task_key = _normalize_task(task)
    definition = TASK_DEFINITIONS[task_key]
    module_name, attribute_name = definition.callable_path.rsplit(".", 1)
    module = importlib.import_module(module_name)
    task_callable = getattr(module, attribute_name)
    return task_callable(*(args or []), **(kwargs or {}))


def serialize_payload(value: Any) -> Any:
    if isinstance(value, bytes):
        return {_BYTES_MARKER: base64.b64encode(value).decode("ascii")}
    if isinstance(value, tuple):
        return [serialize_payload(item) for item in value]
    if isinstance(value, list):
        return [serialize_payload(item) for item in value]
    if isinstance(value, dict):
        return {key: serialize_payload(item) for key, item in value.items()}
    return value


def deserialize_payload(value: Any) -> Any:
    if isinstance(value, list):
        return [deserialize_payload(item) for item in value]
    if isinstance(value, dict):
        if _BYTES_MARKER in value and len(value) == 1:
            return base64.b64decode(value[_BYTES_MARKER])
        return {key: deserialize_payload(item) for key, item in value.items()}
    return value


def _dispatch_cloud_task(
    *,
    definition: TaskDefinition,
    task_key: RegisteredTask,
    args: list[Any],
    kwargs: dict[str, Any],
    countdown: int | None,
) -> TaskDispatchHandle:
    project_id = _require_setting(settings.task_dispatcher_gcp_project_id, "task_dispatcher_gcp_project_id")
    location = _require_setting(settings.task_dispatcher_gcp_location, "task_dispatcher_gcp_location")
    worker_base_url = _require_setting(settings.task_dispatcher_worker_base_url, "task_dispatcher_worker_base_url")
    service_account_email = _require_setting(
        settings.task_dispatcher_service_account_email,
        "task_dispatcher_service_account_email",
    )

    queue_name = _resolve_cloud_tasks_queue_name(definition.cloud_tasks_queue)
    audience = settings.task_dispatcher_audience or worker_base_url
    target_url = f"{worker_base_url.rstrip('/')}{settings.api_v1}/internal/tasks/{task_key.value}"
    request_body = json.dumps(
        {
            "args": serialize_payload(args),
            "kwargs": serialize_payload(kwargs),
        }
    ).encode("utf-8")

    task_request: dict[str, Any] = {
        "task": {
            "httpRequest": {
                "httpMethod": "POST",
                "url": target_url,
                "headers": {
                    "Content-Type": "application/json",
                },
                "body": base64.b64encode(request_body).decode("ascii"),
                "oidcToken": {
                    "serviceAccountEmail": service_account_email,
                    "audience": audience,
                },
            }
        }
    }

    if countdown:
        task_request["task"]["scheduleTime"] = (
            (datetime.now(timezone.utc) + timedelta(seconds=countdown)).isoformat().replace("+00:00", "Z")
        )

    access_token = get_google_access_token()
    response = httpx.post(
        f"{_CLOUD_TASKS_API_BASE_URL}/projects/{project_id}/locations/{location}/queues/{queue_name}/tasks",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        json=task_request,
        timeout=10.0,
    )
    response.raise_for_status()
    response_json = response.json()

    return TaskDispatchHandle(
        id=response_json.get("name"),
        backend=TaskDispatchBackend.CLOUD_TASKS,
        target=target_url,
    )


def _normalize_task(task: RegisteredTask | str) -> RegisteredTask:
    if isinstance(task, RegisteredTask):
        return task
    return RegisteredTask(task)


def _require_setting(value: str | None, setting_name: str) -> str:
    if not value:
        raise ValueError(f"{setting_name} must be configured when TASK_DISPATCH_BACKEND=cloud_tasks")
    return value


def _resolve_cloud_tasks_queue_name(queue_key: str) -> str:
    queue_names = {
        "default": settings.task_dispatcher_default_queue_name,
        "sdk_sync": settings.task_dispatcher_sdk_sync_queue_name,
        "garmin_backfill": settings.task_dispatcher_garmin_backfill_queue_name,
    }
    try:
        return queue_names[queue_key]
    except KeyError as exc:
        raise ValueError(f"Unsupported Cloud Tasks queue key: {queue_key}") from exc
