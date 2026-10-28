"""Tests for the app logger and for LOG_FORMAT / LOG_LEVEL and their effect on app and stdlib logging.

The default (LOG_FORMAT=legacy, LOG_LEVEL unset) must keep the output exactly as it was
before these settings existed; the expected lines below were recorded from that code. The one
exception: debug lines are dropped unless LOG_LEVEL=DEBUG.
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
from fastapi import HTTPException
from fastapi.testclient import TestClient
from freezegun import freeze_time
from pydantic import ValidationError

from app.config import Settings, settings
from app.integrations.celery.core import setup_celery_logging
from app.main import api
from app.utils.config_utils import LogFormat, LogLevel
from app.utils.context import trace_id_var
from app.utils.exceptions import (
    AppError,
    ConfigurationError,
    NotFoundError,
    ProviderError,
    ProviderRateLimitError,
    ServiceUnavailableError,
)
from app.utils.logging_setup import AppHandler, JsonFormatter, TextFormatter, configure_app_logger, configure_logging
from app.utils.structured_logging import get_logger, strict_attributes

FROZEN_AT = "2026-01-02T03:04:05.123456+00:00"
BACKEND_DIR = Path(__file__).resolve().parents[2]
LEGACY_FORMAT = "[%(asctime)s - %(name)s] (%(levelname)s) %(message)s"

logger = get_logger("app.test_logging")


@pytest.fixture(autouse=True)
def _no_trace_id() -> Iterator[None]:
    """Other tests can leave a trace id in the context; these assert exact output."""
    token = trace_id_var.set(None)
    yield
    trace_id_var.reset(token)


@pytest.fixture
def restore_logging() -> Iterator[None]:
    """Snapshot and restore the logger and handler state that configure_logging and Celery change."""
    names = ["", "app", "uvicorn", "uvicorn.error", "uvicorn.access", "celery", "httpx"]
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


@pytest.fixture
def lenient() -> Iterator[None]:
    """Production behaviour: attribute problems do not raise at the call site."""
    strict_attributes(False)
    yield
    strict_attributes(True)


def _record(name: str, message: str, *args: object, exc: BaseException | None = None) -> logging.LogRecord:
    exc_info = (type(exc), exc, exc.__traceback__) if exc else None
    return logging.LogRecord(name, logging.ERROR, __file__, 1, message, args, exc_info)


def _raised(exc: Exception) -> Exception:
    try:
        raise exc
    except Exception as caught:
        return caught


def _with_log_level(level: LogLevel | None) -> None:
    with patch.object(settings, "log_level", level):
        configure_app_logger()


class TestLegacyOutputUnchanged:
    """With the defaults, the app logger prints exactly what log_structured printed before."""

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
                "warning",
                "Level names are lowercased",
                {},
                '{"timestamp": "2026-01-02T03:04:05.123456+00:00", "level": "warning", '
                '"message": "Level names are lowercased", "provider": null}',
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
        getattr(logger, level)(message, **attributes)

        assert capsys.readouterr().out == expected + "\n"

    @freeze_time(FROZEN_AT)
    def test_trace_id_from_context_keeps_the_caller_key_order(self, capsys: pytest.CaptureFixture[str]) -> None:
        token = trace_id_var.set("abcd1234")
        try:
            logger.info("ctx trace", trace_id=None, after="x")
            logger.info("explicit trace", trace_id="zz")
        finally:
            trace_id_var.reset(token)

        assert capsys.readouterr().out.splitlines() == [
            '{"timestamp": "2026-01-02T03:04:05.123456+00:00", "level": "info", "message": "ctx trace", '
            '"provider": null, "trace_id": "abcd1234", "after": "x"}',
            '{"timestamp": "2026-01-02T03:04:05.123456+00:00", "level": "info", "message": "explicit trace", '
            '"provider": null, "trace_id": "zz"}',
        ]

    def test_app_records_do_not_reach_the_root_handlers(self) -> None:
        records: list[logging.LogRecord] = []

        class Keep(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                records.append(record)

        keep = Keep()
        logging.getLogger().addHandler(keep)
        try:
            logger.error("not printed twice")
        finally:
            logging.getLogger().removeHandler(keep)

        assert records == []

    def test_the_alert_flag_is_not_printed(self, capsys: pytest.CaptureFixture[str]) -> None:
        with patch("app.utils.structured_logging.sentry_sdk"):
            logger.warning("flagged", alert=True)

        assert "alert" not in json.loads(capsys.readouterr().out)

    def test_app_import_keeps_the_previous_stdlib_setup(self) -> None:
        """Importing app.main in a fresh process prints library lines as before, app lines as JSON."""
        code = (
            "import logging\n"
            "import app.main\n"
            "from app.utils.structured_logging import get_logger\n"
            "check = logging.getLogger('library.check')\n"
            "check.info('stdlib %s', 'line')\n"
            "check.debug('hidden')\n"
            "app_logger = get_logger('app.check')\n"
            "app_logger.debug('hidden structured line')\n"
            "app_logger.info('structured line')\n"
            "logging.getLogger('app.plain').info('plain app %s', 'line')\n"
        )
        # Explicit values so a developer's config/.env cannot change the outcome.
        env = os.environ | {"LOG_FORMAT": "legacy", "LOG_LEVEL": "", "TELEMETRY_ENABLED": "false"}
        result = subprocess.run(
            [sys.executable, "-c", code], cwd=BACKEND_DIR, env=env, capture_output=True, text=True, timeout=120
        )

        assert result.returncode == 0, result.stderr
        lines = [
            line
            for line in result.stdout.splitlines()
            if "library.check" in line or "structured line" in line or "plain app" in line
        ]
        assert len(lines) == 3, result.stdout
        assert re.fullmatch(r"\[\d{4}-\d\d-\d\d \d\d:\d\d:\d\d,\d{3} - library\.check\] \(INFO\) stdlib line", lines[0])
        assert re.fullmatch(
            r'\{"timestamp": "[^"]+", "level": "info", "message": "structured line", "provider": null\}', lines[1]
        )
        assert re.fullmatch(
            r'\{"timestamp": "[^"]+", "level": "info", "message": "plain app line", "provider": null\}', lines[2]
        )
        assert "hidden" not in result.stdout

    def test_legacy_without_level_changes_nothing(self, restore_logging: None) -> None:
        root = logging.getLogger()
        handlers, level = root.handlers[:], root.level

        configure_logging()

        assert root.handlers == handlers
        assert root.level == level


class TestAppLogger:
    def test_names_outside_the_app_package_are_put_under_it(self) -> None:
        assert get_logger("scripts.init.create_svix_db").name == "app.scripts.init.create_svix_db"
        assert get_logger("app.services.x").name == "app.services.x"

    def test_records_point_at_the_calling_code(self) -> None:
        records: list[logging.LogRecord] = []

        class Keep(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                records.append(record)

        keep = Keep()
        logging.getLogger("app").addHandler(keep)
        try:
            logger.info("where")
            logger.log(logging.WARNING, "where")
        finally:
            logging.getLogger("app").removeHandler(keep)

        assert [record.funcName for record in records] == ["test_records_point_at_the_calling_code"] * 2
        assert {record.pathname for record in records} == {__file__}

    def test_configured_once(self, restore_logging: None) -> None:
        configure_logging()
        configure_logging()
        get_logger("app.another")

        app_logger = logging.getLogger("app")
        assert len([handler for handler in app_logger.handlers if isinstance(handler, AppHandler)]) == 1
        assert app_logger.propagate is False


class TestExceptions:
    def test_exception_is_logged_with_its_traceback(self, capsys: pytest.CaptureFixture[str]) -> None:
        logger.error("Sync failed", exc_info=_raised(ValueError("boom")), provider="garmin", user_id="u1")

        entry = json.loads(capsys.readouterr().out)
        assert entry["level"] == "error"
        assert entry["provider"] == "garmin"
        assert entry["user_id"] == "u1"
        assert entry["error_type"] == "ValueError"
        assert entry["traceback"].startswith("Traceback (most recent call last):")
        assert entry["traceback"].endswith("ValueError: boom")
        assert "error" not in entry

    def test_warnings_keep_the_traceback(self, capsys: pytest.CaptureFixture[str]) -> None:
        try:
            raise ValueError("boom")
        except ValueError:
            logger.warning("Marker unavailable", exc_info=True)

        entry = json.loads(capsys.readouterr().out)
        assert entry["level"] == "warning"
        assert entry["traceback"].endswith("ValueError: boom")

    def test_error_attribute_without_exception(self, capsys: pytest.CaptureFixture[str]) -> None:
        logger.error("Sync failed", error="boom")

        entry = json.loads(capsys.readouterr().out)
        assert entry["error"] == "boom"
        assert "traceback" not in entry

    def test_client_errors_are_warnings(self, capsys: pytest.CaptureFixture[str]) -> None:
        logger.error("Token refresh rejected", exc_info=_raised(HTTPException(status_code=401)))
        logger.error("Provider failed", exc_info=_raised(HTTPException(status_code=502)))
        logger.error("User missing", exc_info=_raised(NotFoundError("User not found.")))
        logger.error("Invariant broken", exc_info=_raised(AppError("boom")))

        levels = [json.loads(line)["level"] for line in capsys.readouterr().out.splitlines()]
        assert levels == ["warning", "error", "warning", "error"]

    def test_failed_provider_and_storage_calls_are_warnings(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Not our bug, unlike a missing setting."""
        logger.error("Garmin down", exc_info=_raised(ProviderError("garmin", upstream_status=503)))
        logger.error("Garmin throttled", exc_info=_raised(ProviderRateLimitError("garmin", upstream_status=429)))
        logger.error("S3 down", exc_info=_raised(ServiceUnavailableError("Failed to complete upload: SlowDown")))
        logger.error("S3 unset", exc_info=_raised(ConfigurationError("S3 bucket not configured")))

        levels = [json.loads(line)["level"] for line in capsys.readouterr().out.splitlines()]
        assert levels == ["warning", "warning", "warning", "error"]

    def test_text_format_prints_the_traceback_below_the_line(self, capsys: pytest.CaptureFixture[str]) -> None:
        with patch.object(settings, "log_format", LogFormat.TEXT):
            logger.error("Sync failed", exc_info=_raised(ValueError("boom")), user_id="u1")

        first, *rest = capsys.readouterr().out.rstrip("\n").splitlines()
        assert first.endswith("Sync failed  user_id=u1 error_type=ValueError")
        assert rest[0] == "Traceback (most recent call last):"
        assert rest[-1] == "ValueError: boom"


