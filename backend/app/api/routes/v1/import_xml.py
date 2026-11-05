import json
from collections.abc import Callable, Coroutine
from json import JSONDecodeError
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response, UploadFile, status
from fastapi.routing import APIRoute
from pydantic import ValidationError
from starlette.types import Message, Receive

from app.config import settings
from app.integrations.celery.tasks.process_aws_upload_task import complete_and_process_aws_upload
from app.integrations.celery.tasks.process_xml_upload_task import process_xml_upload
from app.schemas.providers.apple.apple_xml import (
    MAX_DIRECT_UPLOAD_SIZE,
    MAX_FILE_SIZE,
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
from app.services import ApiKeyDep
from app.services.providers.apple.apple_xml.aws_service import require_bucket_name
from app.services.providers.apple.apple_xml.multipart_upload_service import multipart_upload_service
from app.services.providers.apple.apple_xml.presigned_url_service import presigned_url_service
from app.services.providers.apple.apple_xml.sns_service import sns_service
from app.utils.problem import problem_doc
from app.utils.structured_logging import get_logger

router = APIRouter()
logger = get_logger(__name__)

_MIB = 1024 * 1024
_MULTIPART_CREATE_PATH = "POST /api/v1/users/{user_id}/import/apple/xml/s3/multipart/create"


def _direct_upload_limit() -> int:
    """The direct upload cap, never above the product-wide XML size limit."""
    return min(MAX_DIRECT_UPLOAD_SIZE, MAX_FILE_SIZE)


def _mib(size: int) -> str:
    return f"{size // _MIB}"


def _too_large_detail(file_size: int) -> str:
    # Multipart rejects files over the product-wide limit too, so only point there when it would accept the file.
    if file_size > MAX_FILE_SIZE:
        return f"XML import accepts files up to {_mib(MAX_FILE_SIZE)} MiB."
    return (
        f"Direct upload accepts files up to {_mib(_direct_upload_limit())} MiB. "
        f"Use the multipart upload ({_MULTIPART_CREATE_PATH}) for larger files."
    )


# Room for the multipart framing around the file: the boundaries and the part headers with the filename.
_MULTIPART_OVERHEAD = 64 * 1024


def _too_large(file_size: int) -> HTTPException:
    return HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail=_too_large_detail(file_size))


def _limited_receive(request: Request, limit: int) -> Receive:
    """The request's receive channel, raising 413 once the body outgrows the file limit."""
    max_body = limit + _MULTIPART_OVERHEAD
    # Clients that declare the size are rejected before any of the body is read.
    content_length = request.headers.get("content-length", "")
    if content_length.isdigit() and int(content_length) > max_body:
        raise _too_large(int(content_length) - _MULTIPART_OVERHEAD)

    receive = request.receive
    received = 0

    async def receive_within_limit() -> Message:
        nonlocal received
        message = await receive()
        if message["type"] == "http.request":
            received += len(message.get("body", b""))
            if received > max_body:
                raise _too_large(received - _MULTIPART_OVERHEAD)
        return message

    return receive_within_limit


class _DirectUploadRoute(APIRoute):
    """Answers 413 while an oversized body streams in, before FastAPI spools the form to disk.

    The connection stays open and the rest of the body is read and discarded, so clients that
    send the whole body before reading the response see the 413 rather than a reset.
    """

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        handler = super().get_route_handler()

        async def handler_within_limit(request: Request) -> Response:
            receive = _limited_receive(request, _direct_upload_limit())
            return await handler(Request(request.scope, receive))

        return handler_within_limit


_direct_router = APIRouter(route_class=_DirectUploadRoute)


@router.post("/users/{user_id}/import/apple/xml/s3")
def import_xml_presigned_url(
    user_id: str,
    request: PresignedURLRequest,
    _api_key: ApiKeyDep,
) -> PresignedURLResponse:
    """Generate presigned URL for XML file upload and trigger processing task."""
    return presigned_url_service.create_presigned_url(user_id, request)


@router.post(
    "/users/{user_id}/import/apple/xml/s3/multipart/create",
    status_code=status.HTTP_201_CREATED,
)
def create_multipart_upload(
    user_id: str,
    request: MultipartCreateRequest,
    _api_key: ApiKeyDep,
) -> MultipartCreateResponse:
    """Start a multipart upload for a (potentially very large) XML file to S3/MinIO."""
    return multipart_upload_service.create_upload(
        user_id=user_id,
        filename=request.filename,
        content_type=request.content_type,
        file_size=request.file_size,
    )


@router.post(
    "/users/{user_id}/import/apple/xml/s3/multipart/sign",
)
def sign_multipart_parts(
    user_id: str,
    request: MultipartSignRequest,
    _api_key: ApiKeyDep,
) -> MultipartSignResponse:
    """Presign upload URLs for a batch of parts of an in-progress multipart upload."""
    return multipart_upload_service.sign_upload_parts(
        user_id=user_id,
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
    user_id: str,
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
            user_id,
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
                user_id=user_id,
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
        user_id=user_id,
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
    user_id: str,
    request: MultipartAbortRequest,
    _api_key: ApiKeyDep,
) -> MultipartAbortResponse:
    """Abort an incomplete multipart upload and discard its parts."""
    multipart_upload_service.abort_upload(user_id=user_id, key=request.key, upload_id=request.upload_id)
    return MultipartAbortResponse(status="aborted", key=request.key)


@_direct_router.post(
    "/users/{user_id}/import/apple/xml/direct",
    responses={
        **problem_doc(
            413,
            f"File is over {_mib(_direct_upload_limit())} MiB",
            _too_large_detail(_direct_upload_limit() + 1),
        ),
        **problem_doc(503, "Task queue unavailable", "Unable to queue XML processing"),
    },
    description=(
        f"Import an Apple Health XML file of up to {_mib(_direct_upload_limit())} MiB "
        "into the database. "
        "Larger files must use the S3 multipart upload."
    ),
)
def import_xml_file(
    user_id: str,
    file: UploadFile,
    _api_key: ApiKeyDep,
) -> dict[str, str]:
    """Queue a small XML upload for import; the file travels inside the Celery message."""
    # Starlette's multipart parser always sets the size of the spooled file.
    file_size = file.size or 0
    if file_size > _direct_upload_limit():
        raise _too_large(file_size)

    file_contents = file.file.read()
    filename = file.filename or "upload.xml"

    try:
        task = process_xml_upload.delay(file_contents=file_contents, filename=filename, user_id=user_id)
    except Exception as e:
        logger.error(
            "Failed to queue direct XML upload",
            exc_info=e,
            action="xml_direct_upload_queue_failed",
            user_id=user_id,
            file_size=file_size,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to queue XML processing",
        ) from e

    return {
        "status": "processing",
        "task_id": task.id,
        "user_id": user_id,
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
