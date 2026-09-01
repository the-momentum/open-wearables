import hashlib
import json
from logging import getLogger
from pathlib import Path
from typing import Any, BinaryIO
from uuid import UUID

from botocore.exceptions import ClientError
from celery import Task, shared_task
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.integrations.redis_client import get_redis_client
from app.schemas.providers.apple.apple_xml import CompletedPart
from app.schemas.sync_status import SyncSource, SyncStatus
from app.services import event_record_service
from app.services.apple.apple_xml.aws_service import get_s3_client
from app.services.apple.apple_xml.multipart_upload_service import multipart_upload_service
from app.services.apple.apple_xml.xml_service import XMLService
from app.services.apple.healthkit.sleep_service import handle_sleep_data
from app.services.sync_status_service import completed, failed, new_run_id, started
from app.services.timeseries_service import timeseries_service
from app.services.user_service import user_service
from app.utils.exceptions import ResourceNotFoundError
from app.utils.sentry_helpers import log_and_capture_error

logger = getLogger(__name__)

IMPORT_STATE_TTL_SECONDS = 7 * 24 * 60 * 60


def _import_state_key(bucket_name: str, object_key: str, user_id: str) -> str:
    identity = f"{bucket_name}\0{object_key}\0{user_id}".encode()
    return f"apple_xml:s3_import:{hashlib.sha256(identity).hexdigest()}"


def _upload_completion_key(bucket_name: str, object_key: str, user_id: str) -> str:
    return f"{_import_state_key(bucket_name, object_key, user_id)}:upload_completed"


def _upload_completion_persisted(bucket_name: str, object_key: str, user_id: str) -> bool:
    try:
        return bool(get_redis_client().get(_upload_completion_key(bucket_name, object_key, user_id)))
    except Exception:
        logger.warning("Unable to read Apple XML multipart completion marker", exc_info=True)
        return False


def _store_upload_completion(bucket_name: str, object_key: str, user_id: str) -> None:
    """Persist finalization before import processing begins.

    Retries can then skip the consumed multipart upload ID entirely. If Redis is
    temporarily unavailable, ``_ensure_upload_completed`` still recovers by checking
    whether the finalized object exists after S3 returns ``NoSuchUpload``.
    """
    try:
        get_redis_client().set(
            _upload_completion_key(bucket_name, object_key, user_id),
            "1",
            ex=IMPORT_STATE_TTL_SECONDS,
        )
    except Exception:
        logger.warning("Unable to persist Apple XML multipart completion marker", exc_info=True)


def _claim_import(
    bucket_name: str,
    object_key: str,
    user_id: str,
    run_id: str,
) -> tuple[str, dict[str, str] | None]:
    """Claim an object import, or recover its already-persisted result.

    Redis is already a required service for Celery and sync status. The marker closes
    the acknowledgement-loss window: a successfully imported object is not processed
    again if the same task is redelivered. Database uniqueness/upsert behavior still
    protects the smaller crash window between the final database write and this marker.
    """
    try:
        client = get_redis_client()
        state_key = _import_state_key(bucket_name, object_key, user_id)
        # Retry the read/SET-NX pair once if another worker races us between them.
        for _ in range(2):
            raw_state = client.get(state_key)
            if raw_state:
                state = json.loads(raw_state)
                if state.get("state") == "completed":
                    return "completed", dict(state["result"])
                if state.get("run_id") == run_id:
                    client.expire(state_key, IMPORT_STATE_TTL_SECONDS)
                    return "claimed", None
                return "processing", None

            claimed = client.set(
                state_key,
                json.dumps({"state": "processing", "run_id": run_id}),
                nx=True,
                ex=IMPORT_STATE_TTL_SECONDS,
            )
            if claimed:
                return "claimed", None
        return "processing", None
    except Exception:
        logger.warning("Unable to persist Apple XML import claim; continuing with database idempotency", exc_info=True)
        return "claimed", None


def _store_completed_import(
    bucket_name: str,
    object_key: str,
    user_id: str,
    result: dict[str, str],
) -> None:
    try:
        get_redis_client().set(
            _import_state_key(bucket_name, object_key, user_id),
            json.dumps({"state": "completed", "result": result}),
            ex=IMPORT_STATE_TTL_SECONDS,
        )
    except Exception:
        logger.warning("Unable to persist completed Apple XML import marker", exc_info=True)


