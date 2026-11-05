"""Provider tokens are read both encrypted and plaintext, and still written plaintext (step 1 of the rollout)."""

from datetime import datetime, timedelta, timezone
from typing import NamedTuple
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import settings
from app.models import UserConnection
from app.repositories import UserConnectionRepository
from app.schemas.auth import ConnectionStatus
from app.services.providers.api_client import get_valid_token
from app.utils.exceptions import TokenDecryptionError
from app.utils.token_encryption import ENCRYPTED_PREFIX, decrypt_token, encrypt_token
from tests.factories import ApiKeyFactory, UserConnectionFactory
from tests.utils import api_key_headers

OTHER_SECRET_KEY = "b" * 64
# Encrypted once, with "k" * 64 as SECRET_KEY: pins the key derivation and the stored format, which rows
# encrypted by an earlier release (and the migration's own copy of this code) depend on
PINNED_SECRET_KEY = "k" * 64
PINNED_ENCRYPTED = (
    "enc:v1:gAAAAABq7OWc0wodjZXooIzqXJDJ1NnUHDmPL7u336xfyRobMLZc643zGPIHUPWpdsd3TeSHFyezVwE-a7DH1H8BmNh9a2-gvQ=="
)


def raw_tokens(db: Session, connection_id: UUID) -> tuple[str | None, str | None]:
    """The token columns as stored, bypassing the model's decryption."""
    row = db.execute(
        text("SELECT access_token, refresh_token FROM user_connection WHERE id = :id"), {"id": connection_id}
    ).one()
    return row.access_token, row.refresh_token


def store_raw_tokens(db: Session, connection_id: UUID, access_token: str, refresh_token: str) -> None:
    """Write the token columns as given, as a release that encrypts on write would leave them."""
    db.execute(
        text("UPDATE user_connection SET access_token = :access, refresh_token = :refresh WHERE id = :id"),
        {"access": access_token, "refresh": refresh_token, "id": connection_id},
    )
    db.expire_all()


def load(db: Session, connection_id: UUID) -> UserConnection:
    return db.execute(
        select(UserConnection).where(UserConnection.id == connection_id).execution_options(populate_existing=True)
    ).scalar_one()


class ConnectionIds(NamedTuple):
    # Plain ids: touching the expired model would reload the row, and its tokens no longer decrypt
    id: UUID
    user_id: UUID


@pytest.fixture
def encrypted_with_other_key(db: Session) -> ConnectionIds:
    """A connection whose tokens were encrypted under a SECRET_KEY other than the configured one."""
    connection = UserConnectionFactory(token_expires_at=datetime.now(timezone.utc) - timedelta(hours=1))
    ids = ConnectionIds(connection.id, connection.user_id)
    with patch.object(settings, "secret_key", OTHER_SECRET_KEY):
        access, refresh = encrypt_token("access-secret"), encrypt_token("refresh-secret")
    store_raw_tokens(db, ids.id, access, refresh)
    return ids


class TestTokenEncryption:
    def test_encrypted_token_round_trips(self) -> None:
        encrypted = encrypt_token("access-secret")

        assert encrypted.startswith(ENCRYPTED_PREFIX)
        assert "access-secret" not in encrypted
        assert decrypt_token(encrypted) == "access-secret"

    def test_plaintext_token_is_returned_as_it_is(self) -> None:
        assert decrypt_token("access-secret") == "access-secret"

    def test_value_encrypted_by_an_earlier_release_still_decrypts(self) -> None:
        with patch.object(settings, "secret_key", PINNED_SECRET_KEY):
            assert decrypt_token(PINNED_ENCRYPTED) == "access-secret"

    def test_key_is_derived_from_secret_key(self) -> None:
        encrypted = encrypt_token("access-secret")

        with patch.object(settings, "secret_key", OTHER_SECRET_KEY), pytest.raises(TokenDecryptionError):
            decrypt_token(encrypted)

    @pytest.mark.parametrize(
        "value",
        [ENCRYPTED_PREFIX, f"{ENCRYPTED_PREFIX}not-a-fernet-token", f"{ENCRYPTED_PREFIX}żółw"],
        ids=["empty", "not_fernet", "non_ascii"],
    )
    def test_malformed_encrypted_value_is_never_taken_for_a_token(self, value: str) -> None:
        with pytest.raises(TokenDecryptionError):
            decrypt_token(value)

    def test_error_names_the_cause_without_the_token(self) -> None:
        with patch.object(settings, "secret_key", OTHER_SECRET_KEY):
            encrypted = encrypt_token("access-secret")

        with pytest.raises(TokenDecryptionError) as exc_info:
            decrypt_token(encrypted)

        assert "SECRET_KEY" in exc_info.value.detail
        assert exc_info.value.status_code == 503
        assert "access-secret" not in str(exc_info.value)
        assert exc_info.value.__cause__ is None


