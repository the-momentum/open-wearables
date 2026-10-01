"""Tests for LOG_FORMAT / LOG_LEVEL and their effect on log_structured and stdlib logging.

The default (LOG_FORMAT=legacy, LOG_LEVEL unset) must keep the output exactly as it was
before these settings existed; the expected lines below were recorded from that code.
"""

import json
import logging
import os
import re
import subprocess
import sys
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

import pytest
import uvicorn
from fastapi.testclient import TestClient
from freezegun import freeze_time
from pydantic import ValidationError

from app.config import Settings, settings
from app.integrations.celery.core import setup_celery_logging
from app.main import api
from app.utils.config_utils import LogFormat, LogLevel
from app.utils.context import trace_id_var
from app.utils.logging_setup import JsonFormatter, TextFormatter, configure_logging
from app.utils.structured_logging import log_structured

FROZEN_AT = "2026-01-02T03:04:05.123456+00:00"
BACKEND_DIR = Path(__file__).resolve().parents[2]
LEGACY_FORMAT = "[%(asctime)s - %(name)s] (%(levelname)s) %(message)s"

logger = logging.getLogger("app.test_logging")


@pytest.fixture(autouse=True)
def _no_trace_id() -> Iterator[None]:
    """Other tests can leave a trace id in the context; these assert exact output."""
    token = trace_id_var.set(None)
    yield
    trace_id_var.reset(token)


@pytest.fixture
def restore_logging() -> Iterator[None]:
    """Snapshot and restore the logger and handler state that configure_logging and Celery change."""
    names = ["", "uvicorn", "uvicorn.error", "uvicorn.access", "celery", "httpx"]
    saved = {}
    for name in names:
        target = logging.getLogger(name)
        handlers = [(handler, handler.level) for handler in target.handlers]
        saved[name] = (handlers, target.level, target.propagate, target.disabled)
    trace_logger = logging.getLogger("celery.app.trace")
    saved_filters = trace_logger.filters[:]
    yield
    for name, (handlers, level, propagate, disabled) in saved.items():
        target = logging.getLogger(name)
        target.handlers[:] = [handler for handler, _ in handlers]
        for handler, handler_level in handlers:
            handler.setLevel(handler_level)
        target.setLevel(level)
        target.propagate = propagate
        target.disabled = disabled
    trace_logger.filters[:] = saved_filters


def _record(message: str, *args: object, exc: BaseException | None = None) -> logging.LogRecord:
    exc_info = (type(exc), exc, exc.__traceback__) if exc else None
    return logging.LogRecord("app.test_logging", logging.ERROR, __file__, 1, message, args, exc_info)


