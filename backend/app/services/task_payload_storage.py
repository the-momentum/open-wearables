from pathlib import Path
from typing import TypedDict
from urllib.parse import quote
from uuid import uuid4

import httpx

from app.config import settings
from app.integrations.google_auth import get_google_access_token

_GCS_UPLOAD_URL_TEMPLATE = "https://storage.googleapis.com/upload/storage/v1/b/{bucket}/o"
_GCS_OBJECT_URL_TEMPLATE = "https://storage.googleapis.com/storage/v1/b/{bucket}/o/{object_name}"


class TaskPayloadReference(TypedDict):
    backend: str
    locator: str
    bucket: str | None


def store_task_payload(
    payload: bytes,
    *,
    content_type: str,
    prefix: str,
    filename: str | None = None,
) -> TaskPayloadReference:
    backend = settings.task_payload_storage_backend
    suffix = Path(filename or "").suffix
    payload_id = f"{uuid4()}{suffix}"

    if backend == "filesystem":
        payload_dir = Path(settings.task_payload_local_dir) / prefix
        payload_dir.mkdir(parents=True, exist_ok=True)
        payload_path = payload_dir / payload_id
        payload_path.write_bytes(payload)
        return {
            "backend": "filesystem",
            "locator": str(payload_path),
            "bucket": None,
        }

    if backend == "gcs":
        if not settings.task_payload_gcs_bucket:
            raise ValueError("TASK_PAYLOAD_GCS_BUCKET must be set when TASK_PAYLOAD_STORAGE_BACKEND=gcs")

        object_name = "/".join(
            part.strip("/") for part in [settings.task_payload_gcs_prefix, prefix, payload_id] if part
        )
        access_token = get_google_access_token()
        response = httpx.post(
            _GCS_UPLOAD_URL_TEMPLATE.format(bucket=settings.task_payload_gcs_bucket),
            params={
                "uploadType": "media",
                "name": object_name,
            },
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": content_type,
            },
            content=payload,
            timeout=30.0,
        )
        response.raise_for_status()
        return {
            "backend": "gcs",
            "locator": object_name,
            "bucket": settings.task_payload_gcs_bucket,
        }

    raise ValueError("Large payload offload requires TASK_PAYLOAD_STORAGE_BACKEND to be set to filesystem or gcs")


def load_task_payload(reference: TaskPayloadReference) -> bytes:
    if reference["backend"] == "filesystem":
        return Path(reference["locator"]).read_bytes()

    if reference["backend"] == "gcs":
        if not reference["bucket"]:
            raise ValueError("Task payload reference bucket is required for GCS payloads")

        access_token = get_google_access_token()
        url = _GCS_OBJECT_URL_TEMPLATE.format(
            bucket=reference["bucket"],
            object_name=quote(reference["locator"], safe=""),
        )
        response = httpx.get(
            f"{url}?alt=media",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30.0,
        )
        response.raise_for_status()
        return response.content

    raise ValueError(f"Unsupported task payload backend: {reference['backend']}")


def delete_task_payload(reference: TaskPayloadReference) -> None:
    if reference["backend"] == "filesystem":
        Path(reference["locator"]).unlink(missing_ok=True)
        return

    if reference["backend"] == "gcs":
        if not reference["bucket"]:
            return

        access_token = get_google_access_token()
        response = httpx.delete(
            _GCS_OBJECT_URL_TEMPLATE.format(
                bucket=reference["bucket"], object_name=quote(reference["locator"], safe="")
            ),
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30.0,
        )
        response.raise_for_status()
        return

    raise ValueError(f"Unsupported task payload backend: {reference['backend']}")
