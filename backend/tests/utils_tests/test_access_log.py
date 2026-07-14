"""Tests for access-log mode derivation and the access-log middleware."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.config import Settings, settings
from app.middlewares import add_access_log_middleware
from app.utils.config_utils import AccessLogMode, EnvironmentType


class TestAccessLogModeDerivation:
    @pytest.mark.parametrize(
        ("environment", "expected"),
        [
            (EnvironmentType.PRODUCTION, AccessLogMode.ERRORS),
            (EnvironmentType.STAGING, AccessLogMode.ALL),
            (EnvironmentType.LOCAL, AccessLogMode.ALL),
            (EnvironmentType.TEST, AccessLogMode.ALL),
        ],
    )
    def test_default_is_derived_from_environment(self, environment: EnvironmentType, expected: AccessLogMode) -> None:
        assert Settings(environment=environment, access_log_mode=None).access_log_mode == expected

    def test_explicit_value_overrides_derivation(self) -> None:
        settings = Settings(environment=EnvironmentType.PRODUCTION, access_log_mode=AccessLogMode.ALL)
        assert settings.access_log_mode == AccessLogMode.ALL


def _build_client(mode: AccessLogMode) -> TestClient:
    app = FastAPI()

    @app.get("/ok")
    async def ok() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/client-error")
    async def client_error() -> None:
        raise HTTPException(status_code=404)

    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("kaboom")

    with patch.object(settings, "access_log_mode", mode):
        add_access_log_middleware(app)

    return TestClient(app, raise_server_exceptions=False)


def _logged_statuses(mock: MagicMock) -> list[int]:
    return [call.kwargs["status"] for call in mock.call_args_list]


class TestAccessLogMiddleware:
    def test_all_mode_logs_every_status(self) -> None:
        client = _build_client(AccessLogMode.ALL)
        with patch("app.middlewares.log_structured") as mock:
            client.get("/ok")
            client.get("/client-error")
            client.get("/boom")
        assert _logged_statuses(mock) == [200, 404, 500]

    def test_errors_mode_drops_2xx_keeps_4xx_5xx(self) -> None:
        client = _build_client(AccessLogMode.ERRORS)
        with patch("app.middlewares.log_structured") as mock:
            client.get("/ok")
            client.get("/client-error")
            client.get("/boom")
        assert _logged_statuses(mock) == [404, 500]

    def test_off_mode_logs_nothing(self) -> None:
        client = _build_client(AccessLogMode.OFF)
        with patch("app.middlewares.log_structured") as mock:
            client.get("/ok")
            client.get("/client-error")
        mock.assert_not_called()

    def test_level_is_error_for_4xx_and_5xx(self) -> None:
        client = _build_client(AccessLogMode.ALL)
        with patch("app.middlewares.log_structured") as mock:
            client.get("/ok")
            client.get("/client-error")
        levels = [call.args[1] for call in mock.call_args_list]
        assert levels == ["info", "error"]
