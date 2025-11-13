from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


DEFAULT_EXPIRATION = 300  # 5 minutes


class FileType(str, Enum):
    JSON = "application/json"
    XML = "application/xml"
    CSV = "text/csv"
    TEXT = "text/plain"


class PresignedURLRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=100, description="Unique user identifier")
    file_type: FileType = Field(default=FileType.XML, description="MIME type of the file")
    filename: Optional[str] = Field(None, max_length=200, description="Optional custom filename")
    expiration_seconds: Optional[int] = Field(
        default=DEFAULT_EXPIRATION,
        ge=60,
        le=3600,
        description="URL expiration time in seconds (1 min - 1 hour)",
    )
    max_file_size: Optional[int] = Field(
        default=50 * 1024 * 1024,  # 50MB
        ge=1024,  # 1KB minimum
        le=500 * 1024 * 1024,  # 500MB maximum
        description="Maximum file size in bytes",
    )


class PresignedURLResponse(BaseModel):
    upload_url: str
    form_fields: dict[str, str]
    file_key: str
    expires_in: int
    max_file_size: int
    content_type: str
    bucket: str


class S3Event(BaseModel):
    bucket_name: str
    object_key: str
    event_name: str


class SQSMessage(BaseModel):
    Message: str
    MessageId: str
