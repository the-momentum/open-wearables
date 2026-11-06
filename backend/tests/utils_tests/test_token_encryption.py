"""Provider tokens are read both encrypted and plaintext, and written encrypted once the wait after the upgrade ends."""

from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from typing import NamedTuple
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, select, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.config import settings
from app.models import User, UserConnection
from app.repositories import UserConnectionRepository
from app.schemas.auth import ConnectionStatus
from app.services.providers.api_client import get_valid_token
from app.services.user_connection_service import user_connection_service
from app.services.user_service import user_service
from app.utils import token_encryption
from app.utils.exceptions import SecretKeyMismatchError, TokenDecryptionError
from app.utils.token_encryption import (
    ENCRYPTED_PREFIX,
    ENCRYPTION_DELAY,
    decrypt_token,
    encrypt_token,
    key_fingerprint,
    read_encryption_start,
)
from tests.factories import ApiKeyFactory, UserConnectionFactory
from tests.utils import api_key_headers
from tests.utils.provider_tokens import (
    AFTER_ENCRYPTION,
    BEFORE_ENCRYPTION,
    OTHER_SECRET_KEY,
    PINNED_ENCRYPTED,
    PINNED_SECRET_KEY,
    raw_tokens,
    store_raw_tokens,
    upgraded_ago,
)

# Captured at import, before the autouse fixture in conftest swaps it for a lookup on the test transaction
load_encryption_start_for_real = token_encryption._load_encryption_start


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

    @pytest.mark.parametrize("upgraded", [None, BEFORE_ENCRYPTION], ids=["no_marker", "before_the_wait_ends"])
    def test_tokens_are_written_plaintext_until_encryption_starts(
        self, db: Session, upgraded: timedelta | None
    ) -> None:
        if upgraded is not None:
            upgraded_ago(db, upgraded)
        connection = UserConnectionFactory(access_token="access-secret", refresh_token="refresh-secret")
        db.flush()

        assert raw_tokens(db, connection.id) == ("access-secret", "refresh-secret")

        UserConnectionRepository().update_tokens(db, connection, "new-access", "new-refresh", 3600)

        assert raw_tokens(db, connection.id) == ("new-access", "new-refresh")

    def test_tokens_are_written_encrypted_once_encryption_started(self, db: Session) -> None:
        upgraded_ago(db, AFTER_ENCRYPTION)
        connection = UserConnectionFactory(access_token="access-secret", refresh_token="refresh-secret")
        db.flush()

        stored = raw_tokens(db, connection.id)
        assert all(value is not None and value.startswith(ENCRYPTED_PREFIX) for value in stored)
        assert "access-secret" not in str(stored)
        assert "refresh-secret" not in str(stored)

        UserConnectionRepository().update_tokens(db, connection, "new-access", "new-refresh", 3600)

        stored = raw_tokens(db, connection.id)
        assert "new-access" not in str(stored)
        assert "new-refresh" not in str(stored)
        assert (decrypt_token(stored[0] or ""), decrypt_token(stored[1] or "")) == ("new-access", "new-refresh")
        loaded = load(db, connection.id)
        assert (loaded.access_token, loaded.refresh_token) == ("new-access", "new-refresh")

    def test_null_token_stays_null(self, db: Session) -> None:
        upgraded_ago(db, AFTER_ENCRYPTION)
        connection = UserConnectionFactory(access_token="access-secret", refresh_token=None)
        db.flush()

        assert raw_tokens(db, connection.id)[1] is None

    def test_token_encrypted_with_another_key_fails_when_read(
        self, db: Session, encrypted_with_other_key: ConnectionIds
    ) -> None:
        # The row loads (the token columns are deferred); reading a token raises
        loaded = load(db, encrypted_with_other_key.id)

        assert loaded.status == ConnectionStatus.ACTIVE
        with pytest.raises(TokenDecryptionError):
            _ = loaded.access_token


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

    def test_connections_still_list(
        self, client: TestClient, db: Session, encrypted_with_other_key: ConnectionIds
    ) -> None:
        # The token columns are deferred: a query that doesn't need the tokens doesn't decrypt them
        headers = api_key_headers(ApiKeyFactory().plain_key)

        response = client.get(f"/api/v1/users/{encrypted_with_other_key.user_id}/connections", headers=headers)

        assert response.status_code == 200
        assert [c["id"] for c in response.json()] == [str(encrypted_with_other_key.id)]

    def test_reconnecting_replaces_the_tokens(self, db: Session, encrypted_with_other_key: ConnectionIds) -> None:
        repo = UserConnectionRepository()
        connection = repo.get_by_user_and_provider(db, encrypted_with_other_key.user_id, "garmin")
        assert connection is not None

        repo.update_connection_info(db, connection, "new-access", "new-refresh", 3600)

        assert raw_tokens(db, encrypted_with_other_key.id) == ("new-access", "new-refresh")

    def test_disconnecting_clears_the_tokens(self, db: Session, encrypted_with_other_key: ConnectionIds) -> None:
        oauth = MagicMock()

        user_connection_service.disconnect(db, encrypted_with_other_key.user_id, "garmin", oauth=oauth)

        oauth.deregister_user.assert_not_called()
        assert raw_tokens(db, encrypted_with_other_key.id) == (None, None)

    def test_deleting_the_user_still_works(self, db: Session, encrypted_with_other_key: ConnectionIds) -> None:
        user_service.delete(db, encrypted_with_other_key.user_id)

        assert db.get(User, encrypted_with_other_key.user_id) is None


