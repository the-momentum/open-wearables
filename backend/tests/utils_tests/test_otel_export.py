"""Tests for the optional OpenTelemetry log export (OTEL_ENABLED).

Skipped when the `otel` extra is not installed; test_otel_wiring.py covers what must work
without it.
"""

import dataclasses
import logging
import threading
import time
from collections.abc import Iterator
from fnmatch import fnmatch
from typing import Any
from unittest.mock import patch
from uuid import UUID

import pytest
from pydantic import BaseModel, field_serializer

from app.config import settings
from app.integrations import otel
from app.integrations.celery import core as celery_core
from app.utils.config_utils import LogFormat, LogLevel
from app.utils.context import trace_id_var
from app.utils.structured_logging import log_structured

sdk_export = pytest.importorskip("opentelemetry.sdk._logs.export", reason="needs the otel extra")

logger = logging.getLogger("app.test_otel")


@pytest.fixture(autouse=True)
def _no_trace_id() -> Iterator[None]:
    """Other tests can leave a trace id in the context; these assert exact output."""
    token = trace_id_var.set(None)
    yield
    trace_id_var.reset(token)


@pytest.fixture
def exporter() -> Iterator[Any]:
    """Enable export for the test, with an in-memory pipeline instead of OTLP."""
    memory = sdk_export.InMemoryLogRecordExporter()
    with patch.object(settings, "otel_enabled", True):
        otel.init_otel("open-wearables-test", processor=sdk_export.SimpleLogRecordProcessor(memory))
        try:
            yield memory
        finally:
            otel.shutdown_otel()


def _exported(memory: Any) -> list[Any]:
    return list(memory.get_finished_logs())


def _attributes(item: Any) -> dict[str, Any]:
    return dict(item.log_record.attributes or {})


class TestStructuredExport:
    def test_attributes_are_namespaced_and_converted(self, exporter: Any) -> None:
        log_structured(
            logger,
            "warning",
            "Sync failed for %s",
            provider="garmin",
            user_id=UUID(int=1),
            filename="activity.fit",
            retries=2,
            tags=["a", "b"],
            huge=2**70,
            empty=None,
        )

        [item] = _exported(exporter)
        assert item.log_record.body == "Sync failed for %s"
        assert item.log_record.severity_text == "WARN"
        attributes = _attributes(item)
        assert attributes["app.provider"] == "garmin"
        assert attributes["app.user_id"] == "00000000-0000-0000-0000-000000000001"
        assert attributes["app.filename"] == "activity.fit"
        assert attributes["app.retries"] == 2
        assert list(attributes["app.tags"]) == ["a", "b"]
        assert attributes["app.huge"] == str(2**70)
        assert "app.empty" not in attributes
        assert "structured" not in attributes
        assert not any(key.startswith("code.") for key in attributes)

    def test_app_trace_id_does_not_take_the_otlp_trace_id(self, exporter: Any) -> None:
        token = trace_id_var.set("abcd1234")
        try:
            log_structured(logger, "info", "with trace")
        finally:
            trace_id_var.reset(token)

        [item] = _exported(exporter)
        assert _attributes(item)["app.trace_id"] == "abcd1234"

    def test_sensitive_values_are_redacted(self, exporter: Any) -> None:
        with patch.object(settings, "otel_export_redact_keys", "Email, device-serial"):
            log_structured(
                logger,
                "info",
                "redaction",
                access_token="t0ken",
                client_secret="s3cret",
                id_token="jwt",
                email="person@example.com",
                body_preview="raw body",
                payload={
                    "device_serial": "SN1",
                    "X-Api-Key": "k",
                    "Cookie": "c",
                    "nested": [{"password": "p"}],
                    "kept": "yes",
                },
            )

        attributes = _attributes(_exported(exporter)[0])
        for key in ("app.access_token", "app.client_secret", "app.id_token", "app.email", "app.body_preview"):
            assert attributes[key] == "REDACTED", key
        payload = attributes["app.payload"]
        assert payload["device_serial"] == "REDACTED"
        assert payload["X-Api-Key"] == "REDACTED"
        assert payload["Cookie"] == "REDACTED"
        assert payload["kept"] == "yes"
        # A list of maps is not a valid attribute value, so it is exported as JSON.
        assert payload["nested"] == '[{"password": "REDACTED"}]'

    def test_objects_are_redacted_by_field_or_reduced_to_their_type(self, exporter: Any) -> None:
        class Credentials(BaseModel):
            user: str
            access_token: str

        @dataclasses.dataclass
        class Login:
            user: str
            password: str

        class Opaque:
            def __repr__(self) -> str:
                return "Opaque(token='leak')"

        # log_structured rejects such values (TypeError), so they arrive through `extra=`.
        logger.info(
            "objects",
            extra={
                "account": Credentials(user="u", access_token="TOK1"),
                "login": Login(user="u", password="PW1"),
                "opaque": Opaque(),
            },
        )

        attributes = _attributes(_exported(exporter)[0])
        assert attributes["account"] == {"user": "u", "access_token": "REDACTED"}
        assert attributes["login"] == {"user": "u", "password": "REDACTED"}
        assert attributes["opaque"] == "<Opaque>"

    def test_stdout_is_unchanged(self, exporter: Any, capsys: pytest.CaptureFixture[str]) -> None:
        log_structured(logger, "info", "printed", user_id="u1")

        assert capsys.readouterr().out.endswith('"message": "printed", "provider": null, "user_id": "u1"}\n')
        assert len(_exported(exporter)) == 1

    def test_respects_log_level(self) -> None:
        memory = sdk_export.InMemoryLogRecordExporter()
        with patch.object(settings, "otel_enabled", True), patch.object(settings, "log_level", LogLevel.WARNING):
            otel.init_otel("open-wearables-test", processor=sdk_export.SimpleLogRecordProcessor(memory))
            try:
                log_structured(logger, "info", "dropped")
                log_structured(logger, "error", "kept")
            finally:
                otel.shutdown_otel()

        assert [item.log_record.body for item in _exported(memory)] == ["kept"]


