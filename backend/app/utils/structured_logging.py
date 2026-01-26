"""Structured logging utilities for JSON-compatible logs."""

import json
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

    Log format requirements:
    - `level`: Log level (debug, info, warn, error)
    - `message`: Log message (required)
    - Custom attributes: Any additional key-value pairs (queryable in log explorers)

    Args:
        logger: Logger instance
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

    # Emit as single-line JSON (required by most log aggregation platforms)
    log_func = getattr(logger, level.lower(), logger.info)
    log_func(json.dumps(log_entry))
