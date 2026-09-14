"""Shared factory for boto3 S3 clients.

Both the Apple Health XML upload flow and raw payload storage talk to S3 (or an
S3-compatible server such as MinIO). Centralising client creation keeps
their endpoint, addressing, and signature configuration consistent.
"""

from logging import getLogger
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError

from app.config import settings
from app.utils.structured_logging import log_structured

logger = getLogger(__name__)


def create_s3_client(endpoint_url: str | None = None) -> Any:
    """Create a boto3 S3 client from the app's AWS settings.

    An explicit ``endpoint_url`` takes precedence over the shared ``AWS_ENDPOINT_URL``
    setting. When either is configured (e.g. for MinIO), the client uses
    path-style addressing and SigV4 signing.

    Explicit credentials are used when configured; otherwise boto3 falls back to its
    default credential chain (env vars, instance role, ...). Returns ``None`` if the
    client cannot be created.
    """
    try:
        kwargs: dict[str, Any] = {"region_name": settings.aws_region}

        if settings.aws_access_key_id and settings.aws_secret_access_key:
            kwargs["aws_access_key_id"] = settings.aws_access_key_id
            kwargs["aws_secret_access_key"] = settings.aws_secret_access_key.get_secret_value()

        resolved_endpoint_url = endpoint_url or settings.aws_endpoint_url
        if resolved_endpoint_url:
            kwargs["endpoint_url"] = resolved_endpoint_url
            # MinIO and most self-hosted S3 servers only support path-style addressing.
            kwargs["config"] = Config(signature_version="s3v4", s3={"addressing_style": "path"})

        return boto3.client("s3", **kwargs)
    except (BotoCoreError, ValueError, AttributeError) as e:
        log_structured(
            logger,
            "warning",
            "Cannot create S3 client",
            error_type=type(e).__name__,
            error=str(e),
        )
        return None
