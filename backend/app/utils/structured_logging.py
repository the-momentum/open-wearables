"""Structured logging utilities for JSON-compatible logs."""

import json
import sys
from logging import Logger
from typing import Any


def log_structured(
    logger: Logger,
    level: str,
    message: str,
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

    According to Railway documentation, structured logs must be:
    - Emitted as a single-line JSON string
    - Include `level` and `message` fields
    - Custom attributes are queryable via @name:value

    Args:
        logger: Logger instance (used for compatibility, but output goes directly to stdout)
        level: Log level (debug, info, warn, error)
        message: Log message (required)
        **attributes: Custom attributes to include (queryable via @name:value in log explorers)

    Example:
        log_structured(
            logger,
            "info",
            "Apple sync batch received",
            batch_id="abc-123",
            user_id="user-456",
            records_count=2000,
            workouts_count=5,
            sleep_count=10
        )

    Platform-specific query examples:
        Railway: @batch_id:abc-123, @user_id:user-456 AND @level:info
        Vercel: Filter by JSON attributes in dashboard
        GCP: Use Cloud Logging filters with jsonPayload.batch_id="abc-123"
    """
    log_entry = {
        "level": level.lower(),
        "message": message,
        **attributes,
    }

    # Emit as single-line JSON directly to stdout
    # This bypasses logger formatters (like Celery's) that add prefixes
    # Railway will parse this JSON string correctly
    json_str = json.dumps(log_entry)

    # Always use stdout to avoid Railway's automatic level conversion
    # Railway converts stderr logs to level.error automatically, which creates
    # "attributes":{"level":"error"} that overrides our JSON level field.
    # By using stdout, Railway sets level.info by default, but our JSON level
    # field in the structured log should take precedence.
    # Note: If Celery redirects stdout to stderr, we may still see this issue.
    # In that case, the JSON level field should still be queryable via @level:info
    print(json_str, file=sys.stdout, flush=True)