def _release_import_claim(bucket_name: str, object_key: str, user_id: str, run_id: str) -> None:
    """Release only this task's in-progress claim after its final failure."""
    try:
        client = get_redis_client()
        state_key = _import_state_key(bucket_name, object_key, user_id)
        raw_state = client.get(state_key)
        if raw_state and json.loads(raw_state).get("run_id") == run_id:
            client.delete(state_key)
    except Exception:
        logger.warning("Unable to release failed Apple XML import claim", exc_info=True)


def _as_uuid(user_id: str) -> UUID | None:
    try:
        return UUID(user_id)
    except (TypeError, ValueError):
        return None


def _run_import_task(
    task: Task,
    *,
    bucket_name: str,
    object_key: str,
    user_id: str,
    upload_id: str | None = None,
    parts: list[CompletedPart] | None = None,
) -> dict[str, str]:
    run_id = task.request.id or new_run_id("xml-s3")
    claim_status, persisted_result = _claim_import(bucket_name, object_key, user_id, run_id)
    if persisted_result is not None:
        return persisted_result
    if claim_status == "processing":
        return {
            "bucket": bucket_name,
            "input_key": object_key,
            "user_id": user_id,
            "status": "processing",
            "message": "Import is already being processed",
        }

    user_uuid = _as_uuid(user_id)
    metadata = {"bucket": bucket_name, "object_key": object_key}
    if user_uuid is not None and task.request.retries == 0:
        started(
            user_uuid,
            "apple",
            SyncSource.XML_IMPORT,
            run_id=run_id,
            message="Importing Apple Health XML file from object storage",
            metadata=metadata,
        )

    try:
        if (
            upload_id is not None
            and parts is not None
            and not _upload_completion_persisted(bucket_name, object_key, user_id)
        ):
            _ensure_upload_completed(bucket_name, object_key, upload_id, parts, user_id)
            _store_upload_completion(bucket_name, object_key, user_id)
        result = _process_aws_upload(bucket_name, object_key, user_id)
        _store_completed_import(bucket_name, object_key, user_id, result)
        if user_uuid is not None:
            completed(
                user_uuid,
                "apple",
                SyncSource.XML_IMPORT,
                run_id=run_id,
                status=SyncStatus.SKIPPED if result["status"] == "skipped" else SyncStatus.SUCCESS,
                message=result.get("message") or result.get("reason") or "Apple Health XML import completed",
                metadata=metadata,
            )
        return result
    except Exception as exc:
        retryable = not isinstance(exc, HTTPException) or exc.status_code >= 500
        can_retry = retryable and not task.request.called_directly and task.request.retries < (task.max_retries or 0)
        if can_retry:
            raise task.retry(exc=exc, countdown=min(10 * (2**task.request.retries), 300)) from exc

        _release_import_claim(bucket_name, object_key, user_id, run_id)
        if user_uuid is not None:
            failed(
                user_uuid,
                "apple",
                SyncSource.XML_IMPORT,
                run_id=run_id,
                error=str(exc),
                message="Apple Health XML import failed",
                metadata=metadata,
            )
        raise


def _process_aws_upload(bucket_name: str, object_key: str, user_id: str) -> dict[str, str]:
    """Stream an S3 XML object into the importer without using local disk."""
    s3_client = get_s3_client()
    if not s3_client:
        err = RuntimeError("S3 client not configured — cannot process AWS upload")
        log_and_capture_error(
            err,
            logger,
            "S3 client unavailable in process_aws_upload task",
            extra={"bucket_name": bucket_name, "object_key": object_key, "user_id": user_id},
        )
        raise err

    with SessionLocal() as db:
        # Validate that the user exists before opening a potentially multi-gigabyte object.
        try:
            _ = user_service.get(db, user_id, raise_404=True)
        except ResourceNotFoundError as e:
            log_and_capture_error(
                e,
                logger,
                "Skipping import for non-existent user",
                extra={"user_id": user_id},
            )
            return {
                "status": "skipped",
                "reason": str(e),
            }

        response: dict[str, Any] = s3_client.get_object(Bucket=bucket_name, Key=object_key)
        body: BinaryIO = response["Body"]
        try:
            _import_xml_data(db, body, user_id)
        except Exception:
            db.rollback()
            raise
        finally:
            body.close()

        return {
            "bucket": bucket_name,
            "input_key": object_key,
            "user_id": user_id,
            "status": "success",
            "message": "Import completed successfully",
        }