class TestStdlibExport:
    def test_app_extras_are_redacted_and_the_original_record_is_untouched(self, exporter: Any) -> None:
        seen: list[logging.LogRecord] = []

        class Keep(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                seen.append(record)

        keep = Keep()
        logging.getLogger().addHandler(keep)
        try:
            logger.error("token rotation failed", extra={"token": "secret", "user": "u1"})
        finally:
            logging.getLogger().removeHandler(keep)

        attributes = _attributes(_exported(exporter)[0])
        assert attributes["token"] == "REDACTED"
        assert attributes["user"] == "u1"
        assert seen[0].token == "secret"  # ty: ignore[unresolved-attribute]

    def test_celery_task_payloads_are_not_exported(self, exporter: Any) -> None:
        """Celery attaches task args, kwargs and results to its records (not to the stdout line)."""
        context = {
            "id": "1",
            "name": "send_invitation_email",
            "args": "('a@b.c', 'https://x/invite?token=SECRET')",
            "kwargs": "{'payload': {'heart_rate': [61, 62]}}",
            "return_value": "{'sent': True}",
        }
        logging.getLogger("celery.app.trace").error(
            "Task %(name)s[%(id)s] raised unexpected", context, extra={"data": context}
        )

        [item] = _exported(exporter)
        assert "data" not in _attributes(item)
        assert "SECRET" not in str(_attributes(item))

    def test_each_record_is_exported_once(self, exporter: Any) -> None:
        # Under `fastapi dev` the uvicorn logger has the export handler and propagates to the root.
        uvicorn_logger = logging.getLogger("uvicorn")
        propagate = uvicorn_logger.propagate
        uvicorn_logger.propagate = True
        otel.attach_handler()
        try:
            logging.getLogger("uvicorn.error").warning(
                "Application startup complete.", extra={"color_message": "\x1b[1mcolored\x1b[0m"}
            )
        finally:
            uvicorn_logger.propagate = propagate

        [item] = _exported(exporter)
        assert item.log_record.body == "Application startup complete."
        assert "color_message" not in _attributes(item)

    def test_opentelemetry_own_logs_are_not_exported(self, exporter: Any) -> None:
        logging.getLogger("opentelemetry.exporter.otlp").warning("Transient error")

        assert _exported(exporter) == []

    def test_only_exporter_failures_are_kept_out_of_sentry(self, exporter: Any) -> None:
        from sentry_sdk.integrations.logging import _IGNORED_LOGGERS

        def ignored(name: str) -> bool:
            return any(fnmatch(name, pattern) for pattern in _IGNORED_LOGGERS)

        assert ignored("opentelemetry.exporter.otlp.proto.http._log_exporter")
        assert ignored("opentelemetry.sdk._shared_internal")
        assert not ignored("opentelemetry.instrumentation.fastapi")

    def test_json_and_text_mode_attach_to_the_root_only(self) -> None:
        memory = sdk_export.InMemoryLogRecordExporter()
        with patch.object(settings, "otel_enabled", True), patch.object(settings, "log_format", LogFormat.JSON):
            otel.init_otel("open-wearables-test", processor=sdk_export.SimpleLogRecordProcessor(memory))
            try:
                assert any(otel.is_export_handler(h) for h in logging.getLogger().handlers)
                assert not any(otel.is_export_handler(h) for h in logging.getLogger("celery").handlers)
            finally:
                otel.shutdown_otel()


class TestResource:
    def _resource(self, monkeypatch: pytest.MonkeyPatch, **env: str) -> dict[str, Any]:
        for name in ("OTEL_SERVICE_NAME", "OTEL_RESOURCE_ATTRIBUTES"):
            monkeypatch.delenv(name, raising=False)
        for name, value in env.items():
            monkeypatch.setenv(name, value)
        memory = sdk_export.InMemoryLogRecordExporter()
        with patch.object(settings, "otel_enabled", True):
            otel.init_otel("open-wearables-api", processor=sdk_export.SimpleLogRecordProcessor(memory))
            try:
                logger.warning("resource probe")
            finally:
                otel.shutdown_otel()
        return dict(_exported(memory)[0].resource.attributes)

    def test_code_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        resource = self._resource(monkeypatch)

        assert resource["service.name"] == "open-wearables-api"
        assert resource["service.namespace"] == "open-wearables"
        assert resource["deployment.environment.name"] == settings.environment.value

    def test_environment_overrides_code(self, monkeypatch: pytest.MonkeyPatch) -> None:
        resource = self._resource(
            monkeypatch,
            OTEL_SERVICE_NAME="wearables-eu",
            OTEL_RESOURCE_ATTRIBUTES="deployment.environment.name=staging-eu,team=data",
        )

        assert resource["service.name"] == "wearables-eu"
        assert resource["deployment.environment.name"] == "staging-eu"
        assert resource["team"] == "data"


class TestShutdown:
    def test_stalled_collector_does_not_block_shutdown(self) -> None:
        class StalledExporter(sdk_export.LogRecordExporter):
            def export(self, batch: Any) -> Any:
                time.sleep(30)
                return sdk_export.LogRecordExportResult.SUCCESS

            def shutdown(self) -> None:
                pass

            def force_flush(self, timeout_millis: int = 30000) -> bool:
                return True

        with patch.object(settings, "otel_enabled", True):
            otel.init_otel("open-wearables-test", processor=sdk_export.BatchLogRecordProcessor(StalledExporter()))
            for index in range(5):
                logger.warning("queued %s", index)
            started = time.monotonic()
            otel.shutdown_otel(deadline_seconds=0.5)

        assert time.monotonic() - started < 2


class TestCeleryLogging:
    def test_celery_logging_setup_keeps_the_export_handler(self, exporter: Any) -> None:
        celery_logger = logging.getLogger("celery")
        saved = (celery_logger.handlers[:], celery_logger.level, celery_logger.propagate)
        try:
            celery_core.setup_celery_logging()
            logging.getLogger("celery.worker").info("celery: Warm shutdown")
        finally:
            celery_logger.handlers[:], level, celery_logger.propagate = saved
            celery_logger.setLevel(level)

        assert [item.log_record.body for item in _exported(exporter)] == ["celery: Warm shutdown"]


class TestPrivacyEdgeCases:
    def test_celery_task_results_and_arguments_are_masked_in_the_body(self, exporter: Any) -> None:
        logging.getLogger("celery.app.trace").info(
            "Task %(name)s[%(id)s] succeeded in %(runtime)ss: %(return_value)s",
            {"name": "echo", "id": "1", "runtime": 0.1, "return_value": "{'token': 'RET-SECRET'}"},
        )

        [item] = _exported(exporter)
        assert item.log_record.body == "Task echo[1] succeeded in 0.1s: <omitted>"

    @pytest.mark.parametrize("key", ["privateKey", "Bearer", "session_id", "X-Api-Key", "accessToken"])
    def test_key_spellings_are_normalized(self, exporter: Any, key: str) -> None:
        logger.info("keys", extra={key: "value"})

        assert _attributes(_exported(exporter)[0])[key] == "REDACTED"

    def test_configured_names_match_as_fragments(self, exporter: Any) -> None:
        with patch.object(settings, "otel_export_redact_keys", "email"):
            logger.info("configured", extra={"user_email": "person@example.com", "user": "u1"})

        attributes = _attributes(_exported(exporter)[0])
        assert attributes["user_email"] == "REDACTED"
        assert attributes["user"] == "u1"

    def test_exceptions_in_extras_export_their_type_only(self, exporter: Any) -> None:
        logger.info("error object", extra={"error": ValueError("token=abc")})

        assert _attributes(_exported(exporter)[0])["error"] == "<ValueError>"

    def test_model_serializers_cannot_hide_sensitive_fields(self, exporter: Any) -> None:
        class Wrapped(BaseModel):
            data: dict

            @field_serializer("data")
            def as_json(self, value: dict) -> str:
                return str(value)

        logger.info("model", extra={"wrapped": Wrapped(data={"password": "PW"})})

        assert _attributes(_exported(exporter)[0])["wrapped"] == {"data": {"password": "REDACTED"}}

    def test_one_unconvertible_field_does_not_drop_the_record(self, exporter: Any) -> None:
        @dataclasses.dataclass
        class Holder:
            lock: Any
            safe: str

        try:
            raise RuntimeError("boom")
        except RuntimeError:
            logger.exception("failed %s", "x", extra={"holder": Holder(lock=threading.Lock(), safe="kept")})

        [item] = _exported(exporter)
        attributes = _attributes(item)
        assert item.log_record.body == "failed x"
        assert attributes["holder"]["safe"] == "kept"
        assert attributes["holder"]["lock"].startswith("<")
        assert attributes["exception.type"] == "RuntimeError"