class TestWriteSchedule:
    """When this process starts writing tokens encrypted: read from the marker, at most once a minute."""

    def test_encryption_starts_seven_days_after_the_upgrade(self, db: Session) -> None:
        upgraded_ago(db, timedelta(days=1))
        upgraded_at = db.execute(text("SELECT created_at FROM provider_token_encryption")).scalar_one()

        assert timedelta(days=7) == ENCRYPTION_DELAY
        assert read_encryption_start(db.connection()) == upgraded_at + ENCRYPTION_DELAY

    def test_without_the_table_there_is_no_start(self, db: Session) -> None:
        # A database the migration never reached, or one it was downgraded from
        db.execute(text("DROP TABLE provider_token_encryption"))

        assert read_encryption_start(db.connection()) is None
        assert token_encryption.write_schedule.encrypt_writes() is False

    def test_writes_switch_to_encrypted_when_the_wait_ends_without_another_lookup(self, db: Session) -> None:
        upgraded_ago(db, ENCRYPTION_DELAY - timedelta(minutes=30))
        schedule = token_encryption.write_schedule
        lookup = MagicMock(wraps=token_encryption._load_encryption_start)

        with patch.object(token_encryption, "_load_encryption_start", lookup):
            assert schedule.encrypt_writes() is False
            with patch.object(token_encryption, "_now", return_value=datetime.now(timezone.utc) + timedelta(hours=1)):
                assert schedule.encrypt_writes() is True

        lookup.assert_called_once()

    def test_marker_dropped_by_a_downgrade_stops_encryption_at_the_next_lookup(self, db: Session) -> None:
        upgraded_ago(db, AFTER_ENCRYPTION)
        schedule = token_encryption.write_schedule
        assert schedule.encrypt_writes() is True

        db.execute(text("DELETE FROM provider_token_encryption"))

        # Still going by the marker it read, until a minute has passed
        assert schedule.encrypt_writes() is True
        with patch.object(token_encryption, "MARKER_CHECK_INTERVAL_SECONDS", 0):
            assert schedule.encrypt_writes() is False

    def test_unreadable_marker_writes_plaintext(self, db: Session) -> None:
        upgraded_ago(db, AFTER_ENCRYPTION)
        error = OSError("connection refused")

        with (
            patch.object(token_encryption, "_load_encryption_start", side_effect=error),
            patch.object(token_encryption, "logger") as logger,
        ):
            connection = UserConnectionFactory(access_token="access-secret", refresh_token="refresh-secret")
            db.flush()

            with patch.object(token_encryption, "MARKER_CHECK_INTERVAL_SECONDS", 0):
                assert token_encryption.write_schedule.encrypt_writes() is False

        assert raw_tokens(db, connection.id) == ("access-secret", "refresh-secret")
        # Once per failure streak, not on every lookup
        logger.error.assert_called_once()
        assert logger.error.call_args.kwargs["exc_info"] is error
        assert logger.error.call_args.kwargs["alert"] is True

    def test_marker_of_another_secret_key_is_refused(self, db: Session) -> None:
        upgraded_ago(db, AFTER_ENCRYPTION, secret_key=OTHER_SECRET_KEY)

        with pytest.raises(SecretKeyMismatchError) as exc_info:
            read_encryption_start(db.connection())

        assert "SECRET_KEY" in exc_info.value.detail
        assert exc_info.value.status_code == 503

    def test_process_with_another_secret_key_writes_plaintext_and_alerts_once(self, db: Session) -> None:
        # The API applied the migration with OTHER_SECRET_KEY; this process (a worker, say) has the configured one
        upgraded_ago(db, AFTER_ENCRYPTION, secret_key=OTHER_SECRET_KEY)
        schedule = token_encryption.write_schedule

        with patch.object(token_encryption, "logger") as logger:
            connection = UserConnectionFactory(access_token="access-secret", refresh_token="refresh-secret")
            db.flush()
            with patch.object(token_encryption, "MARKER_CHECK_INTERVAL_SECONDS", 0):
                assert schedule.encrypt_writes() is False

        assert raw_tokens(db, connection.id) == ("access-secret", "refresh-secret")
        logger.error.assert_called_once()
        assert logger.error.call_args.kwargs["alert"] is True
        assert OTHER_SECRET_KEY not in str(logger.mock_calls)
        assert settings.secret_key not in str(logger.mock_calls)

    def test_lookup_running_in_another_thread_leaves_this_write_plaintext(self, db: Session) -> None:
        upgraded_ago(db, AFTER_ENCRYPTION)
        schedule = token_encryption.write_schedule

        with schedule._lock:
            assert schedule.encrypt_writes() is False

        assert schedule.encrypt_writes() is True


class TestMarkerLookupConnection:
    """The production lookup, on a connection of its own with its timeouts, against the test database.

    It doesn't see the test transaction, so the marker it reads is committed here and deleted afterwards.
    """

    @pytest.fixture
    def marker_engine(self, _postgres_url: str) -> Iterator[Engine]:
        engine = create_engine(_postgres_url, poolclass=NullPool)
        try:
            with patch.object(token_encryption, "_marker_engine", return_value=engine):
                yield engine
        finally:
            with engine.begin() as connection:
                connection.execute(text("DELETE FROM provider_token_encryption"))
            engine.dispose()

    def test_without_the_marker_there_is_no_start(self, marker_engine: Engine) -> None:
        assert load_encryption_start_for_real() is None

    def test_reads_the_committed_marker(self, marker_engine: Engine) -> None:
        upgraded_at = datetime.now(timezone.utc) - timedelta(days=1)
        with marker_engine.begin() as connection:
            connection.execute(
                text("INSERT INTO provider_token_encryption (id, created_at, key_check) VALUES (1, :at, :key_check)"),
                {"at": upgraded_at, "key_check": key_fingerprint(settings.secret_key)},
            )

        assert load_encryption_start_for_real() == upgraded_at + ENCRYPTION_DELAY
