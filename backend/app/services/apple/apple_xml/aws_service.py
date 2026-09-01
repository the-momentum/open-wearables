"""Apple XML object-store configuration and client helpers.

This module owns storage configuration validation, cached backend/browser clients,
and object-key generation. Upload lifecycle operations remain in the presigned and
multipart services; SNS notification handling remains in ``sns_service``.
"""

from datetime import UTC, datetime
from logging import getLogger
from typing import Any
from uuid import uuid4

import boto3
from botocore.exceptions import NoCredentialsError
from fastapi import HTTPException, status

from app.config import settings
from app.services.s3_client import create_s3_client
from app.utils.structured_logging import log_structured

logger = getLogger(__name__)


def require_bucket_name() -> str:
    """Return the configured bucket name or fail with the public API error."""
    if not settings.aws_bucket_name:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="S3 bucket not configured",
        )
    return settings.aws_bucket_name


# Successful clients are cached per endpoint so we don't rebuild them on every call.
# Crucially, failures (missing credentials, unbuildable client) are never cached, so a
# later configuration change can recover instead of the process being wedged at 503.
_client_cache: dict[str | None, Any] = {}


def _resolve_client(endpoint_url: str | None) -> Any | None:
    if not (settings.aws_access_key_id and settings.aws_secret_access_key):
        log_structured(logger, "warning", "AWS credentials not configured")
        return None
    cached = _client_cache.get(endpoint_url)
    if cached is not None:
        return cached
    client = create_s3_client(endpoint_url)
    if client is None:
        return None
    _client_cache[endpoint_url] = client
    return client


def get_s3_client() -> Any | None:
    """Return an S3 client for the Apple XML upload flow, or None when unconfigured.

    Credentials are required (MinIO uses them too), which keeps the "storage not
    configured -> 503" behaviour that callers rely on. When ``AWS_ENDPOINT_URL``
    is set the client points at that S3-compatible server (e.g. MinIO).
    """
    return _resolve_client(settings.aws_endpoint_url)


def get_public_s3_client() -> Any | None:
    """S3 client whose endpoint is what the *browser* will hit for presigned uploads.

    Uses ``AWS_PUBLIC_ENDPOINT_URL`` when set (e.g. ``http://localhost:9000`` for a
    Dockerised MinIO whose service name the browser can't resolve), otherwise
    falls back to the internal ``AWS_ENDPOINT_URL``. Only used to presign POST /
    ``upload_part`` URLs handed to the browser — all backend-side S3 calls use
    :func:`get_s3_client`.
    """
    return _resolve_client(settings.aws_public_endpoint_url or settings.aws_endpoint_url)


def get_sns_client() -> Any | None:
    try:
        return boto3.client(
            "sns",
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key.get_secret_value(),  # ty:ignore[unresolved-attribute]
        )
    except (NoCredentialsError, AttributeError):
        log_structured(logger, "warning", "AWS credentials not configured")
        return None


def build_object_key(user_id: str, filename: str | None = None) -> str:
    """Build the S3 object key for a user's uploaded Apple Health XML file.

    Keys are always namespaced under ``<user_id>/raw/`` so uploads can be attributed
    back to a user and access can be scoped per user.
    """
    # A unique token is required even when a filename is supplied. Otherwise two
    # concurrent exports from the same user target the same object and one completed
    # multipart upload can overwrite the object while the other task is reading it.
    unique_token = uuid4().hex
    if filename:
        clean_filename = "".join(c for c in filename if c.isalnum() or c in ".-_")
        if clean_filename:
            return f"{user_id}/raw/{unique_token}-{clean_filename}"
    # Compact, URL-safe UTC timestamp (no spaces/colons) so the key needs no encoding.
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    return f"{user_id}/raw/{timestamp}-{unique_token}.xml"
