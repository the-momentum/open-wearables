from pydantic import BaseModel, Field

from app.config import settings

MIN_SECONDS, DEFAULT_SECONDS, MAX_SECONDS = settings.presigned_url_expiration_seconds
MIN_FILESIZE, DEFAULT_FILESIZE, MAX_FILESIZE = settings.presigned_url_max_filesize


class PresignedURLRequest(BaseModel):
    filename: str = Field(None, max_length=200, description="Custom filename")
    expiration_seconds: int = Field(
        default=DEFAULT_SECONDS,
        ge=MIN_SECONDS,
        le=MAX_SECONDS,
        description="URL expiration time in seconds (1 min - 1 hour)",
    )
    max_file_size: int = Field(
        default=DEFAULT_FILESIZE,
        ge=MIN_FILESIZE,
        le=MAX_FILESIZE,
        description="Maximum file size in bytes (1KB - 500MB)",
    )


class PresignedURLResponse(BaseModel):
    upload_url: str
    form_fields: dict[str, str]
    file_key: str
    expires_in: int
    max_file_size: int
    bucket: str