class TestAttributeChecks:
    """In tests a bad attribute raises at the call site in every mode, so text mode in
    development does not hide what legacy or json mode would print in production."""

    @pytest.mark.parametrize("log_format", [LogFormat.LEGACY, LogFormat.JSON, LogFormat.TEXT])
    def test_unserializable_value_raises_in_every_format(self, log_format: LogFormat) -> None:
        with patch.object(settings, "log_format", log_format), pytest.raises(TypeError, match="not JSON serializable"):
            logger.info("bad", value=datetime(2026, 1, 1))

    def test_raises_even_when_the_level_is_filtered_out(self) -> None:
        with pytest.raises(TypeError):
            logger.debug("bad", value=object())

    @pytest.mark.parametrize("name", ["timestamp", "level", "message"])
    def test_base_field_names_are_rejected(self, name: str) -> None:
        with pytest.raises(ValueError, match="cannot be named"):
            logger.info("clash", **{name: "x"})

    @pytest.mark.parametrize("name", ["error_type", "traceback"])
    def test_exception_field_names_are_rejected_with_an_exception(self, name: str) -> None:
        with pytest.raises(ValueError, match="cannot be named"):
            logger.warning("clash", exc_info=ValueError("boom"), **{name: "x"})

    def test_exception_field_names_are_allowed_without_an_exception(self, capsys: pytest.CaptureFixture[str]) -> None:
        logger.warning("no clash", error_type="ValueError")

        assert json.loads(capsys.readouterr().out)["error_type"] == "ValueError"

    def test_in_production_an_exception_field_keeps_its_value_apart(
        self, lenient: None, capsys: pytest.CaptureFixture[str]
    ) -> None:
        logger.warning("clash", exc_info=_raised(ValueError("boom")), error_type="custom")

        line = json.loads(capsys.readouterr().out)
        assert (line["error_type"], line["attr_error_type"]) == ("ValueError", "custom")

    @freeze_time(FROZEN_AT)
    def test_in_production_the_line_is_printed_anyway(self, lenient: None, capsys: pytest.CaptureFixture[str]) -> None:
        logger.info("odd values", value=datetime(2026, 1, 1), timestamp="from a header", message="other")

        assert capsys.readouterr().out == (
            '{"timestamp": "2026-01-02T03:04:05.123456+00:00", "level": "info", "message": "odd values", '
            '"provider": null, "value": "2026-01-01 00:00:00", "attr_timestamp": "from a header", '
            '"attr_message": "other"}\n'
        )


