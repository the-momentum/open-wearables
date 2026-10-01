"""Structured logging utilities for JSON-compatible logs."""

import json
import sys
import time
from datetime import datetime, timezone
from logging import Logger
from typing import Any, NamedTuple
from uuid import UUID

from app.config import settings
from app.integrations.otel import export_structured
from app.utils.config_utils import LogFormat
from app.utils.context import trace_id_var
from app.utils.logging_setup import format_text_line, level_number, min_log_level


class LogContext(NamedTuple):
    """Per-request log fields threaded into downstream fetch/save logs.

    Lets callers pass the provider-side user id and trace id as a single
    argument instead of threading two separate params through every signature.
    Unpack at the top of a method:  ``provider_user_id, trace_id = log_ctx or LogContext()``.
    """

    provider_user_id: str | None = None
    trace_id: str | None = None


def json_serial(obj: Any) -> str:
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, UUID):
        return str(obj)
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")


def log_structured(
    logger: Logger,
    level: str,
    message: str,
    provider: str | None = None,
    **attributes: Any,
) -> None:
    """
    Emit structured JSON log compatible with various logging platforms.

    With ``LOG_FORMAT=legacy`` (default) or ``json`` this prints one JSON line to stdout;
    with ``LOG_FORMAT=text`` it prints a human-readable line instead. ``LOG_LEVEL``, when
    set, drops calls below that level.

    This function emits logs in JSON format on a single line, making them compatible
    with platforms that support structured logging, including (but not limited to):
    - Railway
    - Vercel
    - Google Cloud Platform (Cloud Functions, Cloud Run)
    - Heroku
    - AWS Lambda (with CloudWatch)
    - Other platforms that collect logs from stdout/stderr


    Args:
        logger: Logger whose name appears in text output; output goes directly to stdout
        level: Log level (debug, info, warning, error)
        message: Log message (required)
        provider: Provider name (optional)
        **attributes: Custom attributes to include (queryable via @name:value in log explorers)

    Example:
        log_structured(
            logger,
            "info",
            "Apple sync batch received",
            action="batch_received",
            batch_id="abc-123",
            user_id="user-456",
            records_count=2000,
            workouts_count=5,
            sleep_count=10
        )

    Platform-specific query examples:
        Railway: @batch_id:abc-123, @user_id:user-456 AND @level:info, @action:batch_received
        Vercel: Filter by JSON attributes in dashboard
        GCP: Use Cloud Logging filters with jsonPayload.batch_id="abc-123"
    """
    if attributes.get("trace_id") is None:
        tid = trace_id_var.get()
        if tid:
            attributes["trace_id"] = tid

    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": level.lower(),
        "message": message,
        "provider": provider,
        **attributes,
    }

    # Emit as single-line JSON directly to stdout
    # This bypasses logger formatters (like Celery's) that add prefixes
    # Platforms will parse this JSON string correctly
    # Serialized in every mode and before filtering, so an unserializable value raises the
    # same TypeError whatever LOG_FORMAT and LOG_LEVEL are set to.
    json_str = json.dumps(log_entry, default=json_serial)

    levelno = level_number(level)
    threshold = min_log_level()
    if threshold is not None and levelno < threshold:
        return

    if settings.log_format is LogFormat.TEXT:
        line = format_text_line(time.time(), level, logger.name, message, {"provider": provider, **attributes})
        print(line, file=sys.stdout, flush=True)
        export_structured(logger, levelno, message, provider, attributes)
        return

    # Always use stdout to avoid Railway's automatic level conversion
    # Platforms can convert stderr logs to level.error automatically, which creates
    # "attributes":{"level":"error"} that overrides our JSON level field.
    # By using stdout, platforms sets level.info by default, but our JSON level
    # field in the structured log should take precedence.
    print(json_str, file=sys.stdout, flush=True)
    export_structured(logger, levelno, message, provider, attributes)
