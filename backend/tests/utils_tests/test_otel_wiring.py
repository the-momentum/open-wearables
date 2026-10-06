"""OpenTelemetry log export wiring that must work without the `otel` extra installed.

The export itself is tested in test_otel_export.py, which is skipped without the extra.
"""

import logging
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.config import settings
from app.integrations import otel
from app.integrations.celery import core as celery_core
from app.utils.structured_logging import log_structured

BACKEND_DIR = Path(__file__).resolve().parents[2]

logger = logging.getLogger("app.test_otel")


class TestDisabled:
    def test_nothing_is_set_up(self) -> None:
        with patch.object(settings, "otel_enabled", False):
            otel.init_otel("open-wearables-test")

        assert not any(otel.is_export_handler(handler) for handler in logging.getLogger().handlers)
        log_structured(logger, "info", "not exported")

    def test_sdk_disabled_variable_wins(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OTEL_SDK_DISABLED", "true")
        with patch.object(settings, "otel_enabled", True):
            assert otel.export_enabled() is False

    def test_disabled_export_starts_no_threads_and_sets_no_provider(self) -> None:
        code = (
            "import threading\n"
            "from opentelemetry import _logs\n"
            "import app.main\n"
            "from app.integrations.otel import init_otel\n"
            "init_otel('open-wearables-api')\n"
            "print(type(_logs.get_logger_provider()).__module__.startswith('opentelemetry.sdk'))\n"
            "print(sorted(t.name for t in threading.enumerate() if 'otel' in t.name.lower()))\n"
        )
        env = os.environ | {"OTEL_ENABLED": "false", "TELEMETRY_ENABLED": "false"}
        result = subprocess.run(
            [sys.executable, "-c", code], cwd=BACKEND_DIR, env=env, capture_output=True, text=True, timeout=120
        )

        assert result.returncode == 0, result.stderr
        assert result.stdout.splitlines()[-2:] == ["False", "[]"]


class TestDependencies:
    def test_missing_extra_fails_at_startup(self) -> None:
        with (
            patch.object(settings, "otel_enabled", True),
            patch("app.integrations.otel.importlib.util.find_spec", return_value=None),
            pytest.raises(RuntimeError, match="'otel' extra"),
        ):
            otel.check_dependencies()

    def test_missing_extra_is_fine_while_disabled(self) -> None:
        with (
            patch.object(settings, "otel_enabled", False),
            patch("app.integrations.otel.importlib.util.find_spec", return_value=None),
        ):
            otel.check_dependencies()


class TestCeleryWiring:
    @pytest.mark.parametrize(
        ("hostname", "expected"),
        [
            ("io@worker-1", "open-wearables-worker-io"),
            ("cpu@worker-1", "open-wearables-worker-cpu"),
            ("celery@worker-1", "open-wearables-worker"),
            (None, "open-wearables-worker"),
        ],
    )
    def test_service_name_follows_the_node_name(self, hostname: str | None, expected: str) -> None:
        assert celery_core._worker_service_name_for(hostname) == expected

    @pytest.mark.parametrize(
        ("pool_cls", "starts_in_parent"),
        [
            ("prefork", False),
            ("processes", False),
            ("celery.concurrency.prefork:TaskPool", False),
            ("threads", True),
            ("solo", True),
        ],
    )
    def test_prefork_parent_leaves_export_to_its_children(self, pool_cls: str, starts_in_parent: bool) -> None:
        with patch.object(celery_core, "init_otel") as init_otel:
            celery_core.init_worker_log_export(SimpleNamespace(hostname="io@host", pool_cls=pool_cls))

        assert init_otel.called is starts_in_parent

    def test_prefork_pool_class_is_detected(self) -> None:
        from celery.concurrency.prefork import TaskPool as PreforkPool
        from celery.concurrency.thread import TaskPool as ThreadPool

        class CustomPreforkPool(PreforkPool):
            pass

        assert celery_core._uses_prefork(PreforkPool) is True
        assert celery_core._uses_prefork(CustomPreforkPool) is True
        assert celery_core._uses_prefork(ThreadPool) is False
        assert celery_core._uses_prefork("no-such-pool") is False

    def test_child_process_starts_export_under_the_worker_name(self) -> None:
        with patch.object(celery_core, "init_otel") as init_otel:
            celery_core.init_worker_log_export(SimpleNamespace(hostname="cpu@host", pool_cls="prefork"))
            celery_core.init_worker_process_log_export()

        init_otel.assert_called_once_with("open-wearables-worker-cpu")