class TestLogLevel:
    @pytest.mark.parametrize(
        ("level", "printed"), [("debug", False), ("info", False), ("warning", True), ("error", True)]
    )
    def test_app_logger_respects_log_level(
        self, restore_logging: None, capsys: pytest.CaptureFixture[str], level: str, printed: bool
    ) -> None:
        _with_log_level(LogLevel.WARNING)
        getattr(logger, level)("gated")

        assert bool(capsys.readouterr().out) is printed

    def test_debug_is_dropped_unless_log_level_asks_for_it(
        self, restore_logging: None, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _with_log_level(None)
        logger.debug("hidden")
        _with_log_level(LogLevel.DEBUG)
        logger.debug("shown")

        assert [json.loads(line)["message"] for line in capsys.readouterr().out.splitlines()] == ["shown"]

    def test_critical_level_drops_errors(self, restore_logging: None, capsys: pytest.CaptureFixture[str]) -> None:
        """The record is never created, so it does not reach Sentry either (documented)."""
        _with_log_level(LogLevel.CRITICAL)
        logger.error("Sync failed", exc_info=_raised(ValueError("boom")))

        assert capsys.readouterr().out == ""

    def test_applied_to_app_root_and_framework_loggers(self, restore_logging: None) -> None:
        with patch.object(settings, "log_level", LogLevel.WARNING):
            configure_logging()

        for name in ("", "app", "uvicorn", "uvicorn.error", "celery"):
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
            logging.getLogger("library.test_logging").error("library error")

        out = capsys.readouterr().out
        assert "httpx warning" not in out
        assert "library error" in out


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
    def test_app_logger_prints_a_readable_line(self, capsys: pytest.CaptureFixture[str]) -> None:
        with patch.object(settings, "log_format", LogFormat.TEXT):
            logger.warning(
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
        line = TextFormatter().format(
            _record("library.test_logging", "failed %s", "x", exc=_raised(ValueError("boom")))
        )

        first, *rest = line.splitlines()
        assert re.fullmatch(r"\d\d:\d\d:\d\d\.\d{3} ERROR    library\.test_logging  failed x", first)
        assert rest[-1] == "ValueError: boom"


class TestJsonFormat:
    @freeze_time(FROZEN_AT)
    def test_app_logger_output_matches_legacy(self, capsys: pytest.CaptureFixture[str]) -> None:
        with patch.object(settings, "log_format", LogFormat.JSON):
            logger.info("Sync done", provider="garmin", user_id="u1")

        assert capsys.readouterr().out == (
            '{"timestamp": "2026-01-02T03:04:05.123456+00:00", "level": "info", "message": "Sync done", '
            '"provider": "garmin", "user_id": "u1"}\n'
        )

    def test_stdlib_formatter(self) -> None:
        record = _record("library.test_logging", "failed %s", "x", exc=_raised(ValueError("boom")))
        entry = json.loads(JsonFormatter().format(record))

        assert entry["level"] == "error"
        assert entry["message"] == "failed x"
        assert entry["logger"] == "library.test_logging"
        assert entry["exception"].endswith("ValueError: boom")
        assert entry["timestamp"].endswith("+00:00")

    def test_app_records_without_attributes_get_the_app_fields(self) -> None:
        entry = json.loads(JsonFormatter().format(_record("app.test_logging", "failed %s", "x")))

        assert list(entry) == ["timestamp", "level", "message", "provider"]
        assert entry["message"] == "failed x"


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
        assert logging.getLogger("app").propagate is False


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
