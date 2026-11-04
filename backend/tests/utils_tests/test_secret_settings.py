"""Tests for secrets whose old defaults are public: refused or derived at startup."""

import pytest
from pydantic import ValidationError

from app.config import (
    MIN_SECRET_KEY_LENGTH,
    PUBLISHED_SECRET_VALUES,
    PUBLISHED_STRAVA_WEBHOOK_VERIFY_TOKENS,
    Settings,
)
from app.utils.config_utils import derive_secret

STRONG_SECRET_KEY = "a" * MIN_SECRET_KEY_LENGTH


class TestSecretKeyValidation:
    """Anyone who knows SECRET_KEY can forge tokens, so a guessable one must stop startup."""

    @pytest.mark.parametrize("value", sorted(PUBLISHED_SECRET_VALUES["secret_key"]))
    def test_published_default_is_rejected(self, value: str) -> None:
        with pytest.raises(ValidationError, match="SECRET_KEY is set to a value published"):
            Settings(secret_key=value)

    def test_short_key_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match=f"at least {MIN_SECRET_KEY_LENGTH} characters"):
            Settings(secret_key="a" * (MIN_SECRET_KEY_LENGTH - 1))

    def test_empty_key_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match="SECRET_KEY is not set. Run `make init`"):
            Settings(secret_key="")

    def test_missing_key_points_to_make_init(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A deployment without SECRET_KEY must learn how to fix it, not just "Field required"."""
        monkeypatch.delenv("SECRET_KEY", raising=False)

        with pytest.raises(ValidationError, match="SECRET_KEY is not set. Run `make init`"):
            Settings()

    def test_key_of_minimum_length_is_accepted(self) -> None:
        settings = Settings(secret_key=STRONG_SECRET_KEY)

        assert settings.secret_key == STRONG_SECRET_KEY

    def test_rejected_key_is_not_echoed_in_the_error(self) -> None:
        """The startup traceback lands in container logs, so it must not carry the key."""
        real_but_short_key = "MyRealButShortSecret-123"

        with pytest.raises(ValidationError) as exc_info:
            Settings(secret_key=real_but_short_key)

        assert real_but_short_key not in str(exc_info.value)


class TestStravaWebhookVerifyToken:
    """Strava receives this token, so a derived one must not reveal SECRET_KEY."""

    def _token(self, value: str | None) -> str:
        token = Settings(secret_key=STRONG_SECRET_KEY, strava_webhook_verify_token=value).strava_webhook_verify_token
        assert token is not None
        return token.get_secret_value()

    @pytest.mark.parametrize("value", [None, ""])
    def test_unset_token_is_derived_from_secret_key(self, value: str | None) -> None:
        token = self._token(value)

        assert token == derive_secret(STRONG_SECRET_KEY, "strava-webhook-verify-token")
        assert token != STRONG_SECRET_KEY

    @pytest.mark.parametrize("value", sorted(PUBLISHED_STRAVA_WEBHOOK_VERIFY_TOKENS))
    def test_published_default_counts_as_unset(self, value: str) -> None:
        with pytest.warns(UserWarning, match="Ignoring STRAVA_WEBHOOK_VERIFY_TOKEN"):
            token = self._token(value)

        assert token == derive_secret(STRONG_SECRET_KEY, "strava-webhook-verify-token")

    def test_own_token_is_kept(self) -> None:
        assert self._token("b" * 64) == "b" * 64
