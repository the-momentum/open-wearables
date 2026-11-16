"""Process-wide log output selected by LOG_FORMAT and LOG_LEVEL.

App code logs through the ``app`` logger (see ``app.utils.structured_logging``). It has a
stdout handler of its own and does not propagate, so its lines look the same whatever the
root, uvicorn and Celery loggers are set up with: one JSON object per line in ``legacy``
(the default) and ``json``, a readable line in ``text``.

``legacy`` keeps the output of everything else as it was before these settings existed:
stdlib loggers print plain text through the handlers set up in ``app.main`` and the Celery
``setup_logging`` signal. ``json`` and ``text`` route every other stdlib record through one
stdout handler with a matching formatter.
"""

import json
import logging
import sys
import traceback
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from app.config import settings
from app.integrations.otel import attach_handler, check_dependencies, is_export_handler
from app.utils.config_utils import LogFormat

APP_LOGGER = "app"
# Record attribute holding what app code passed to the logger: {"provider", "attributes"}.
STRUCTURED = "structured"
# Line fields app attributes cannot replace.
BASE_FIELDS = frozenset({"timestamp", "level", "message", "provider"})
# Line fields of a record with an exception.
EXCEPTION_FIELDS = frozenset({"error_type", "traceback"})

# Loggers that come with their own level from uvicorn's or Celery's logging setup, so the
# root level alone would not apply LOG_LEVEL to them.
_FRAMEWORK_LOGGERS = ("uvicorn", "uvicorn.error", "celery")


def json_serial(obj: Any) -> str:
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, UUID):
        return str(obj)
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")


def min_log_level() -> int | None:
    """The LOG_LEVEL threshold, or None when LOG_LEVEL is not set."""
    if settings.log_level is None:
        return None
    return logging.getLevelNamesMapping()[settings.log_level.value]


def from_app_code(record: logging.LogRecord) -> bool:
    return record.name == APP_LOGGER or record.name.startswith(f"{APP_LOGGER}.")


def _structured(record: logging.LogRecord) -> tuple[str | None, dict[str, Any]]:
    structured = getattr(record, STRUCTURED, None) or {}
    return structured.get("provider"), structured.get("attributes") or {}


def _exception_type(record: logging.LogRecord) -> type[BaseException] | None:
    return record.exc_info[0] if record.exc_info else None


def _formatted_traceback(record: logging.LogRecord) -> str:
    return "".join(traceback.format_exception(*record.exc_info)).rstrip()  # ty: ignore[not-iterable]


def _app_fields(record: logging.LogRecord) -> dict[str, Any]:
    """Provider, attributes and exception fields of an app record, in line order."""
    provider, attributes = _structured(record)
    exc_type = _exception_type(record)
    reserved = BASE_FIELDS | EXCEPTION_FIELDS if exc_type is not None else BASE_FIELDS
    fields: dict[str, Any] = {"provider": provider}
    for key, value in attributes.items():
        # An attribute named like a base field must not replace it; keep its value apart.
        fields[f"attr_{key}" if key in reserved else key] = value
    if exc_type is not None:
        fields["error_type"] = exc_type.__name__
    return fields


def _text_value(value: Any) -> str:
    if isinstance(value, (dict, list, tuple)):
        # Already JSON, so only quote it when it contains whitespace.
        text = json.dumps(value, default=str, separators=(",", ":"))
        return json.dumps(text) if any(char.isspace() for char in text) else text
    text = value if isinstance(value, str) else str(value)
    if not text or any(char in text for char in ' ="\n'):
        return json.dumps(text)
    return text


def format_text_line(created: float, level: str, logger_name: str, message: str, fields: dict[str, Any]) -> str:
    """One human-readable line: local time, level, logger, message, then ``key=value`` pairs.

    Fields with a None value are left out.
    """
    timestamp = datetime.fromtimestamp(created).strftime("%H:%M:%S.%f")[:-3]
    line = f"{timestamp} {level.upper():<8} {logger_name}  {message}"
    pairs = " ".join(f"{key}={_text_value(value)}" for key, value in fields.items() if value is not None)
    return f"{line}  {pairs}" if pairs else line


class TextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        fields = _app_fields(record) if from_app_code(record) else {}
        line = format_text_line(record.created, record.levelname, record.name, record.getMessage(), fields)
        if record.exc_info:
            line = f"{line}\n{self.formatException(record.exc_info)}"
        if record.stack_info:
            line = f"{line}\n{self.formatStack(record.stack_info)}"
        return line


class JsonFormatter(logging.Formatter):
    """App records keep the fields app lines have always had: timestamp, level, message,
    provider, then the attributes. Other records carry the logger name and the exception."""

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created, timezone.utc).isoformat()
        if from_app_code(record):
            return self._format_app(record, timestamp)
        entry: dict[str, Any] = {
            "timestamp": timestamp,
            "level": record.levelname.lower(),
            "message": record.getMessage(),
            "logger": record.name,
        }
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            entry["stack"] = self.formatStack(record.stack_info)
        return json.dumps(entry, default=repr)

    def _format_app(self, record: logging.LogRecord, timestamp: str) -> str:
        entry = {
            "timestamp": timestamp,
            "level": record.levelname.lower(),
            "message": record.getMessage(),
            **_app_fields(record),
        }
        if _exception_type(record) is not None:
            entry["traceback"] = _formatted_traceback(record)
        try:
            return json.dumps(entry, default=json_serial)
        except TypeError:
            # Never lose the line over one value; tests make this raise at the call site.
            return json.dumps(entry, default=str)


class AppFormatter(logging.Formatter):
    """Formatter of the app handler; follows LOG_FORMAT at the time a record is written."""

    def __init__(self) -> None:
        super().__init__()
        self._json = JsonFormatter()
        self._text = TextFormatter()

    def format(self, record: logging.LogRecord) -> str:
        formatter = self._text if settings.log_format is LogFormat.TEXT else self._json
        return formatter.format(record)


class AppHandler(logging.StreamHandler):
    """Writes app lines to the current ``sys.stdout``.

    Stdout, not stderr: some platforms (Railway) turn stderr lines into errors, which would
    override the level in the JSON line. Looking up ``sys.stdout`` on every write, like
    ``print`` does, keeps redirections (pytest's capsys) working.
    """

    def __init__(self) -> None:
        super().__init__(sys.stdout)
        self.setFormatter(AppFormatter())

    @property
    def stream(self) -> Any:
        return sys.stdout

    @stream.setter
    def stream(self, value: Any) -> None:
        pass


def configure_app_logger() -> None:
    """Give the ``app`` logger its stdout handler and LOG_LEVEL (INFO when unset). Idempotent."""
    app_logger = logging.getLogger(APP_LOGGER)
    if not any(isinstance(handler, AppHandler) for handler in app_logger.handlers):
        app_logger.addHandler(AppHandler())
    app_logger.propagate = False
    level = min_log_level()
    app_logger.setLevel(logging.INFO if level is None else level)


_FORMATTERS: dict[LogFormat, type[logging.Formatter]] = {
    LogFormat.JSON: JsonFormatter,
    LogFormat.TEXT: TextFormatter,
}


def configure_logging() -> None:
    """Apply LOG_FORMAT and LOG_LEVEL to the app, root, uvicorn and Celery loggers.

    Safe to call repeatedly. uvicorn re-applies its own logging config after the app
    module is imported (``fastapi run``), so the app lifespan calls this again, and so
    does the Celery ``setup_logging`` signal after it set up the ``celery`` logger.
    """
    check_dependencies()
    configure_app_logger()
    root = logging.getLogger()
    level = min_log_level()

    if settings.log_format is not LogFormat.LEGACY:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(_FORMATTERS[settings.log_format]())
        for existing in root.handlers[:]:
            if not is_export_handler(existing):
                root.removeHandler(existing)
        root.addHandler(handler)
        root.setLevel(logging.INFO if level is None else level)
        for name in ("uvicorn", "uvicorn.error"):
            uvicorn_logger = logging.getLogger(name)
            uvicorn_logger.handlers.clear()
            uvicorn_logger.propagate = True

    if level is not None:
        for name in ("", *_FRAMEWORK_LOGGERS):
            target = logging.getLogger(name)
            target.setLevel(level)
            # Records from loggers with a level of their own (httpx, httpcore) reach the
            # handlers without passing these loggers' level, so filter at the handlers too.
            for handler in target.handlers:
                handler.setLevel(level)

    # uvicorn and Celery replace the handlers of their loggers; put the export handler back.
    attach_handler()