class TestLegacyOutputUnchanged:
    """With the defaults, log_structured prints exactly what it printed before."""

    @freeze_time(FROZEN_AT)
    @pytest.mark.parametrize(
        ("level", "message", "attributes", "expected"),
        [
            (
                "info",
                "Sync done",
                {"provider": "garmin", "user_id": "u1"},
                '{"timestamp": "2026-01-02T03:04:05.123456+00:00", "level": "info", "message": "Sync done", '
                '"provider": "garmin", "user_id": "u1"}',
            ),
            (
                "debug",
                "Debug lines are not filtered",
                {},
                '{"timestamp": "2026-01-02T03:04:05.123456+00:00", "level": "debug", '
                '"message": "Debug lines are not filtered", "provider": null}',
            ),
            (
                "WARN",
                "Level strings are lowercased, aliases kept",
                {},
                '{"timestamp": "2026-01-02T03:04:05.123456+00:00", "level": "warn", '
                '"message": "Level strings are lowercased, aliases kept", "provider": null}',
            ),
            (
                "bogus",
                "Unknown levels pass through",
                {},
                '{"timestamp": "2026-01-02T03:04:05.123456+00:00", "level": "bogus", '
                '"message": "Unknown levels pass through", "provider": null}',
            ),
            (
                "info",
                "msg %s literal",
                {"filename": "f.fit", "created": "c", "name": "n", "args": "a", "module": "m"},
                '{"timestamp": "2026-01-02T03:04:05.123456+00:00", "level": "info", "message": "msg %s literal", '
                '"provider": null, "filename": "f.fit", "created": "c", "name": "n", "args": "a", "module": "m"}',
            ),
            (
                "info",
                "uuid and nested values",
                {"id": UUID(int=1), "nested": {"a": [1, 2]}},
                '{"timestamp": "2026-01-02T03:04:05.123456+00:00", "level": "info", '
                '"message": "uuid and nested values", "provider": null, '
                '"id": "00000000-0000-0000-0000-000000000001", "nested": {"a": [1, 2]}}',
            ),
            (
                "info",
                "explicit none",
                {"trace_id": None},
                '{"timestamp": "2026-01-02T03:04:05.123456+00:00", "level": "info", "message": "explicit none", '
                '"provider": null, "trace_id": null}',
            ),
        ],
    )
    def test_line_matches_recorded_output(
        self,
        capsys: pytest.CaptureFixture[str],
        level: str,
        message: str,
        attributes: dict,
        expected: str,
    ) -> None:
        log_structured(logger, level, message, **attributes)

        assert capsys.readouterr().out == expected + "\n"

    @freeze_time(FROZEN_AT)
    def test_trace_id_from_context_keeps_the_caller_key_order(self, capsys: pytest.CaptureFixture[str]) -> None:
        token = trace_id_var.set("abcd1234")
        try:
            log_structured(logger, "info", "ctx trace", trace_id=None, after="x")
            log_structured(logger, "info", "explicit trace", trace_id="zz")
        finally:
            trace_id_var.reset(token)

        assert capsys.readouterr().out.splitlines() == [
            '{"timestamp": "2026-01-02T03:04:05.123456+00:00", "level": "info", "message": "ctx trace", '
            '"provider": null, "trace_id": "abcd1234", "after": "x"}',
            '{"timestamp": "2026-01-02T03:04:05.123456+00:00", "level": "info", "message": "explicit trace", '
            '"provider": null, "trace_id": "zz"}',
        ]

    def test_output_does_not_go_through_logging_handlers(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.DEBUG):
            log_structured(logger, "error", "not a log record")

        assert caplog.records == []

    def test_app_import_keeps_the_previous_stdlib_setup(self) -> None:
        """Importing app.main in a fresh process prints stdlib and structured lines as before."""
        code = (
            "import logging\n"
            "import app.main\n"
            "from app.utils.structured_logging import log_structured\n"
            "log = logging.getLogger('app.check')\n"
            "log.info('stdlib %s', 'line')\n"
            "log.debug('hidden')\n"
            "log_structured(log, 'debug', 'structured line')\n"
        )
        # Explicit values so a developer's config/.env cannot change the outcome.
        env = os.environ | {"LOG_FORMAT": "legacy", "LOG_LEVEL": "", "TELEMETRY_ENABLED": "false"}
        result = subprocess.run(
            [sys.executable, "-c", code], cwd=BACKEND_DIR, env=env, capture_output=True, text=True, timeout=120
        )

        assert result.returncode == 0, result.stderr
        lines = [line for line in result.stdout.splitlines() if "app.check" in line or "structured line" in line]
        assert len(lines) == 2, result.stdout
        assert re.fullmatch(r"\[\d{4}-\d\d-\d\d \d\d:\d\d:\d\d,\d{3} - app\.check\] \(INFO\) stdlib line", lines[0])
        assert re.fullmatch(
            r'\{"timestamp": "[^"]+", "level": "debug", "message": "structured line", "provider": null\}', lines[1]
        )
        assert "hidden" not in result.stdout

    def test_legacy_without_level_changes_nothing(self, restore_logging: None) -> None:
        root = logging.getLogger()
        handlers, level = root.handlers[:], root.level

        configure_logging()

        assert root.handlers == handlers
        assert root.level == level


class TestUnserializableValues:
    """An unserializable attribute raises in the caller in every mode, so text mode in
    development does not hide a crash that legacy or json mode would hit in production."""

    @pytest.mark.parametrize("log_format", [LogFormat.LEGACY, LogFormat.JSON, LogFormat.TEXT])
    def test_raises_in_every_format(self, log_format: LogFormat) -> None:
        with patch.object(settings, "log_format", log_format), pytest.raises(TypeError, match="not JSON serializable"):
            log_structured(logger, "info", "bad", value=datetime(2026, 1, 1))

    def test_raises_even_when_the_level_is_filtered_out(self) -> None:
        with patch.object(settings, "log_level", LogLevel.ERROR), pytest.raises(TypeError):
            log_structured(logger, "debug", "bad", value=object())


