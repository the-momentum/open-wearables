from typing import Any, cast

from app.integrations.celery.tasks.process_xml_upload_task import process_xml_upload
from app.services.task_payload_storage import TaskPayloadReference, delete_task_payload, load_task_payload
from celery import shared_task


@shared_task
def process_xml_upload_reference(
    payload_reference: dict[str, Any],
    filename: str,
    user_id: str,
) -> dict[str, Any]:
    try:
        file_contents = load_task_payload(cast(TaskPayloadReference, payload_reference))
        return process_xml_upload(
            file_contents=file_contents,
            filename=filename,
            user_id=user_id,
        )
    finally:
        delete_task_payload(cast(TaskPayloadReference, payload_reference))