@shared_task(bind=True, acks_late=True, reject_on_worker_lost=True, max_retries=3)
def process_aws_upload(task: Task, bucket_name: str, object_key: str, user_id: str) -> dict[str, str]:
    """Process an XML file uploaded to S3 and import it into Postgres."""
    return _run_import_task(task, bucket_name=bucket_name, object_key=object_key, user_id=user_id)


def _object_exists(bucket_name: str, object_key: str) -> bool:
    """Whether the finalized object is already present (i.e. completion already ran)."""
    s3_client = get_s3_client()
    if not s3_client:
        return False
    try:
        s3_client.head_object(Bucket=bucket_name, Key=object_key)
        return True
    except ClientError as exc:
        error_code = str(exc.response.get("Error", {}).get("Code", ""))
        http_status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        if error_code in {"NoSuchKey", "NotFound", "404"} or http_status == 404:
            return False
        raise


def _ensure_upload_completed(
    bucket_name: str,
    object_key: str,
    upload_id: str,
    parts: list[CompletedPart],
    user_id: str,
) -> None:
    """Complete the multipart upload, tolerating an already-completed upload.

    A duplicate task delivery (or a manual retry) can arrive after the upload was already
    assembled, at which point the upload id is gone and ``complete_upload`` fails with a
    404. When the finalized object already exists that is a success, not an error, so we
    swallow it and let processing proceed against the stored object.
    """
    try:
        multipart_upload_service.complete_upload(
            user_id=user_id,
            key=object_key,
            upload_id=upload_id,
            parts=parts,
            bucket_name=bucket_name,
        )
    except HTTPException as exc:
        if exc.status_code == status.HTTP_404_NOT_FOUND and _object_exists(bucket_name, object_key):
            return
        raise


@shared_task(bind=True, acks_late=True, reject_on_worker_lost=True, max_retries=3)
def complete_and_process_aws_upload(
    task: Task,
    *,
    bucket_name: str,
    object_key: str,
    upload_id: str,
    parts: list[dict[str, Any]],
    user_id: str,
) -> dict[str, str]:
    """Finalize a client-driven multipart upload and process it in one queued job.

    Publishing this task happens before the multipart upload is completed. If the broker
    is unavailable, the upload therefore remains incomplete and can still be retried or
    aborted instead of becoming an untracked finalized object.

    Completion is idempotent (see :func:`_ensure_upload_completed`). The task uses late
    acknowledgement and retries transient completion/import failures. A Redis object-state
    marker suppresses duplicate delivery after success; importer writes also use existing
    uniqueness/upsert behavior for crash recovery before that marker is stored.
    """
    completed_parts = [CompletedPart.model_validate(part) for part in parts]
    return _run_import_task(
        task,
        bucket_name=bucket_name,
        object_key=object_key,
        user_id=user_id,
        upload_id=upload_id,
        parts=completed_parts,
    )


def _import_xml_data(db: Session, xml_source: str | Path | BinaryIO, user_id: str) -> None:
    """
    Parse XML file and import data to database using XMLExporter.

    Args:
        db: Database session
        xml_source: Path or binary stream containing the XML file
        user_id: User ID to associate with the data
    """
    normalized_source = Path(xml_source) if isinstance(xml_source, str) else xml_source
    xml_service = XMLService(normalized_source, getLogger(__name__))

    for time_series_records, workouts, sync_request in xml_service.parse_xml(user_id):
        for record, detail in workouts:
            created_record = event_record_service.create(db, record)
            detail_for_record = detail.model_copy(update={"record_id": created_record.id})
            event_record_service.create_detail(db, detail_for_record)
        if time_series_records:
            timeseries_service.bulk_create_samples(db, time_series_records)
            db.commit()
        if sync_request and sync_request.data.sleep:
            handle_sleep_data(db, sync_request, user_id)
