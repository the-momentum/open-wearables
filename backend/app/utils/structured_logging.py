"""Structured logging utilities for JSON-compatible logs."""

import json
import sys
import uuid
from logging import Logger
from typing import Any


def json_serial(obj: Any) -> str:
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, uuid.UUID):
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

    This function emits logs in JSON format on a single line, making them compatible
    with platforms that support structured logging, including (but not limited to):
    - Railway
    - Vercel
    - Google Cloud Platform (Cloud Functions, Cloud Run)
    - Heroku
    - AWS Lambda (with CloudWatch)
    - Other platforms that collect logs from stdout/stderr


    Args:
        logger: Logger instance (used for compatibility, but output goes directly to stdout)
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
    log_entry = {
        "level": level.lower(),
        "message": message,
        "provider": provider,
        **attributes,
    }

    # Emit as single-line JSON directly to stdout
    # This bypasses logger formatters (like Celery's) that add prefixes
    # Platforms will parse this JSON string correctly
    json_str = json.dumps(log_entry, default=json_serial)

    # Always use stdout to avoid Railway's automatic level conversion
    # Platforms can convert stderr logs to level.error automatically, which creates
    # "attributes":{"level":"error"} that overrides our JSON level field.
    # By using stdout, platforms sets level.info by default, but our JSON level
    # field in the structured log should take precedence.
    #
    # IMPORTANT: Celery workers and other services must redirect stderr to stdout
    # in their startup scripts (using `exec 2>&1`) to prevent platforms from
    # converting all logs to level.error. See scripts/start/*.sh for examples.
    print(json_str, file=sys.stdout, flush=True)
