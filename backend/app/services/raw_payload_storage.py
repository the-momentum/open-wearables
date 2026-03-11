"""Optional raw payload storage for debugging incoming data.

Stores raw payloads received from SDKs, webhooks, and API responses.
Disabled by default - enable via RAW_PAYLOAD_STORAGE env var.

Supported backends:
    - "disabled" (default): no-op
    - "log": prints JSON to stdout
    - "s3": uploads to S3 bucket (configured via RAW_PAYLOAD_S3_BUCKET / AWS creds)

Usage (one-liner at ingestion point):
    store_raw_payload(source="webhook", provider="garmin", payload=data)
"""

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.utils.structured_logging import json_serial

logger = logging.getLogger(__name__)

_storage_backend: str = "disabled"
_max_size_bytes: int = 10 * 1024 * 1024  # 10 MB
_s3_bucket: str | None = None
_s3_prefix: str = "raw-payloads"
_s3_client: Any = None


def configure(
    storage_backend: str,
    max_size_bytes: int,
    s3_bucket: str | None = None,
    s3_prefix: str = "raw-payloads",
    s3_endpoint_url: str | None = None,
) -> None:
    """Called once at startup from settings."""
    global _storage_backend, _max_size_bytes, _s3_bucket, _s3_prefix, _s3_client
    _storage_backend = storage_backend
    _max_size_bytes = max_size_bytes
    _s3_prefix = s3_prefix

    if storage_backend == "s3":
        _s3_bucket = s3_bucket
        if not _s3_bucket:
            logger.error("RAW_PAYLOAD_STORAGE=s3 but no S3 bucket configured")
            _storage_backend = "disabled"
            return
        _s3_client = _create_s3_client(endpoint_url=s3_endpoint_url)
        if _s3_client is None:
            logger.error("Failed to create S3 client - raw payload storage disabled")
            _storage_backend = "disabled"


def _create_s3_client(endpoint_url: str | None = None) -> Any:
    """Create a boto3 S3 client using app AWS settings."""
    try:
        import boto3
        from botocore.exceptions import NoCredentialsError

        from app.config import settings

        kwargs: dict[str, Any] = {"region_name": settings.aws_region}
        if settings.aws_access_key_id and settings.aws_secret_access_key:
            kwargs["aws_access_key_id"] = settings.aws_access_key_id
            kwargs["aws_secret_access_key"] = settings.aws_secret_access_key.get_secret_value()
        if endpoint_url:
            kwargs["endpoint_url"] = endpoint_url

        return boto3.client("s3", **kwargs)
    except (NoCredentialsError, AttributeError, Exception) as e:
        logger.error("Cannot create S3 client for raw payload storage: %s", e)
        return None


def store_raw_payload(
    *,
    source: str,
    provider: str,
    payload: Any,
    user_id: str | None = None,
    trace_id: str | None = None,
) -> None:
    """Store a raw payload. No-op when disabled.

    Args:
        source: Origin type - "sdk", "webhook", or "api_response"
        provider: Provider name (e.g. "garmin", "apple", "strava")
        payload: Raw data (dict, list, or pre-serialized string)
        user_id: Optional user identifier for correlation
        trace_id: Optional trace/batch ID for correlation with processed data
    """
    if _storage_backend == "disabled":
        return

    payload_str = payload if isinstance(payload, str) else json.dumps(payload, default=json_serial)

    # Skip payloads that exceed size limit
    size = len(payload_str.encode("utf-8"))
    if size > _max_size_bytes:
        logger.warning(
            "Raw payload skipped (size %d bytes exceeds limit %d)",
            size,
            _max_size_bytes,
        )
        return

    if _storage_backend == "log":
        _store_to_log(source, provider, payload_str, size, user_id, trace_id)
    elif _storage_backend == "s3":
        _store_to_s3(source, provider, payload_str, size, user_id, trace_id)


def _store_to_log(
    source: str,
    provider: str,
    payload_str: str,
    size: int,
    user_id: str | None,
    trace_id: str | None,
) -> None:
    entry: dict[str, Any] = {
        "level": "debug",
        "message": "raw_payload",
        "source": source,
        "provider": provider,
        "size_bytes": size,
    }
    if user_id:
        entry["user_id"] = user_id
    if trace_id:
        entry["trace_id"] = trace_id
    entry["payload"] = payload_str

    print(json.dumps(entry), file=sys.stdout, flush=True)


def _store_to_s3(
    source: str,
    provider: str,
    payload_str: str,
    size: int,
    user_id: str | None,
    trace_id: str | None,
) -> None:
    """Upload raw payload to S3.

    Key format: {prefix}/{provider}/{source}/{YYYY-MM-DD}/{uuid}.json
    Metadata includes user_id, trace_id, and size for easy filtering.
    """
    if _s3_client is None or _s3_bucket is None:
        logger.warning("S3 client or bucket not configured - skipping raw payload storage")
        return

    now = datetime.now(UTC)
    date_part = now.strftime("%Y-%m-%d")
    file_id = uuid4().hex[:12]
    user_part = user_id if user_id else "_unknown"
    key = f"{_s3_prefix}/{provider}/{source}/{date_part}/{user_part}/{file_id}.json"

    metadata: dict[str, str] = {
        "source": source,
        "provider": provider,
        "size_bytes": str(size),
        "timestamp": now.isoformat(),
    }
    if user_id:
        metadata["user_id"] = user_id
    if trace_id:
        metadata["trace_id"] = trace_id

    try:
        _s3_client.put_object(
            Bucket=_s3_bucket,
            Key=key,
            Body=payload_str.encode("utf-8"),
            ContentType="application/json",
            Metadata=metadata,
        )
        logger.debug(
            "Stored raw payload to S3: s3://%s/%s (%d bytes)",
            _s3_bucket,
            key,
            size,
        )
    except Exception:
        logger.exception("Failed to store raw payload to S3: s3://%s/%s", _s3_bucket, key)
