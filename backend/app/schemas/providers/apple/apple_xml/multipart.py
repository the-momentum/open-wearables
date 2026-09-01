"""Schemas for S3-compatible multipart uploads of Apple Health XML exports.

S3's protocol limits remain code constants because they are interoperability
invariants: parts are 5 MiB-5 GiB (the final part may be smaller), with at most
10,000 parts per upload. Open Wearables separately caps Apple XML uploads at the
shared ``MAX_FILE_SIZE`` product limit.
"""

from math import ceil
from typing import Annotated

from pydantic import BaseModel, Field

from app.config import settings

from .aws import MAX_FILE_SIZE

MIN_PART_SIZE = 5 * 1024 * 1024  # 5 MiB (S3 minimum, except the final part)
MAX_PART_SIZE = 5 * 1024 * 1024 * 1024  # 5 GiB
MAX_PARTS = 10_000
# Backward-compatible exported default; runtime recommendations read the setting so
# operators can tune it without changing S3's fixed protocol limits.
DEFAULT_PART_SIZE = 100 * 1024 * 1024
MIN_EXPIRATION_SECONDS = 60  # 1 minute
MAX_EXPIRATION_SECONDS = 24 * 60 * 60  # 24 hours
DEFAULT_EXPIRATION_SECONDS = MAX_EXPIRATION_SECONDS  # Supports slow multi-gigabyte uploads


def recommended_part_size(file_size: int) -> int:
    """Pick a part size that keeps the upload within S3's 10,000-part limit.

    Uses the configured default for typical files and grows it (rounded up to a whole
    number of MiB) only when the file is large enough to otherwise exceed MAX_PARTS.
    """
    part_size = settings.apple_xml_multipart_part_size_bytes
    if ceil(file_size / part_size) > MAX_PARTS:
        needed = ceil(file_size / MAX_PARTS)
        # round up to the next whole MiB for tidy, aligned parts
        part_size = ceil(needed / (1024 * 1024)) * (1024 * 1024)
    return min(max(part_size, MIN_PART_SIZE), MAX_PART_SIZE)


class MultipartCreateRequest(BaseModel):
    filename: str = Field("", max_length=200, description="Original filename")
    content_type: str = Field("application/xml", max_length=100, description="Object content type")
    file_size: int = Field(
        ...,
        ge=MIN_PART_SIZE,
        le=MAX_FILE_SIZE,
        description="Total file size in bytes (used to recommend a part size)",
    )


class MultipartCreateResponse(BaseModel):
    upload_id: str = Field(..., description="S3 multipart upload id")
    key: str = Field(..., description="S3 object key the parts belong to")
    bucket: str = Field(..., description="Target bucket")
    part_size: int = Field(..., description="Recommended part size in bytes")


class MultipartSignRequest(BaseModel):
    key: str = Field(..., max_length=1024, description="Object key returned by create")
    upload_id: str = Field(..., max_length=1024, description="Upload id returned by create")
    part_numbers: list[Annotated[int, Field(ge=1, le=MAX_PARTS)]] = Field(
        ...,
        min_length=1,
        max_length=MAX_PARTS,
        description="Part numbers (1-based) to presign upload URLs for",
    )
    expiration_seconds: int = Field(
        default=DEFAULT_EXPIRATION_SECONDS,
        ge=MIN_EXPIRATION_SECONDS,
        le=MAX_EXPIRATION_SECONDS,
        description="Presigned URL lifetime in seconds",
    )


class SignedPart(BaseModel):
    part_number: int = Field(..., ge=1, le=MAX_PARTS)
    url: str


class MultipartSignResponse(BaseModel):
    urls: list[SignedPart]


class CompletedPart(BaseModel):
    part_number: int = Field(..., ge=1, le=MAX_PARTS)
    etag: str = Field(..., max_length=256, description="ETag returned by S3 for the uploaded part")


class MultipartCompleteRequest(BaseModel):
    key: str = Field(..., max_length=1024)
    upload_id: str = Field(..., max_length=1024)
    parts: list[CompletedPart] = Field(..., min_length=1, max_length=MAX_PARTS)


class MultipartCompleteResponse(BaseModel):
    status: str
    key: str
    bucket: str
    task_id: str | None = None


class MultipartAbortRequest(BaseModel):
    key: str = Field(..., max_length=1024)
    upload_id: str = Field(..., max_length=1024)


class MultipartAbortResponse(BaseModel):
    status: str
    key: str