class TestLogLevel:
    @pytest.mark.parametrize(
        ("level", "printed"),
        [("debug", False), ("info", False), ("bogus", False), ("warning", True), ("warn", True), ("error", True)],
    )
    def test_log_structured_respects_log_level(
        self, capsys: pytest.CaptureFixture[str], level: str, printed: bool
    ) -> None:
        with patch.object(settings, "log_level", LogLevel.WARNING):
            log_structured(logger, level, "gated")

        assert bool(capsys.readouterr().out) is printed

    def test_applied_to_root_and_framework_loggers(self, restore_logging: None) -> None:
        with patch.object(settings, "log_level", LogLevel.WARNING):
            configure_logging()

        for name in ("", "uvicorn", "uvicorn.error", "celery"):
            assert logging.getLogger(name).level == logging.WARNING

    @pytest.mark.parametrize("log_format", [LogFormat.LEGACY, LogFormat.JSON])
    def test_applies_to_loggers_with_their_own_level(
        self, restore_logging: None, capsys: pytest.CaptureFixture[str], log_format: LogFormat
    ) -> None:
        """httpx keeps WARNING from app.main; LOG_LEVEL=ERROR still hides its warnings."""
        root = logging.getLogger()
        root.handlers[:] = [logging.StreamHandler(sys.stdout)]
        with patch.object(settings, "log_format", log_format), patch.object(settings, "log_level", LogLevel.ERROR):
            configure_logging()
            logging.getLogger("httpx").warning("httpx warning")
            logging.getLogger("app.test_logging").error("app error")

        out = capsys.readouterr().out
        assert "httpx warning" not in out
        assert "app error" in out


