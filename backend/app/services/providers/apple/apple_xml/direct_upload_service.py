from typing import BinaryIO

from app.config import settings
from app.integrations.celery.tasks.process_xml_upload_task import process_xml_upload
from app.schemas.providers.apple.apple_xml import MAX_DIRECT_UPLOAD_SIZE, MAX_FILE_SIZE
from app.utils.exceptions import ContentTooLargeError, ServiceUnavailableError
from app.utils.structured_logging import get_logger

logger = get_logger(__name__)

_MIB = 1024 * 1024
_MULTIPART_CREATE_PATH = f"POST {settings.api_v1}/users/{{user_id}}/import/apple/xml/s3/multipart/create"
# Room for the multipart framing around the file: the boundaries and the part headers with the filename.
_MULTIPART_OVERHEAD = 64 * 1024


def direct_upload_limit() -> int:
    return min(MAX_DIRECT_UPLOAD_SIZE, MAX_FILE_SIZE)


def mib(size: int) -> str:
    return f"{size // _MIB}"


def too_large_detail(file_size: int) -> str:
    # Multipart rejects files over the product-wide limit too, so only point there when it would accept the file.
    if file_size > MAX_FILE_SIZE:
        return f"XML import accepts files up to {mib(MAX_FILE_SIZE)} MiB."
    return (
        f"Direct upload accepts files up to {mib(direct_upload_limit())} MiB. "
        f"Use the multipart upload ({_MULTIPART_CREATE_PATH}) for larger files."
    )


def max_request_body() -> int:
    return direct_upload_limit() + _MULTIPART_OVERHEAD


def request_too_large_detail(body_size: int) -> str:
    return too_large_detail(body_size - _MULTIPART_OVERHEAD)


class DirectUploadService:
    def queue_import(self, user_id: str, file: BinaryIO, file_size: int, filename: str) -> str:
        """Queue a small XML upload for import; the file travels inside the Celery message."""
        if file_size > direct_upload_limit():
            raise ContentTooLargeError(too_large_detail(file_size))
        try:
            task = process_xml_upload.delay(file_contents=file.read(), filename=filename, user_id=user_id)
        except Exception as e:
            logger.error(
                "Failed to queue direct XML upload",
                exc_info=e,
                action="xml_direct_upload_queue_failed",
                user_id=user_id,
                file_size=file_size,
            )
            raise ServiceUnavailableError("Unable to queue XML processing") from e
        return task.id


direct_upload_service = DirectUploadService()
