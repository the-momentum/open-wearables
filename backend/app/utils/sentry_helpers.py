"""Helper functions for Sentry error reporting."""

from logging import Logger

import sentry_sdk


def log_and_capture_error(
    exception: Exception,
    logger: Logger,
    message: str,
    *,
    level: str = "error",
    extra: dict | None = None,
) -> None:
    """
    Log an error and capture it in Sentry.

    Use this for exceptions that are caught and handled gracefully,
    but still need to be reported to Sentry for monitoring.

    Args:
        exception: The exception to log and capture
        logger: Logger instance to use for logging
        message: Log message (can include format placeholders)
        level: Log level ('error', 'warning', 'info')
        extra: Optional extra context to attach to Sentry event

    Example:
        try:
            process_data(item)
        except ValidationError as e:
            log_and_capture_error(
                e,
                logger,
                f"Failed to process item {item.id}",
                extra={"item_id": item.id, "user_id": user.id}
            )
            # Continue processing other items
    """
    # Log with standard logger
    log_func = getattr(logger, level, logger.error)
    log_func(message, exc_info=True)

    # Capture in Sentry with optional extra context
    if extra:
        with sentry_sdk.push_scope() as scope:
            for key, value in extra.items():
                scope.set_context(key, {"value": value})
            sentry_sdk.capture_exception(exception)
    else:
        sentry_sdk.capture_exception(exception)
