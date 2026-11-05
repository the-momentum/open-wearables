import json
from json import JSONDecodeError
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response, UploadFile, status
from pydantic import ValidationError

from app.config import settings
from app.database import DbSession
from app.integrations.celery.tasks.process_aws_upload_task import complete_and_process_aws_upload
from app.schemas.providers.apple.apple_xml import (
    MultipartAbortRequest,
    MultipartAbortResponse,
    MultipartCompleteRequest,
    MultipartCompleteResponse,
    MultipartCreateRequest,
    MultipartCreateResponse,
    MultipartSignRequest,
    MultipartSignResponse,
    PresignedURLRequest,
    PresignedURLResponse,
    SNSNotification,
)
from app.schemas.responses.upload import UploadDataResponse
from app.services import ApiKeyDep, user_service
from app.services.providers.apple.apple_xml.aws_service import require_bucket_name
from app.services.providers.apple.apple_xml.direct_upload_service import (
    direct_upload_limit,
    direct_upload_service,
    max_request_body,
    mib,
    request_too_large_detail,
    too_large_detail,
)
from app.services.providers.apple.apple_xml.multipart_upload_service import multipart_upload_service
from app.services.providers.apple.apple_xml.presigned_url_service import presigned_url_service
from app.services.providers.apple.apple_xml.sns_service import sns_service
from app.utils.body_limit import body_limit_route
from app.utils.problem import problem_doc

router = APIRouter()

# Checked when an import starts. For S3 uploads a missing user fails before the file is
# uploaded, and the S3 worker checks again before importing. For direct uploads the file
# has already been received, so the check only keeps it out of the queue.
_USER_NOT_FOUND = problem_doc(404, "User not found", "User with ID: 123e4567-e89b-12d3-a456-426614174000 not found.")


@router.post("/users/{user_id}/import/apple/xml/s3", responses={**_USER_NOT_FOUND})
def import_xml_presigned_url(
    user_id: UUID,
    request: PresignedURLRequest,
    db: DbSession,
    _api_key: ApiKeyDep,
) -> PresignedURLResponse:
    """Generate presigned URL for XML file upload and trigger processing task."""
    user_service.get(db, user_id, raise_404=True)
    return presigned_url_service.create_presigned_url(str(user_id), request)


@router.post(
    "/users/{user_id}/import/apple/xml/s3/multipart/create",
    status_code=status.HTTP_201_CREATED,
    responses={**_USER_NOT_FOUND},
)
def create_multipart_upload(
    user_id: UUID,
    request: MultipartCreateRequest,
    db: DbSession,
    _api_key: ApiKeyDep,
) -> MultipartCreateResponse:
    """Start a multipart upload for a (potentially very large) XML file to S3/MinIO."""
    user_service.get(db, user_id, raise_404=True)
    return multipart_upload_service.create_upload(
        user_id=str(user_id),
        filename=request.filename,
        content_type=request.content_type,
        file_size=request.file_size,
    )


@router.post(
    "/users/{user_id}/import/apple/xml/s3/multipart/sign",
)
def sign_multipart_parts(
    user_id: UUID,
    request: MultipartSignRequest,
    _api_key: ApiKeyDep,
) -> MultipartSignResponse:
    """Presign upload URLs for a batch of parts of an in-progress multipart upload."""
    return multipart_upload_service.sign_upload_parts(
        user_id=str(user_id),
        key=request.key,
        upload_id=request.upload_id,
        part_numbers=request.part_numbers,
        expiration_seconds=request.expiration_seconds,
    )


