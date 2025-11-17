from datetime import datetime, UTC
from logging import Logger, getLogger

from fastapi import HTTPException, status
from botocore.exceptions import ClientError

from app.services.apple.apple_xml.aws_service import s3_client, AWS_BUCKET_NAME
from app.schemas.apple.apple_xml.aws import PresignedURLResponse, PresignedURLRequest


class ImportService:
    def __init__(self, log: Logger, **kwargs):
        self.log = log

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
        try:
            s3_client.head_bucket(Bucket=AWS_BUCKET_NAME)
            self.log.debug(f"S3 bucket exists: {AWS_BUCKET_NAME}")
            return True
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "404":
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="S3 bucket not found") from e
            elif error_code == "403":
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to S3 bucket") from e
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail=f"S3 bucket error: {error_code}"
                ) from e

    def create_presigned_url(self, user_id: str, request: PresignedURLRequest) -> PresignedURLResponse:
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

            presigned_post = s3_client.generate_presigned_post(
                Bucket=AWS_BUCKET_NAME,
                Key=file_key,
                Fields={"Content-Type": "application/xml"},
                Conditions=conditions,
                ExpiresIn=request.expiration_seconds,
            )

            self.log.debug(f"Generated presigned URL: {presigned_post['url']}")

            return PresignedURLResponse(
                upload_url=presigned_post["url"],
                form_fields=presigned_post["fields"],
                file_key=file_key,
                expires_in=request.expiration_seconds,
                max_file_size=request.max_file_size,
                bucket=AWS_BUCKET_NAME,
            )

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to generate presigned URL: {error_code}",
            ) from e
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Unexpected error: {str(e)}"
            ) from e


import_service = ImportService(getLogger(__name__))
