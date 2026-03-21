from typing import Any, cast

from app.integrations.celery.tasks.process_sdk_upload_task import process_sdk_upload
from app.services.task_payload_storage import TaskPayloadReference, delete_task_payload, load_task_payload
from celery import shared_task


@shared_task(queue="sdk_sync")
def process_sdk_upload_reference(
    payload_reference: dict[str, Any],
    content_type: str,
    user_id: str,
    provider: str,
    batch_id: str | None = None,
) -> dict[str, int | str]:
    try:
        content = load_task_payload(cast(TaskPayloadReference, payload_reference)).decode("utf-8")
        return process_sdk_upload(
            content=content,
            content_type=content_type,
            user_id=user_id,
            provider=provider,
            batch_id=batch_id,
        )
    finally:
        delete_task_payload(cast(TaskPayloadReference, payload_reference))