@router.post(
    "/users/{user_id}/import/apple/xml/s3/multipart/complete",
    status_code=status.HTTP_202_ACCEPTED,
)
def complete_multipart_upload(
    user_id: UUID,
    request: MultipartCompleteRequest,
    response: Response,
    _api_key: ApiKeyDep,
) -> MultipartCompleteResponse:
    """Finalize an SNS upload, or queue client-driven finalization and processing.

    When ``APPLE_XML_UPLOAD_COMPLETION_MODE`` is ``"sns"`` the import task is instead
    triggered by the S3 bucket event, so this endpoint only finalizes the object.
    """
    if settings.apple_xml_upload_completion_mode == "client":
        bucket_name = multipart_upload_service.validate_completion_request(
            str(user_id),
            request.key,
            request.upload_id,
            request.parts,
        )
        try:
            task = complete_and_process_aws_upload.delay(
                bucket_name=bucket_name,
                object_key=request.key,
                upload_id=request.upload_id,
                parts=[part.model_dump() for part in request.parts],
                user_id=str(user_id),
            )
        except Exception as e:
            # The object has deliberately not been finalized yet, so callers can safely
            # retry this request or abort the still-incomplete upload.
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to queue upload processing; the multipart upload remains incomplete",
            ) from e

        return MultipartCompleteResponse(
            status="processing",
            key=request.key,
            bucket=bucket_name,
            task_id=task.id,
        )

    key = multipart_upload_service.complete_upload(
        user_id=str(user_id),
        key=request.key,
        upload_id=request.upload_id,
        parts=request.parts,
    )
    bucket_name = require_bucket_name()
    response.status_code = status.HTTP_200_OK

    return MultipartCompleteResponse(
        status="uploaded",
        key=key,
        bucket=bucket_name,
        task_id=None,
    )


@router.post(
    "/users/{user_id}/import/apple/xml/s3/multipart/abort",
)
def abort_multipart_upload(
    user_id: UUID,
    request: MultipartAbortRequest,
    _api_key: ApiKeyDep,
) -> MultipartAbortResponse:
    """Abort an incomplete multipart upload and discard its parts."""
    multipart_upload_service.abort_upload(user_id=str(user_id), key=request.key, upload_id=request.upload_id)
    return MultipartAbortResponse(status="aborted", key=request.key)


# Rejects an oversized upload while it streams in, before FastAPI spools it to disk.
_direct_router = APIRouter(route_class=body_limit_route(max_request_body, request_too_large_detail))


@_direct_router.post(
    "/users/{user_id}/import/apple/xml/direct",
    responses={
        **_USER_NOT_FOUND,
        **problem_doc(
            413,
            f"File is over {mib(direct_upload_limit())} MiB",
            too_large_detail(direct_upload_limit() + 1),
        ),
        **problem_doc(503, "Task queue unavailable", "Unable to queue XML processing"),
    },
    description=(
        f"Import an Apple Health XML file of up to {mib(direct_upload_limit())} MiB "
        "into the database. "
        "Larger files must use the S3 multipart upload."
    ),
)
def import_xml_file(
    user_id: UUID,
    file: UploadFile,
    db: DbSession,
    _api_key: ApiKeyDep,
) -> dict[str, str]:
    """Queue a small XML upload for import."""
    user_service.get(db, user_id, raise_404=True)
    # Starlette's multipart parser always sets the size of the spooled file.
    task_id = direct_upload_service.queue_import(str(user_id), file.file, file.size or 0, file.filename or "upload.xml")

    return {
        "status": "processing",
        "task_id": task_id,
        "user_id": str(user_id),
    }


router.include_router(_direct_router)


@router.post("/sns/notification", status_code=status.HTTP_202_ACCEPTED)
async def receive_sns_notification(
    request: Request,
) -> UploadDataResponse:
    """Handle all SNS messages (subscription confirmation + S3 upload notifications)."""
    body = await request.body()
    try:
        notification = SNSNotification.model_validate(json.loads(body))
    except (ValidationError, JSONDecodeError) as e:
        # the parse error, which quotes the body, goes to the access log only
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid SNS notification") from e

    result = await sns_service.handle_sns_notification(notification)

    if result.status_code not in (status.HTTP_200_OK, status.HTTP_202_ACCEPTED):
        raise HTTPException(status_code=result.status_code, detail=result.response)
    return result
