"""Process-wide log output selected by LOG_FORMAT and LOG_LEVEL.

``legacy`` (the default) leaves the output exactly as it was before these settings
existed: ``log_structured`` prints JSON lines, stdlib loggers print plain text through
the handlers set up in ``app.main`` and the Celery ``setup_logging`` signal. ``json`` and
``text`` route every stdlib record through one stdout handler with a matching formatter;
``log_structured`` renders its own lines (see ``app.utils.structured_logging``).
"""

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

from app.config import settings
from app.integrations.otel import attach_handler, check_dependencies, is_export_handler
from app.utils.config_utils import LogFormat

# Loggers that come with their own level from uvicorn's or Celery's logging setup, so the
# root level alone would not apply LOG_LEVEL to them.
_FRAMEWORK_LOGGERS = ("uvicorn", "uvicorn.error", "celery")


def level_number(level: str) -> int:
    """Map a ``log_structured`` level string to a logging level. Unknown strings count as INFO."""
    return logging.getLevelNamesMapping().get(level.upper(), logging.INFO)


def min_log_level() -> int | None:
    """The LOG_LEVEL threshold, or None when LOG_LEVEL is not set."""
    if settings.log_level is None:
        return None
    return logging.getLevelNamesMapping()[settings.log_level.value]


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
        line = format_text_line(record.created, record.levelname, record.name, record.getMessage(), {})
        if record.exc_info:
            line = f"{line}\n{self.formatException(record.exc_info)}"
        if record.stack_info:
            line = f"{line}\n{self.formatStack(record.stack_info)}"
        return line


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname.lower(),
            "message": record.getMessage(),
            "logger": record.name,
        }
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            entry["stack"] = self.formatStack(record.stack_info)
        return json.dumps(entry, default=repr)


_FORMATTERS: dict[LogFormat, type[logging.Formatter]] = {
    LogFormat.JSON: JsonFormatter,
    LogFormat.TEXT: TextFormatter,
}


def configure_logging() -> None:
    """Apply LOG_FORMAT and LOG_LEVEL to the root, uvicorn and Celery loggers.

    Safe to call repeatedly. uvicorn re-applies its own logging config after the app
    module is imported (``fastapi run``), so the app lifespan calls this again, and so
    does the Celery ``setup_logging`` signal after it set up the ``celery`` logger.
    """
    check_dependencies()
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
