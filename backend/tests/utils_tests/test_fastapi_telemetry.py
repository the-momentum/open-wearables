"""FastAPI's built-in OpenTelemetry support stays off, whatever OTEL_* variables are set and
whatever OpenTelemetry providers other code installs."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2]

# Runs in a fresh process: OpenTelemetry providers are process-global. With
# INSTALL_PROVIDERS=1 it installs providers that record every use before the app is
# imported, the way a log or tracing integration would, which makes FastAPI's per-request
# telemetry check pass; only the `tracing`/`metrics`/`logs` flags then keep it silent.
_PROBE = """
import json
import logging
import os

from opentelemetry import _logs, metrics, trace

uses = []


# Real provider classes, not NoOp ones: FastAPI treats NoOp providers as unconfigured.
class Tracers(trace.TracerProvider):
    def get_tracer(self, name, *args, **kwargs):
        uses.append("tracer")
        return trace.NoOpTracer()


class Meters(metrics.MeterProvider):
    def get_meter(self, name, *args, **kwargs):
        uses.append("meter")
        return metrics.NoOpMeter(name)


class Loggers(_logs.LoggerProvider):
    def get_logger(self, name, *args, **kwargs):
        uses.append("logger")
        return _logs.NoOpLogger(name)


from fastapi import FastAPI
from fastapi.testclient import TestClient

control_uses = 0
if os.environ.get("INSTALL_PROVIDERS") == "1":
    trace.set_tracer_provider(Tracers())
    metrics.set_meter_provider(Meters())
    _logs.set_logger_provider(Loggers())

    # Positive control: a FastAPI app with default telemetry must use these providers,
    # otherwise an empty `uses` below would prove nothing.
    control = FastAPI()

    @control.get("/")
    def control_root():
        return {}

    with TestClient(control) as control_client:
        control_client.get("/")
    control_uses = len(uses)
    uses.clear()

import app.main

api = app.main.api


@api.get("/_probe/error")
def probe_error():
    raise RuntimeError("probe")


@api.get("/_probe/validate")
def probe_validate(number: int):
    return number


fastapi_messages = []


class Collect(logging.Handler):
    def emit(self, record):
        fastapi_messages.append(record.getMessage())


logging.getLogger("fastapi").addHandler(Collect())
with TestClient(api, raise_server_exceptions=False) as client:
    statuses = [
        client.get("/openapi.json").status_code,
        client.get("/_probe/validate", params={"number": "x"}).status_code,
        client.get("/_probe/error").status_code,
    ]

providers = [trace.get_tracer_provider(), metrics.get_meter_provider(), _logs.get_logger_provider()]
print("PROBE_REPORT " + json.dumps({
    "control_uses": control_uses,
    "uses": uses,
    "statuses": statuses,
    "sdk_providers": [type(p).__module__ for p in providers if type(p).__module__.startswith("opentelemetry.sdk")],
    "fastapi_messages": fastapi_messages,
}))
"""


@pytest.mark.parametrize("install_providers", ["0", "1"])
def test_fastapi_telemetry_stays_off(install_providers: str) -> None:
    env = {key: value for key, value in os.environ.items() if not key.startswith("OTEL_")} | {
        "OTEL_EXPORTER_OTLP_ENDPOINT": "http://127.0.0.1:4318",
        "INSTALL_PROVIDERS": install_providers,
        # The child does not get conftest's mocks; keep it away from external services.
        "OUTGOING_WEBHOOKS_ENABLED": "false",
        "SENTRY_ENABLED": "false",
        "TELEMETRY_ENABLED": "false",
    }
    result = subprocess.run(
        [sys.executable, "-c", _PROBE], cwd=BACKEND_DIR, env=env, capture_output=True, text=True, timeout=120
    )

    assert result.returncode == 0, result.stderr
    [report_line] = [line for line in result.stdout.splitlines() if line.startswith("PROBE_REPORT ")]
    report = json.loads(report_line.removeprefix("PROBE_REPORT "))
    if install_providers == "1":
        assert report["control_uses"] > 0
    assert report["statuses"] == [200, 400, 500]
    assert report["uses"] == []
    # The SDK is not a dependency here; this guards against one pulling it in and FastAPI
    # configuring exporters on its own.
    assert report["sdk_providers"] == []
    assert report["fastapi_messages"] == []
