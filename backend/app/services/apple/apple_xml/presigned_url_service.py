from logging import Logger, getLogger

from botocore.exceptions import ClientError
from fastapi import HTTPException, status

from app.schemas.providers.apple.apple_xml import (
    PresignedURLRequest,
    PresignedURLResponse,
)
from app.services.apple.apple_xml.aws_service import (
    build_object_key,
    get_public_s3_client,
    get_s3_client,
    require_bucket_name,
)
from app.utils.structured_logging import log_structured


class PresignedURLService:
    def __init__(self, log: Logger) -> None:
        self.log = log

    def generate_file_key(self, user_id: str, filename: str | None = None) -> str:
        file_key = build_object_key(user_id, filename)
        log_structured(
            self.log,
            "debug",
            "Generated Apple XML file key",
            provider="apple_xml",
            action="file_key_generated",
            file_key=file_key,
        )
        return file_key

    def validate_bucket_exists(self) -> str:
        """Return the configured bucket after checking that it is accessible."""

        s3_client = get_s3_client()
        if not s3_client:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="S3 client not configured")

        bucket = require_bucket_name()
        try:
            s3_client.head_bucket(Bucket=bucket)
            log_structured(
                self.log,
                "debug",
                "S3 bucket exists",
                provider="apple_xml",
                action="bucket_validated",
                bucket=bucket,
            )
            return bucket
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "404":
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="S3 bucket not found") from e
            if error_code == "403":
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to S3 bucket") from e
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"S3 bucket error: {error_code}",
            ) from e

    def create_presigned_url(self, user_id: str, request: PresignedURLRequest) -> PresignedURLResponse:
        s3_client = get_s3_client()
        if not s3_client:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="S3 client not configured")

        bucket = self.validate_bucket_exists()

        file_key = self.generate_file_key(
            user_id=user_id,
            filename=request.filename,
        )

        try:
            fields = {"Content-Type": "application/xml"}
            conditions = [
                ["content-length-range", 1, request.max_file_size],
                {"Content-Type": "application/xml"},
            ]

            # Presign against the browser-facing endpoint so the returned URL is one the
            # browser can actually reach (bucket existence was checked via the internal client).
            presign_client = get_public_s3_client() or s3_client
            presigned_post = presign_client.generate_presigned_post(
                Bucket=bucket,
                Key=file_key,
                Fields=fields,
                Conditions=conditions,
                ExpiresIn=request.expiration_seconds,
            )

            log_structured(
                self.log,
                "debug",
                "Generated Apple XML presigned POST",
                provider="apple_xml",
                action="presigned_post_generated",
                bucket=bucket,
                file_key=file_key,
            )

            return PresignedURLResponse(
                upload_url=presigned_post["url"],
                form_fields=presigned_post["fields"],
                file_key=file_key,
                expires_in=request.expiration_seconds,
                max_file_size=request.max_file_size,
                bucket=bucket,
            )

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to generate presigned URL: {error_code}",
            ) from e
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Unexpected error: {str(e)}",
            ) from e


presigned_url_service = PresignedURLService(getLogger(__name__))
