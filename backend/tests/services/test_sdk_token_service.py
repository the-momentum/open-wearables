"""Tests for SDK token service."""

from datetime import datetime, timedelta, timezone

from jose import jwt

from app.config import settings
from app.services.sdk_token_service import create_sdk_user_token


class TestSDKTokenServiceCreate:
    """Tests for creating SDK user tokens."""

    def test_create_sdk_user_token_contains_scope(self) -> None:
        """Token should contain scope=sdk claim."""
        token = create_sdk_user_token("app_123", "user_456")
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])

        assert payload["scope"] == "sdk"

    def test_create_sdk_user_token_contains_subject(self) -> None:
        """Token subject should be external_user_id."""
        token = create_sdk_user_token("app_123", "my_user")
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])

        assert payload["sub"] == "my_user"

    def test_create_sdk_user_token_contains_app_id(self) -> None:
        """Token should contain app_id claim."""
        token = create_sdk_user_token("app_xyz", "user_456")
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])

        assert payload["app_id"] == "app_xyz"

    def test_create_sdk_user_token_has_expiration(self) -> None:
        """Token should have expiration claim."""
        token = create_sdk_user_token("app_123", "user_456")
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])

        assert "exp" in payload

    def test_create_sdk_user_token_expires_in_configured_time(self) -> None:
        """Token should expire based on settings.access_token_expire_minutes."""
        before = datetime.now(timezone.utc)
        token = create_sdk_user_token("app_123", "user_456")
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        after = datetime.now(timezone.utc)

        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        expected_min = before + timedelta(minutes=settings.access_token_expire_minutes - 1)
        expected_max = after + timedelta(minutes=settings.access_token_expire_minutes + 1)

        assert expected_min < exp < expected_max

    def test_create_sdk_user_token_is_valid_jwt(self) -> None:
        """Token should be a valid JWT that can be decoded."""
        token = create_sdk_user_token("app_123", "user_456")

        # Should not raise an exception
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])

        assert payload is not None

    def test_create_sdk_user_token_different_users(self) -> None:
        """Different users should get different token subjects."""
        token1 = create_sdk_user_token("app_123", "user_1")
        token2 = create_sdk_user_token("app_123", "user_2")

        payload1 = jwt.decode(token1, settings.secret_key, algorithms=[settings.algorithm])
        payload2 = jwt.decode(token2, settings.secret_key, algorithms=[settings.algorithm])

        assert payload1["sub"] == "user_1"
        assert payload2["sub"] == "user_2"

    def test_create_sdk_user_token_different_apps(self) -> None:
        """Different apps should get different app_id claims."""
        token1 = create_sdk_user_token("app_1", "user_123")
        token2 = create_sdk_user_token("app_2", "user_123")

        payload1 = jwt.decode(token1, settings.secret_key, algorithms=[settings.algorithm])
        payload2 = jwt.decode(token2, settings.secret_key, algorithms=[settings.algorithm])

        assert payload1["app_id"] == "app_1"
        assert payload2["app_id"] == "app_2"
