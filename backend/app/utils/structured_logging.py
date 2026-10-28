"""Structured logging: the single way app code writes logs.

    from app.utils.structured_logging import get_logger

    logger = get_logger(__name__)

    logger.info("Apple sync batch received", action="batch_received", batch_id="abc-123", user_id="u-456")

    try:
        process_item(item)
    except Exception as e:
        logger.error("Failed to process item", exc_info=e, item_id=item.id, user_id=user_id)

Records go through the standard ``logging`` module under the ``app`` logger, which prints
them as JSON lines (or readable lines with ``LOG_FORMAT=text``, see
``app.utils.logging_setup``) and exports them with OpenTelemetry. Sentry gets a line from
here, not from its logging integration (which ignores the ``app`` logger): an ``error`` with
an exception, unless LOG_LEVEL filters it out, and any line logged with ``alert=True``.
"""

import json
import logging
import sys
from typing import Any, NamedTuple

import sentry_sdk
from fastapi import HTTPException

from app.utils.context import trace_id_var
from app.utils.exceptions import AppError
from app.utils.logging_setup import (
    APP_LOGGER,
    BASE_FIELDS,
    EXCEPTION_FIELDS,
    STRUCTURED,
    configure_app_logger,
    json_serial,
)

__all__ = ["LogContext", "StructuredLogger", "get_logger", "json_serial", "strict_attributes"]

# Frames between the code that logs and Logger.log: the public method and _log.
_STACKLEVEL = 3


class LogContext(NamedTuple):
    """Per-request log fields threaded into downstream fetch/save logs.

    Lets callers pass the provider-side user id and trace id as a single
    argument instead of threading two separate params through every signature.
    Unpack at the top of a method:  ``provider_user_id, trace_id = log_ctx or LogContext()``.
    """

    provider_user_id: str | None = None
    trace_id: str | None = None


_strict = False


def strict_attributes(enabled: bool) -> None:
    """Check attributes at the call site: raise for a value JSON cannot serialize or a name
    that clashes with a line field. The test suite turns this on; otherwise the line is
    printed anyway, with ``str()`` of such values."""
    global _strict
    _strict = enabled


def _check_attributes(attributes: dict[str, Any], exc: BaseException | None) -> None:
    reserved = BASE_FIELDS | EXCEPTION_FIELDS if exc is not None else BASE_FIELDS
    if clashing := reserved.intersection(attributes):
        raise ValueError(f"Log attributes cannot be named {sorted(clashing)}; pick another name")
    json.dumps(attributes, default=json_serial)


def _exception(exc_info: Any) -> BaseException | None:
    if isinstance(exc_info, BaseException):
        return exc_info
    if isinstance(exc_info, tuple):
        return exc_info[1]
    return sys.exc_info()[1] if exc_info else None


def _is_client_error(exc: BaseException | None) -> bool:
    """4xx HTTPExceptions and AppErrors are explicit, handled client errors (e.g. a provider
    rejecting a token refresh): logged as warnings, kept out of Sentry."""
    if isinstance(exc, AppError):
        return exc.is_client_error
    return isinstance(exc, HTTPException) and 400 <= exc.status_code < 500


def _report(level: int, msg: str, exc: BaseException | None, context: dict[str, Any]) -> None:
    """Send one line to Sentry, its message and attributes as the ``log`` context.

    Set on the scope, so the SDK serializes the context (UUIDs, dates) like any other data.
    An exception is reported at ``error`` at least, also from a warning logged with
    ``alert=True``: the line's level is for the logs, a captured exception is an error.
    """
    if exc is not None:
        level = max(level, logging.ERROR)
    with sentry_sdk.new_scope() as scope:
        scope.set_level(logging.getLevelName(level).lower())  # ty: ignore[invalid-argument-type]
        scope.set_context("log", context)
        if exc is not None:
            sentry_sdk.capture_exception(exc)
        else:
            sentry_sdk.capture_message(msg)


class StructuredLogger:
    """A ``logging.Logger`` that takes the variable parts of a line as keyword arguments.

    Every method accepts:

    - ``exc_info``: an exception (or True inside ``except``) - adds ``error_type`` and
      ``traceback`` to the line. At ``error`` and above it is also reported to Sentry, unless
      LOG_LEVEL filters the line out; at ``warning`` it is not. 4xx ``HTTPException``\\s and
      ``AppError``\\s are logged as warnings.
    - ``provider``: provider name, printed right after the message.
    - ``alert``: always report the line to Sentry - without an exception, below ``error``,
      and also when LOG_LEVEL filters it out of the logs.
    - any other keyword: an attribute of the line (queryable via @name:value in log
      explorers). Keep values JSON-serializable and free of health data and PII.
    """

    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger

    @property
    def name(self) -> str:
        return self.logger.name

    def isEnabledFor(self, level: int, /) -> bool:  # noqa: N802 - mirrors logging.Logger
        return self.logger.isEnabledFor(level)

    def debug(self, msg: str, /, **kwargs: Any) -> None:
        self._log(logging.DEBUG, msg, **kwargs)

    def info(self, msg: str, /, **kwargs: Any) -> None:
        self._log(logging.INFO, msg, **kwargs)

    def warning(self, msg: str, /, **kwargs: Any) -> None:
        self._log(logging.WARNING, msg, **kwargs)

    def error(self, msg: str, /, **kwargs: Any) -> None:
        self._log(logging.ERROR, msg, **kwargs)

    def exception(self, msg: str, /, *, exc_info: Any = True, **kwargs: Any) -> None:
        self._log(logging.ERROR, msg, exc_info=exc_info, **kwargs)

    def critical(self, msg: str, /, **kwargs: Any) -> None:
        self._log(logging.CRITICAL, msg, **kwargs)

    def log(self, level: int, msg: str, /, **kwargs: Any) -> None:
        self._log(level, msg, **kwargs)

    def _log(
        self,
        level: int,
        msg: str,
        /,
        *,
        exc_info: Any = None,
        provider: str | None = None,
        alert: bool = False,
        **attributes: Any,
    ) -> None:
        exc = _exception(exc_info)
        if _strict:
            _check_attributes(attributes, exc)
        if level > logging.WARNING and _is_client_error(exc):
            level = logging.WARNING
        enabled = self.logger.isEnabledFor(level)
        if not (enabled or alert):
            return
        if attributes.get("trace_id") is None and (tid := trace_id_var.get()):
            attributes["trace_id"] = tid
        if enabled:
            self.logger.log(
                level,
                msg,
                exc_info=exc_info,
                stacklevel=_STACKLEVEL,
                extra={STRUCTURED: {"provider": provider, "attributes": attributes}},
            )
        if alert or (enabled and exc is not None and level >= logging.ERROR):
            context: dict[str, Any] = {"message": msg, "logger": self.logger.name, "provider": provider}
            for key, value in attributes.items():
                # Like on the line: an attribute must not replace a base field.
                context[f"attr_{key}" if key in context else key] = value
            _report(level, msg, exc, context)


def get_logger(name: str) -> StructuredLogger:
    """The logger for a module: ``logger = get_logger(__name__)``.

    Names outside the ``app`` package (scripts) are put under it, so every app line gets
    the same format and handling.
    """
    if name != APP_LOGGER and not name.startswith(f"{APP_LOGGER}."):
        name = f"{APP_LOGGER}.{name}"
    configure_app_logger()
    return StructuredLogger(logging.getLogger(name))
