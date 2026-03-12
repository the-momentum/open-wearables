from pydantic import BaseModel, Field

MIN_EXPIRATION_SECONDS = 60  # 1 minute
MAX_EXPIRATION_SECONDS = 3600  # 1 hour
DEFAULT_EXPIRATION_SECONDS = 300  # 5 minutes
MIN_FILE_SIZE = 1024  # 1KB
MAX_FILE_SIZE = 1024 * 1024 * 1024  # 500MB
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
        description="Maximum file size in bytes (1KB - 500MB)",
    )


class PresignedURLResponse(BaseModel):
    upload_url: str
    form_fields: dict[str, str]
    file_key: str
    expires_in: int
    max_file_size: int
    bucket: str

class SNSNotification(BaseModel):
    message_type: str = Field(..., alias="Type", description="Type of message received from SNS")
    message_id: str = Field(..., alias="MessageId", description="Message ID of the message received from SNS")
    token: str = Field(..., alias="Token", description="Token of the message received from SNS")
    topic_arn: str = Field(..., alias="TopicArn", description="Topic ARN of the message received from SNS")
    message: str = Field(..., alias="Message", description="Message of the message received from SNS")
    subscribe_url: str = Field(..., alias="SubscribeURL", description="Subscribe URL of the message received from SNS")
    timestamp: str = Field(..., alias="Timestamp", description="Timestamp of the message received from SNS")
    signature: str = Field(..., alias="Signature", description="Signature of the message received from SNS")
    signature_version: str = Field(..., alias="SignatureVersion", description="Signature version of the message received from SNS")
    signing_cert_url: str = Field(..., alias="SigningCertURL", description="Signing certificate URL of the message received from SNS")
