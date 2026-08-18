"""Tests for the Settings.redis_url property (scheme, TLS, URL-encoding)."""

from unittest.mock import patch

from pydantic import SecretStr

from app.config import settings


class TestRedisUrl:
    """Test suite for Settings.redis_url."""

    def test_plaintext_url_without_auth(self) -> None:
        with (
            patch.object(settings, "redis_host", "localhost"),
            patch.object(settings, "redis_port", 6379),
            patch.object(settings, "redis_db", 0),
            patch.object(settings, "redis_password", None),
            patch.object(settings, "redis_username", None),
            patch.object(settings, "redis_ssl", False),
        ):
            assert settings.redis_url == "redis://localhost:6379/0"

    def test_tls_uses_rediss_scheme_and_cert_reqs(self) -> None:
        with (
            patch.object(settings, "redis_host", "redis.example.com"),
            patch.object(settings, "redis_port", 6379),
            patch.object(settings, "redis_db", 0),
            patch.object(settings, "redis_password", SecretStr("secret")),
            patch.object(settings, "redis_username", None),
            patch.object(settings, "redis_ssl", True),
        ):
            assert settings.redis_url == "rediss://:secret@redis.example.com:6379/0?ssl_cert_reqs=required"

    def test_special_characters_in_credentials_are_url_encoded(self) -> None:
        # Managed AUTH tokens can contain reserved chars; '#' would truncate the
        # URL and '+'/'=' change how it parses, so they must be percent-encoded.
        with (
            patch.object(settings, "redis_host", "redis.example.com"),
            patch.object(settings, "redis_port", 6379),
            patch.object(settings, "redis_db", 1),
            patch.object(settings, "redis_password", SecretStr("p@ss#wo&rd=+/")),
            patch.object(settings, "redis_username", None),
            patch.object(settings, "redis_ssl", True),
        ):
            assert (
                settings.redis_url
                == "rediss://:p%40ss%23wo%26rd%3D%2B%2F@redis.example.com:6379/1?ssl_cert_reqs=required"
            )