class TestSettings:
    @pytest.mark.parametrize(
        ("raw", "expected"), [("warning", LogLevel.WARNING), (" Debug ", LogLevel.DEBUG), ("", None)]
    )
    def test_log_level_is_normalized(self, raw: str, expected: LogLevel | None) -> None:
        assert Settings(log_level=raw).log_level == expected

    @pytest.mark.parametrize(("raw", "expected"), [("warn", LogLevel.WARNING), ("FATAL", LogLevel.CRITICAL)])
    def test_logging_aliases_are_accepted(self, raw: str, expected: LogLevel) -> None:
        assert Settings(log_level=raw).log_level == expected

    @pytest.mark.parametrize("raw", ["verbose", "NOTSET", "trace"])
    def test_unknown_log_level_is_ignored_with_a_warning(self, raw: str) -> None:
        with pytest.warns(UserWarning, match="Ignoring LOG_LEVEL"):
            assert Settings(log_level=raw).log_level is None

    @pytest.mark.parametrize(
        ("raw", "expected"), [("JSON", LogFormat.JSON), (" text ", LogFormat.TEXT), ("", LogFormat.LEGACY)]
    )
    def test_log_format_is_normalized(self, raw: str, expected: LogFormat) -> None:
        assert Settings(log_format=raw).log_format is expected

    def test_invalid_log_format_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Settings(log_format="xml")

    def test_defaults_keep_legacy_behaviour(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("LOG_FORMAT", raising=False)
        monkeypatch.delenv("LOG_LEVEL", raising=False)

        defaults = Settings(_env_file=None)  # ty: ignore[unknown-argument]

        assert defaults.log_format is LogFormat.LEGACY
        assert defaults.log_level is None


class TestTextFormat:
    def test_log_structured_prints_a_readable_line(self, capsys: pytest.CaptureFixture[str]) -> None:
        with patch.object(settings, "log_format", LogFormat.TEXT):
            log_structured(
                logger,
                "warning",
                "Sync failed",
                provider="garmin",
                user_id="u1",
                error="timed out after 30s",
                details={"retry": 2},
                trace_id=None,
            )

        line = capsys.readouterr().out.rstrip("\n")
        assert re.fullmatch(
            r"\d\d:\d\d:\d\d\.\d{3} WARNING  app\.test_logging  Sync failed  "
            r'provider=garmin user_id=u1 error="timed out after 30s" details=\{"retry":2\}',
            line,
        ), line

    def test_stdlib_formatter(self) -> None:
        try:
            raise ValueError("boom")
        except ValueError as error:
            line = TextFormatter().format(_record("failed %s", "x", exc=error))

        first, *rest = line.splitlines()
        assert re.fullmatch(r"\d\d:\d\d:\d\d\.\d{3} ERROR    app\.test_logging  failed x", first)
        assert rest[-1] == "ValueError: boom"


class TestJsonFormat:
    @freeze_time(FROZEN_AT)
    def test_log_structured_output_matches_legacy(self, capsys: pytest.CaptureFixture[str]) -> None:
        with patch.object(settings, "log_format", LogFormat.JSON):
            log_structured(logger, "info", "Sync done", provider="garmin", user_id="u1")

        assert capsys.readouterr().out == (
            '{"timestamp": "2026-01-02T03:04:05.123456+00:00", "level": "info", "message": "Sync done", '
            '"provider": "garmin", "user_id": "u1"}\n'
        )

    def test_stdlib_formatter(self) -> None:
        try:
            raise ValueError("boom")
        except ValueError as error:
            entry = json.loads(JsonFormatter().format(_record("failed %s", "x", exc=error)))

        assert entry["level"] == "error"
        assert entry["message"] == "failed x"
        assert entry["logger"] == "app.test_logging"
        assert entry["exception"].endswith("ValueError: boom")
        assert entry["timestamp"].endswith("+00:00")


class TestConfigureLogging:
    @pytest.mark.parametrize("log_format", [LogFormat.JSON, LogFormat.TEXT])
    def test_routes_everything_through_one_stdout_handler(self, restore_logging: None, log_format: LogFormat) -> None:
        uvicorn_logger = logging.getLogger("uvicorn")
        uvicorn_logger.addHandler(logging.StreamHandler(sys.stderr))
        uvicorn_logger.propagate = False

        with patch.object(settings, "log_format", log_format):
            configure_logging()
            configure_logging()

        root = logging.getLogger()
        assert len(root.handlers) == 1
        assert root.handlers[0].stream is sys.stdout  # ty: ignore[unresolved-attribute]
        expected = JsonFormatter if log_format is LogFormat.JSON else TextFormatter
        assert isinstance(root.handlers[0].formatter, expected)
        assert root.level == logging.INFO
        for name in ("uvicorn", "uvicorn.error"):
            assert logging.getLogger(name).handlers == []
            assert logging.getLogger(name).propagate is True

    def test_lifespan_reapplies_the_format_after_uvicorn_configures_logging(self, restore_logging: None) -> None:
        """`fastapi run` imports the app, then uvicorn applies its own logging config."""
        with patch.object(settings, "log_format", LogFormat.JSON):
            configure_logging()
            uvicorn.Config(api).configure_logging()
            assert logging.getLogger("uvicorn").handlers != []

            with TestClient(api):
                pass

        for name in ("uvicorn", "uvicorn.error"):
            assert logging.getLogger(name).handlers == []
            assert logging.getLogger(name).propagate is True
        assert isinstance(logging.getLogger().handlers[0].formatter, JsonFormatter)


class TestCeleryLogging:
    def test_legacy_keeps_the_celery_handler(self, restore_logging: None) -> None:
        setup_celery_logging()

        celery_logger = logging.getLogger("celery")
        assert celery_logger.propagate is False
        assert len(celery_logger.handlers) == 1
        formatter = celery_logger.handlers[0].formatter
        assert formatter is not None
        assert formatter._fmt == LEGACY_FORMAT
        assert formatter.datefmt == "%Y-%m-%d %H:%M:%S"
        assert celery_logger.level == logging.INFO

    @pytest.mark.parametrize("log_format", [LogFormat.JSON, LogFormat.TEXT])
    def test_other_formats_propagate_to_the_root_handler(self, restore_logging: None, log_format: LogFormat) -> None:
        with patch.object(settings, "log_format", log_format):
            setup_celery_logging()

        celery_logger = logging.getLogger("celery")
        assert celery_logger.handlers == []
        assert celery_logger.propagate is True