class TestUserConnectionTokens:
    def test_plaintext_row_is_read_as_it_is(self, db: Session) -> None:
        connection = UserConnectionFactory()
        store_raw_tokens(db, connection.id, "access-secret", "refresh-secret")

        loaded = load(db, connection.id)

        assert (loaded.access_token, loaded.refresh_token) == ("access-secret", "refresh-secret")

    def test_encrypted_row_is_decrypted(self, db: Session) -> None:
        connection = UserConnectionFactory()
        store_raw_tokens(db, connection.id, encrypt_token("access-secret"), encrypt_token("refresh-secret"))

        loaded = load(db, connection.id)

        assert (loaded.access_token, loaded.refresh_token) == ("access-secret", "refresh-secret")

    def test_tokens_are_still_written_plaintext(self, db: Session) -> None:
        connection = UserConnectionFactory(access_token="access-secret", refresh_token="refresh-secret")
        db.flush()

        assert raw_tokens(db, connection.id) == ("access-secret", "refresh-secret")

        UserConnectionRepository().update_tokens(db, connection, "new-access", "new-refresh", 3600)

        assert raw_tokens(db, connection.id) == ("new-access", "new-refresh")

    def test_row_encrypted_with_another_key_fails_to_load(
        self, db: Session, encrypted_with_other_key: ConnectionIds
    ) -> None:
        with pytest.raises(TokenDecryptionError):
            load(db, encrypted_with_other_key.id)


class TestWrongSecretKeyKeepsTheConnection:
    """A token that doesn't decrypt is a deployment error: the connection is neither used, revoked nor cleared."""

    def test_token_is_not_refreshed_and_connection_not_revoked(
        self, db: Session, encrypted_with_other_key: ConnectionIds
    ) -> None:
        stored = raw_tokens(db, encrypted_with_other_key.id)
        oauth = MagicMock()

        with patch("httpx.post") as http_post, pytest.raises(TokenDecryptionError):
            get_valid_token(db, encrypted_with_other_key.user_id, "garmin", UserConnectionRepository(), oauth)

        http_post.assert_not_called()
        oauth.refresh_access_token.assert_not_called()
        oauth.revoke_connection.assert_not_called()
        status = db.execute(
            text("SELECT status FROM user_connection WHERE id = :id"), {"id": encrypted_with_other_key.id}
        ).scalar_one()
        assert status == ConnectionStatus.ACTIVE
        assert raw_tokens(db, encrypted_with_other_key.id) == stored

    def test_api_answers_503_configuration_error(
        self, client: TestClient, db: Session, encrypted_with_other_key: ConnectionIds
    ) -> None:
        headers = api_key_headers(ApiKeyFactory().plain_key)

        response = client.get(f"/api/v1/users/{encrypted_with_other_key.user_id}/connections", headers=headers)

        assert response.status_code == 503
        assert response.json()["code"] == "CONFIGURATION_ERROR"
        assert "SECRET_KEY" in response.json()["detail"]
