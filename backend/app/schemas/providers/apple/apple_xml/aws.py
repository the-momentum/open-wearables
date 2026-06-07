from pydantic import BaseModel, Field

MIN_EXPIRATION_SECONDS = 60  # 1 minute
MAX_EXPIRATION_SECONDS = 3600  # 1 hour
DEFAULT_EXPIRATION_SECONDS = 300  # 5 minutes
MIN_FILE_SIZE = 1024  # 1KB
MAX_FILE_SIZE = 5 * 1024 * 1024 * 1024  # 5GB
DEFAULT_FILE_SIZE = 50 * 1024 * 1024  # 50MB


class PresignedURLRequest(BaseModel):
    filename: str = Field("", max_length=200, description="Custom filename")
    expiration_seconds: int = Field(
        default=DEFAULT_EXPIRATION_SECONDS,
        ge=MIN_EXPIRATION_SECONDS,
        le=MAX_EXPIRATION_SECONDS,
        description="URL expiration time in seconds (1 min - 1 hour)",
    )
    max_file_size: int = Field(
        default=DEFAULT_FILE_SIZE,
        ge=MIN_FILE_SIZE,
        le=MAX_FILE_SIZE,
        description="Maximum file size in bytes (1KB - 5GB)",
    )


class PresignedURLResponse(BaseModel):
    upload_url: str
    form_fields: dict[str, str]
    file_key: str
    expires_in: int
    max_file_size: int
    bucket: str
    requires_manual_processing: bool = Field(
        description="When true, call the /s3/process endpoint after upload (no SNS auto-trigger)",
    )


class ProcessS3XmlUploadRequest(BaseModel):
    file_key: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="S3 object key returned from the presigned URL step",
    )


class ProcessS3XmlUploadResponse(BaseModel):
    status: str = Field("processing", description="Import task status")
    task_id: str = Field(..., description="Celery task ID for the background import")
    file_key: str
    bucket: str
    user_id: str


class SNSNotification(BaseModel):
    """Handles both SubscriptionConfirmation and Notification message types from SNS."""

    message_type: str = Field(..., alias="Type")
    message_id: str = Field(..., alias="MessageId")
    topic_arn: str = Field(..., alias="TopicArn")
    message: str = Field(..., alias="Message")
    timestamp: str = Field(..., alias="Timestamp")
    signature: str = Field(..., alias="Signature")
    signature_version: str = Field(..., alias="SignatureVersion")
    signing_cert_url: str = Field(..., alias="SigningCertURL")
    # Only present on SubscriptionConfirmation
    token: str | None = Field(None, alias="Token")
    subscribe_url: str | None = Field(None, alias="SubscribeURL")
    # Only present on Notification
    subject: str | None = Field(None, alias="Subject")
    unsubscribe_url: str | None = Field(None, alias="UnsubscribeURL")
