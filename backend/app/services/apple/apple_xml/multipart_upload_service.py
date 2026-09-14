"""Service for S3 / MinIO multipart uploads of Apple Health XML exports.

Drives the four multipart phases from the backend so the browser only needs the
presigned per-part URLs:

    create_upload     -> open an upload and return its key + recommended part size
    sign_upload_parts -> presign an ``upload_part`` URL for each requested part
    complete_upload   -> assemble the parts into the final object
    abort_upload      -> discard an incomplete upload and its parts

Object keys are always namespaced under ``<user_id>/raw/``; every call verifies the
key belongs to the requesting user so one user cannot touch another's upload.
"""

from logging import Logger, getLogger
from typing import Any

from botocore.exceptions import ClientError
from fastapi import HTTPException, status

from app.schemas.providers.apple.apple_xml import (
    MAX_PARTS,
    CompletedPart,
    MultipartCreateResponse,
    MultipartSignResponse,
    SignedPart,
    recommended_part_size,
)
from app.services.apple.apple_xml.aws_service import (
    build_object_key,
    get_public_s3_client,
    get_s3_client,
    require_bucket_name,
)
from app.utils.structured_logging import log_structured


class MultipartUploadService:
    def __init__(self, log: Logger) -> None:
        self.log = log

    def _require_client(self) -> Any:

        client = get_s3_client()
        if not client:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="S3 client not configured",
            )
        return client

    def _require_public_client(self) -> Any:
        """Client for presigning browser-facing part URLs; falls back to the internal one."""
        client = get_public_s3_client() or get_s3_client()
        if not client:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="S3 client not configured",
            )
        return client

    @staticmethod
    def _verify_owner(user_id: str, key: str) -> None:
        """Reject keys that don't belong to the requesting user."""
        if not key.startswith(f"{user_id}/"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Object key does not belong to this user",
            )

    def validate_completion_request(
        self,
        user_id: str,
        key: str,
        upload_id: str,
        parts: list[CompletedPart],
    ) -> str:
        """Validate ownership and uploaded parts before background finalization."""
        self._verify_owner(user_id, key)
        client = self._require_client()
        bucket = require_bucket_name()

        uploaded_parts: dict[int, str] = {}
        marker = 0
        listed_part_count = 0
        page_count = 0

        max_pages = MAX_PARTS
        try:
            while True:
                page_count += 1
                if page_count > max_pages:
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail="Object storage returned too many multipart listing pages",
                    )
                kwargs: dict[str, Any] = {
                    "Bucket": bucket,
                    "Key": key,
                    "UploadId": upload_id,
                    "MaxParts": 1000,
                }
                if marker:
                    kwargs["PartNumberMarker"] = marker
                response = client.list_parts(**kwargs)
                page_parts = response.get("Parts", [])
                if not isinstance(page_parts, list):
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail="Object storage returned an invalid multipart part listing",
                    )
                previous_part_number = marker
                for uploaded_part in page_parts:
                    try:
                        part_number = int(uploaded_part["PartNumber"])
                        etag_value = uploaded_part["ETag"]
                        if etag_value is None:
                            raise ValueError("missing ETag")
                    except (KeyError, TypeError, ValueError) as e:
                        raise HTTPException(
                            status_code=status.HTTP_502_BAD_GATEWAY,
                            detail="Object storage returned an invalid multipart part listing",
                        ) from e
                    listed_part_count += 1
                    if (
                        listed_part_count > MAX_PARTS
                        or part_number <= previous_part_number
                        or part_number > MAX_PARTS
                        or part_number in uploaded_parts
                    ):
                        raise HTTPException(
                            status_code=status.HTTP_502_BAD_GATEWAY,
                            detail="Object storage returned an invalid multipart part listing",
                        )
                    uploaded_parts[part_number] = self._normalize_etag(str(etag_value))
                    previous_part_number = part_number

                if not response.get("IsTruncated", False):
                    break

                if listed_part_count >= MAX_PARTS or page_count >= max_pages:
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail="Object storage returned more multipart parts than allowed",
                    )
                next_marker = response.get("NextPartNumberMarker")

                try:
                    parsed_next_marker = int(next_marker)
                except (TypeError, ValueError) as e:
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail="Object storage returned an invalid multipart part listing",
                    ) from e
                if parsed_next_marker <= marker or parsed_next_marker < previous_part_number:
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail="Object storage returned an invalid multipart part listing",
                    )
                marker = parsed_next_marker
        except ClientError as e:
            raise self._client_error(e, "Failed to validate multipart upload") from e

        requested_parts = {part.part_number: self._normalize_etag(part.etag) for part in parts}
        if len(requested_parts) != len(parts) or requested_parts != uploaded_parts:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Completed parts do not match the parts stored for this multipart upload",
            )
        return bucket

    def create_upload(
        self,
        user_id: str,
        filename: str,
        content_type: str,
        file_size: int,
    ) -> MultipartCreateResponse:
        client = self._require_client()
        bucket = require_bucket_name()
        key = build_object_key(user_id, filename or None)

        try:
            response = client.create_multipart_upload(
                Bucket=bucket,
                Key=key,
                ContentType=content_type,
            )
        except ClientError as e:
            raise self._client_error(e, "Failed to create multipart upload") from e

        log_structured(
            self.log,
            "debug",
            "Created Apple XML multipart upload",
            provider="apple_xml",
            action="multipart_upload_created",
            bucket=bucket,
            key=key,
            upload_id=response["UploadId"],
        )
        return MultipartCreateResponse(
            upload_id=response["UploadId"],
            key=key,
            bucket=bucket,
            part_size=recommended_part_size(file_size),
        )

    def sign_upload_parts(
        self,
        user_id: str,
        key: str,
        upload_id: str,
        part_numbers: list[int],
        expiration_seconds: int,
    ) -> MultipartSignResponse:
        self._verify_owner(user_id, key)
        client = self._require_public_client()
        bucket = require_bucket_name()

        urls: list[SignedPart] = []
        for part_number in part_numbers:
            try:
                url = client.generate_presigned_url(
                    "upload_part",
                    Params={
                        "Bucket": bucket,
                        "Key": key,
                        "UploadId": upload_id,
                        "PartNumber": part_number,
                    },
                    ExpiresIn=expiration_seconds,
                )
            except ClientError as e:
                raise self._client_error(e, "Failed to sign upload part") from e
            urls.append(SignedPart(part_number=part_number, url=url))

        log_structured(
            self.log,
            "debug",
            "Signed Apple XML multipart upload parts",
            provider="apple_xml",
            action="multipart_upload_parts_signed",
            bucket=bucket,
            key=key,
            upload_id=upload_id,
            part_count=len(part_numbers),
            expiration_seconds=expiration_seconds,
        )
        return MultipartSignResponse(urls=urls)

    def complete_upload(
        self,
        user_id: str,
        key: str,
        upload_id: str,
        parts: list[CompletedPart],
        *,
        bucket_name: str | None = None,
    ) -> str:
        """Complete the upload and return the finalized object key."""
        self._verify_owner(user_id, key)
        client = self._require_client()
        bucket = bucket_name or require_bucket_name()

        ordered = sorted(parts, key=lambda p: p.part_number)
        multipart_parts = [
            {"ETag": self._normalize_etag(part.etag), "PartNumber": part.part_number} for part in ordered
        ]

        try:
            client.complete_multipart_upload(
                Bucket=bucket,
                Key=key,
                UploadId=upload_id,
                MultipartUpload={"Parts": multipart_parts},
            )
        except ClientError as e:
            raise self._client_error(e, "Failed to complete multipart upload") from e

        log_structured(
            self.log,
            "debug",
            "Completed Apple XML multipart upload",
            provider="apple_xml",
            action="multipart_upload_completed",
            bucket=bucket,
            key=key,
            upload_id=upload_id,
        )
        return key

    def abort_upload(self, user_id: str, key: str, upload_id: str) -> None:
        self._verify_owner(user_id, key)
        client = self._require_client()
        bucket = require_bucket_name()

        try:
            client.abort_multipart_upload(Bucket=bucket, Key=key, UploadId=upload_id)
        except ClientError as e:
            # Abort is intentionally idempotent. The upload may already have been
            # discarded by a previous request or by the stale-upload cleanup task.
            if self._error_code(e) == "NoSuchUpload":
                return
            raise self._client_error(e, "Failed to abort multipart upload") from e

        log_structured(
            self.log,
            "debug",
            "Aborted Apple XML multipart upload",
            provider="apple_xml",
            action="multipart_upload_aborted",
            bucket=bucket,
            key=key,
            upload_id=upload_id,
        )

    @staticmethod
    def _error_code(error: ClientError) -> str:
        return str(error.response.get("Error", {}).get("Code", "UnknownError"))

    @staticmethod
    def _normalize_etag(etag: str) -> str:
        """Trim transport whitespace without changing the object store's opaque ETag."""
        return etag.strip()

    @classmethod
    def _client_error(cls, error: ClientError, message: str) -> HTTPException:
        error_code = cls._error_code(error)
        if error_code in {"NoSuchUpload", "NoSuchKey", "NotFound", "404"}:
            status_code = status.HTTP_404_NOT_FOUND
        elif error_code in {"AccessDenied", "AllAccessDisabled", "Forbidden", "403"}:
            status_code = status.HTTP_403_FORBIDDEN
        elif error_code in {
            "EntityTooSmall",
            "InvalidArgument",
            "InvalidPart",
            "InvalidPartOrder",
            "MalformedXML",
        }:
            status_code = status.HTTP_400_BAD_REQUEST
        elif error_code in {"InternalError", "RequestTimeout", "ServiceUnavailable", "SlowDown"}:
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        else:
            # Authentication, connectivity, and unknown object-store failures are
            # upstream/backend problems rather than application-internal errors.
            status_code = status.HTTP_502_BAD_GATEWAY
        return HTTPException(
            status_code=status_code,
            detail=f"{message}: {error_code}",
        )


multipart_upload_service = MultipartUploadService(getLogger(__name__))
