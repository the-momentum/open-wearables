import pytest
from pydantic import SecretStr

from app.config import settings


def test_db_uri_prefers_database_url_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "database_url", SecretStr("postgresql+psycopg://override"))
    monkeypatch.setattr(settings, "db_socket_path", None)

    assert settings.db_uri == "postgresql+psycopg://override"


def test_db_uri_supports_cloud_sql_socket_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "database_url", None)
    monkeypatch.setattr(settings, "db_socket_path", "/cloudsql/project:region:instance")
    monkeypatch.setattr(settings, "db_user", "socket-user")
    monkeypatch.setattr(settings, "db_password", SecretStr("socket-password"))
    monkeypatch.setattr(settings, "db_name", "socket-db")

    assert settings.db_uri == (
        "postgresql+psycopg://socket-user:socket-password@/socket-db?host=%2Fcloudsql%2Fproject%3Aregion%3Ainstance"
    )


def test_redis_url_prefers_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "redis_url_override", SecretStr("redis://override"))

    assert settings.redis_url == "redis://override"
