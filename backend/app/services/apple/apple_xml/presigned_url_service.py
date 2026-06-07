from datetime import UTC, datetime
from logging import Logger, getLogger

from botocore.exceptions import ClientError
from fastapi import HTTPException, status

from app.config import settings
from app.integrations.celery.tasks.process_aws_upload_task import process_aws_upload
from app.schemas.providers.apple.apple_xml import (
    PresignedURLRequest,
    PresignedURLResponse,
    ProcessS3XmlUploadResponse,
)
from app.services.apple.apple_xml.aws_service import AWS_BUCKET_NAME, get_s3_client


class PresignedURLService:
    def __init__(self, log: Logger, **kwargs):
        self.log = log
        self.s3_client = get_s3_client()

    def generate_file_key(self, user_id: str, filename: str | None = None) -> str:
        timestamp = datetime.now(UTC)

        if filename:
            clean_filename = "".join(c for c in filename if c.isalnum() or c in ".-_")
            file_key = f"{user_id}/raw/{clean_filename}" if clean_filename else f"{user_id}/raw/{timestamp}.xml"
        else:
            file_key = f"{user_id}/raw/{timestamp}.xml"

        self.log.debug(f"Generated file key: {file_key}")
        return file_key

    def validate_bucket_exists(self) -> bool:
        """Check if the S3 bucket exists and is accessible"""
        if not self.s3_client:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="S3 client not configured")

        try:
            self.s3_client.head_bucket(Bucket=AWS_BUCKET_NAME)
            self.log.debug(f"S3 bucket exists: {AWS_BUCKET_NAME}")
            return True
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
        if not self.s3_client:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="S3 client not configured")

        self.validate_bucket_exists()

        file_key = self.generate_file_key(
            user_id=user_id,
            filename=request.filename,
        )

        try:
            conditions = [
                ["content-length-range", 1, request.max_file_size],
                {"Content-Type": "application/xml"},
            ]

            presigned_post = self.s3_client.generate_presigned_post(
                Bucket=AWS_BUCKET_NAME,
                Key=file_key,
                Fields={"Content-Type": "application/xml"},
                Conditions=conditions,
                ExpiresIn=request.expiration_seconds,
            )

            self.log.debug(f"Generated presigned URL: {presigned_post['url']}")

            sns_configured = bool(
                settings.aws_sns_topic_arn and settings.aws_sns_topic_arn.get_secret_value()
            )

            return PresignedURLResponse(
                upload_url=presigned_post["url"],
                form_fields=presigned_post["fields"],
                file_key=file_key,
                expires_in=request.expiration_seconds,
                max_file_size=request.max_file_size,
                bucket=AWS_BUCKET_NAME,  # ty:ignore[invalid-argument-type]
                requires_manual_processing=not sns_configured,
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

    def start_s3_xml_processing(self, user_id: str, file_key: str) -> ProcessS3XmlUploadResponse:
        """Queue Celery import for an XML file already uploaded to S3."""
        if not self.s3_client:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="S3 client not configured")

        if not AWS_BUCKET_NAME:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="S3 bucket not configured")

        expected_prefix = f"{user_id}/"
        if not file_key.startswith(expected_prefix):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="file_key does not belong to this user",
            )

        try:
            self.s3_client.head_object(Bucket=AWS_BUCKET_NAME, Key=file_key)
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code in ("404", "NoSuchKey"):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Uploaded file not found in S3",
                ) from e
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"S3 object error: {error_code}",
            ) from e

        task = process_aws_upload.delay(
            bucket_name=AWS_BUCKET_NAME,
            object_key=file_key,
            user_id=user_id,
        )

        self.log.info("Queued S3 XML import for user %s: s3://%s/%s", user_id, AWS_BUCKET_NAME, file_key)

        return ProcessS3XmlUploadResponse(
            task_id=task.id,
            file_key=file_key,
            bucket=AWS_BUCKET_NAME,  # ty:ignore[invalid-argument-type]
            user_id=user_id,
        )


presigned_url_service = PresignedURLService(getLogger(__name__))
