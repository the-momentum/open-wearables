"""Optional raw payload storage for debugging incoming data.

Stores raw payloads received from SDKs, webhooks, and API responses.
Disabled by default - enable via RAW_PAYLOAD_STORAGE env var.

Usage (one-liner at ingestion point):
    store_raw_payload(source="webhook", provider="garmin", payload=data)
"""

import json
import logging
import sys
from typing import Any

from app.utils.structured_logging import json_serial

logger = logging.getLogger(__name__)

_storage_backend: str = "disabled"
_max_size_bytes: int = 10 * 1024 * 1024  # 10 MB


def configure(storage_backend: str, max_size_bytes: int) -> None:
    """Called once at startup from settings."""
    global _storage_backend, _max_size_bytes
    _storage_backend = storage_backend
    _max_size_bytes = max_size_bytes


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
