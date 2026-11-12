"""The beat task brings stored provider secrets in line with the encryption schedule."""

from collections.abc import Callable
from datetime import timedelta
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.integrations import redis_lock
from app.integrations.celery.tasks import provider_token_encryption_task as task
from app.services.provider_token_encryption_service import (
    ProviderTokenEncryptionService,
    TokenSweep,
    provider_token_encryption_service,
)
from app.utils.token_encryption import ENCRYPTED_PREFIX, decrypt_token, encrypt_token
from tests.factories import UserConnectionFactory
from tests.utils.provider_tokens import (
    AFTER_ENCRYPTION,
    BEFORE_ENCRYPTION,
    LATER_FORMAT,
    OTHER_SECRET_KEY,
    raw_tokens,
    raw_webhook_secret,
    store_raw_tokens,
    store_raw_webhook_secret,
    upgraded_ago,
)


def plaintext_connection(
    db: Session, access: str | None = "access-secret", refresh: str | None = "refresh-secret"
) -> UUID:
    connection = UserConnectionFactory()
    store_raw_tokens(db, connection.id, access, refresh)
    return connection.id


def encrypted_connection(db: Session) -> UUID:
    connection = UserConnectionFactory()
    store_raw_tokens(db, connection.id, encrypt_token("access-secret"), encrypt_token("refresh-secret"))
    return connection.id


def decrypted(stored: tuple[str | None, str | None]) -> tuple[str | None, str | None]:
    return tuple(None if value is None else decrypt_token(value) for value in stored)  # type: ignore[return-value]


def is_encrypted(value: str | None) -> bool:
    return value is not None and value.startswith(ENCRYPTED_PREFIX)


class TestEncryptSweep:
    def test_encrypts_plaintext_tokens_once_encryption_started(self, db: Session) -> None:
        upgraded_ago(db, AFTER_ENCRYPTION)
        both = plaintext_connection(db)
        access_only = plaintext_connection(db, refresh=None)

        result = provider_token_encryption_service.run(db)

        assert (result.sweep, result.updated, result.changed_meanwhile) == (TokenSweep.ENCRYPT, 2, 0)
        stored = raw_tokens(db, both)
        assert all(is_encrypted(value) for value in stored)
        assert "access-secret" not in str(stored)
        assert "refresh-secret" not in str(stored)
        assert decrypted(stored) == ("access-secret", "refresh-secret")
        access, refresh = raw_tokens(db, access_only)
        assert is_encrypted(access)
        assert refresh is None

    def test_runs_in_batches(self, db: Session) -> None:
        upgraded_ago(db, AFTER_ENCRYPTION)
        ids = [plaintext_connection(db) for _ in range(5)]

        result = provider_token_encryption_service.run(db, batch_size=2)

        assert result.updated == 5
        assert all(is_encrypted(raw_tokens(db, connection_id)[0]) for connection_id in ids)

    def test_stops_when_a_downgrade_drops_the_marker_between_batches(self, db: Session) -> None:
        upgraded_ago(db, AFTER_ENCRYPTION)
        ids = [plaintext_connection(db) for _ in range(3)]
        replace_values = provider_token_encryption_service.repo.replace_values

        def replace_then_downgrade(*args: object, **kwargs: object) -> bool:
            replaced = replace_values(*args, **kwargs)  # type: ignore[arg-type]
            db.execute(text("DELETE FROM provider_token_encryption"))
            return replaced

        with patch.object(provider_token_encryption_service.repo, "replace_values", side_effect=replace_then_downgrade):
            result = provider_token_encryption_service.run(db, batch_size=1)

        assert (result.updated, result.interrupted) == (1, True)
        assert sum(is_encrypted(raw_tokens(db, connection_id)[0]) for connection_id in ids) == 1

    def test_skips_the_scan_for_an_hour_after_a_clean_run(self, db: Session) -> None:
        upgraded_ago(db, AFTER_ENCRYPTION)
        connection_id = plaintext_connection(db)
        assert provider_token_encryption_service.run(db).updated == 1  # changed something: no clean flag yet
        assert provider_token_encryption_service.run(db).skipped is False  # scans, finds nothing: sets the flag

        # A plaintext token written now (a process with another SECRET_KEY) waits for the flag to expire
        store_raw_tokens(db, connection_id, "late-access", None)
        with patch.object(
            provider_token_encryption_service.repo,
            "find_batch",
            wraps=provider_token_encryption_service.repo.find_batch,
        ) as find_batch:
            result = provider_token_encryption_service.run(db)

        assert result.skipped is True
        find_batch.assert_not_called()
        assert raw_tokens(db, connection_id) == ("late-access", None)

    def test_without_the_marker_it_never_skips(self, db: Session) -> None:
        # After a downgrade: a stale process can still write an encrypted token, decrypted on the next run
        assert provider_token_encryption_service.run(db).skipped is False
        connection_id = encrypted_connection(db)

        result = provider_token_encryption_service.run(db)

        assert (result.skipped, result.updated) == (False, 1)
        assert raw_tokens(db, connection_id) == ("access-secret", "refresh-secret")

    def test_clean_flag_set_before_a_downgrade_does_not_skip(self, db: Session) -> None:
        # A clean run while the marker existed set the flag; after the downgrade a stale process can still write an
        # encrypted token, decrypted on the next run, not once the flag expires
        upgraded_ago(db, BEFORE_ENCRYPTION)
        assert provider_token_encryption_service.run(db).skipped is False  # scans, finds nothing: sets the flag
        assert provider_token_encryption_service.run(db).skipped is True
        db.execute(text("DROP TABLE provider_token_encryption"))
        connection_id = encrypted_connection(db)

        result = provider_token_encryption_service.run(db)

        assert (result.sweep, result.skipped, result.updated) == (TokenSweep.DECRYPT, False, 1)
        assert raw_tokens(db, connection_id) == ("access-secret", "refresh-secret")

    def test_clean_flag_of_the_other_sweep_does_not_skip(self, db: Session) -> None:
        # Clean before encryption started; once it starts, the encrypt sweep runs right away
        upgraded_ago(db, BEFORE_ENCRYPTION)
        assert provider_token_encryption_service.run(db).sweep is TokenSweep.DECRYPT
        db.execute(text("DELETE FROM provider_token_encryption"))
        upgraded_ago(db, AFTER_ENCRYPTION)
        connection_id = plaintext_connection(db)

        result = provider_token_encryption_service.run(db)

        assert (result.sweep, result.skipped, result.updated) == (TokenSweep.ENCRYPT, False, 1)
        assert is_encrypted(raw_tokens(db, connection_id)[0])

    def test_second_run_changes_nothing(self, db: Session) -> None:
        upgraded_ago(db, AFTER_ENCRYPTION)
        connection_id = plaintext_connection(db)
        provider_token_encryption_service.run(db)
        stored = raw_tokens(db, connection_id)

        result = provider_token_encryption_service.run(db)

        assert (result.updated, result.changed_meanwhile) == (0, 0)
        assert raw_tokens(db, connection_id) == stored

    def test_encrypts_only_the_plaintext_token_of_a_row(self, db: Session) -> None:
        upgraded_ago(db, AFTER_ENCRYPTION)
        connection_id = plaintext_connection(db)
        with patch.object(settings, "secret_key", OTHER_SECRET_KEY):
            # Encrypted with a key this instance doesn't have: never decrypted, never encrypted twice
            foreign = encrypt_token("access-secret")
        store_raw_tokens(db, connection_id, foreign, "refresh-secret")

        provider_token_encryption_service.run(db)

        access, refresh = raw_tokens(db, connection_id)
        assert access == foreign
        assert decrypted((None, refresh)) == (None, "refresh-secret")

    def test_leaves_a_later_format_to_its_release(self, db: Session) -> None:
        upgraded_ago(db, AFTER_ENCRYPTION)
        connection_id = plaintext_connection(db, access=LATER_FORMAT)

        result = provider_token_encryption_service.run(db)

        assert (result.updated, result.undecryptable) == (1, 0)
        access, refresh = raw_tokens(db, connection_id)
        assert access == LATER_FORMAT
        assert decrypted((None, refresh)) == (None, "refresh-secret")

    @pytest.mark.parametrize("upgraded", [None, BEFORE_ENCRYPTION], ids=["no_marker", "before_the_wait_ends"])
    def test_leaves_plaintext_tokens_before_encryption_started(self, db: Session, upgraded: timedelta | None) -> None:
        if upgraded is not None:
            upgraded_ago(db, upgraded)
        connection_id = plaintext_connection(db)

        result = provider_token_encryption_service.run(db)

        assert (result.sweep, result.updated) == (TokenSweep.DECRYPT, 0)
        assert raw_tokens(db, connection_id) == ("access-secret", "refresh-secret")

    def test_token_refreshed_meanwhile_is_not_overwritten(self, db: Session) -> None:
        upgraded_ago(db, AFTER_ENCRYPTION)
        connection_id = plaintext_connection(db)
        service = ProviderTokenEncryptionService()
        replace_values = service.repo.replace_values

        def refreshed_first(db: Session, *args: object, **kwargs: object) -> bool:
            # Another worker refreshes the token between the sweep's read and its update
            store_raw_tokens(db, connection_id, "refreshed-access", "refreshed-refresh")
            return replace_values(db, *args, **kwargs)  # type: ignore[arg-type]

        with patch.object(service.repo, "replace_values", side_effect=refreshed_first):
            result = service.run(db)

        assert (result.updated, result.changed_meanwhile) == (0, 1)
        assert raw_tokens(db, connection_id) == ("refreshed-access", "refreshed-refresh")

    def test_marker_dropped_mid_lookup_still_decrypts(self, db: Session) -> None:
        # A downgrade drops the table between the existence check and the query: no marker, and the run goes on
        connection_id = encrypted_connection(db)
        db.execute(text("DROP TABLE provider_token_encryption"))

        with patch("app.utils.token_encryption._MARKER_TABLE_EXISTS", text("SELECT true")):
            result = provider_token_encryption_service.run(db)

        assert (result.sweep, result.updated) == (TokenSweep.DECRYPT, 1)
        assert raw_tokens(db, connection_id) == ("access-secret", "refresh-secret")

    def test_unreadable_marker_changes_nothing(self, db: Session) -> None:
        upgraded_ago(db, AFTER_ENCRYPTION)
        connection_id = plaintext_connection(db)

        with (
            patch.object(
                provider_token_encryption_service.repo,
                "get_encryption_start",
                side_effect=OSError("connection refused"),
            ),
            pytest.raises(OSError, match="connection refused"),
        ):
            provider_token_encryption_service.run(db)

        assert raw_tokens(db, connection_id) == ("access-secret", "refresh-secret")


class TestDecryptSweep:
    """Before encryption started, a token encrypted early (a stale process after a downgrade) is decrypted."""

    @pytest.mark.parametrize("upgraded", [None, BEFORE_ENCRYPTION], ids=["no_marker", "before_the_wait_ends"])
    def test_decrypts_tokens_before_encryption_started(self, db: Session, upgraded: timedelta | None) -> None:
        if upgraded is not None:
            upgraded_ago(db, upgraded)
        connection_id = encrypted_connection(db)

        result = provider_token_encryption_service.run(db)

        assert (result.sweep, result.updated) == (TokenSweep.DECRYPT, 1)
        assert raw_tokens(db, connection_id) == ("access-secret", "refresh-secret")

    def test_leaves_encrypted_tokens_once_encryption_started(self, db: Session) -> None:
        upgraded_ago(db, AFTER_ENCRYPTION)
        connection_id = encrypted_connection(db)
        stored = raw_tokens(db, connection_id)

        provider_token_encryption_service.run(db)

        assert raw_tokens(db, connection_id) == stored

    def test_token_encrypted_with_another_key_is_left_as_it_is(self, db: Session) -> None:
        decryptable = encrypted_connection(db)
        # A plain id: the expired model would reload the row, and its tokens no longer decrypt
        foreign = UserConnectionFactory().id
        with patch.object(settings, "secret_key", OTHER_SECRET_KEY):
            stored = (encrypt_token("access-secret"), encrypt_token("refresh-secret"))
        store_raw_tokens(db, foreign, *stored)

        result = provider_token_encryption_service.run(db)

        assert (result.updated, result.undecryptable) == (1, 1)
        assert raw_tokens(db, foreign) == stored
        assert raw_tokens(db, decryptable) == ("access-secret", "refresh-secret")

    def test_leaves_a_later_format_to_its_release(self, db: Session) -> None:
        connection_id = plaintext_connection(db, access=LATER_FORMAT, refresh=None)

        result = provider_token_encryption_service.run(db)

        assert (result.updated, result.undecryptable) == (0, 0)
        assert raw_tokens(db, connection_id) == (LATER_FORMAT, None)


class TestWebhookSecretSweep:
    """The sweep covers Polar's webhook secret in ``provider_settings`` like the tokens."""

    def test_encrypts_it_once_encryption_started(self, db: Session) -> None:
        upgraded_ago(db, AFTER_ENCRYPTION)
        store_raw_webhook_secret(db, "polar", "polar-secret")

        result = provider_token_encryption_service.run(db)

        stored = raw_webhook_secret(db, "polar")
        assert result.updated == 1
        assert is_encrypted(stored)
        assert decrypt_token(stored or "") == "polar-secret"

    def test_decrypts_it_before_encryption_started(self, db: Session) -> None:
        store_raw_webhook_secret(db, "polar", encrypt_token("polar-secret"))

        result = provider_token_encryption_service.run(db)

        assert (result.sweep, result.updated) == (TokenSweep.DECRYPT, 1)
        assert raw_webhook_secret(db, "polar") == "polar-secret"

    def test_tokens_and_secret_in_one_run_across_batches(self, db: Session) -> None:
        upgraded_ago(db, AFTER_ENCRYPTION)
        ids = [plaintext_connection(db) for _ in range(3)]
        store_raw_webhook_secret(db, "polar", "polar-secret")

        result = provider_token_encryption_service.run(db, batch_size=2)

        assert (result.updated, result.interrupted) == (4, False)
        assert all(is_encrypted(raw_tokens(db, connection_id)[0]) for connection_id in ids)
        assert is_encrypted(raw_webhook_secret(db, "polar"))


class TestTask:
    def test_logs_what_it_changed_without_the_tokens(
        self, db: Session, mock_session_local: Callable[[Session], MagicMock]
    ) -> None:
        upgraded_ago(db, AFTER_ENCRYPTION)
        plaintext_connection(db)

        with (
            patch.object(task, "SessionLocal", return_value=mock_session_local(db)),
            patch.object(task, "logger") as logger,
        ):
            task.apply_provider_token_encryption()

        kwargs = logger.info.call_args.kwargs
        assert (kwargs["sweep"], kwargs["updated"], kwargs["changed_meanwhile"]) == ("encrypt", 1, 0)
        assert "access-secret" not in str(logger.mock_calls)
        assert "refresh-secret" not in str(logger.mock_calls)
        logger.error.assert_not_called()

    def test_alerts_on_tokens_it_cannot_decrypt(
        self, db: Session, mock_session_local: Callable[[Session], MagicMock]
    ) -> None:
        foreign = UserConnectionFactory().id
        with patch.object(settings, "secret_key", OTHER_SECRET_KEY):
            store_raw_tokens(db, foreign, encrypt_token("access-secret"), None)

        with (
            patch.object(task, "SessionLocal", return_value=mock_session_local(db)),
            patch.object(task, "logger") as logger,
        ):
            task.apply_provider_token_encryption()

        kwargs = logger.error.call_args.kwargs
        assert (kwargs["undecryptable"], kwargs["alert"]) == (1, True)
        logger.info.assert_not_called()

    def test_secret_key_other_than_the_markers_changes_nothing_and_alerts(
        self, db: Session, mock_session_local: Callable[[Session], MagicMock]
    ) -> None:
        upgraded_ago(db, AFTER_ENCRYPTION, secret_key=OTHER_SECRET_KEY)
        plaintext_id = plaintext_connection(db)
        encrypted_id = encrypted_connection(db)
        encrypted_stored = raw_tokens(db, encrypted_id)

        with (
            patch.object(task, "SessionLocal", return_value=mock_session_local(db)),
            patch.object(task, "logger") as logger,
        ):
            task.apply_provider_token_encryption()

        assert raw_tokens(db, plaintext_id) == ("access-secret", "refresh-secret")
        assert raw_tokens(db, encrypted_id) == encrypted_stored
        assert logger.error.call_args.kwargs["alert"] is True
        logger.info.assert_not_called()

    def test_a_persisting_problem_alerts_once_an_hour(
        self, db: Session, mock_session_local: Callable[[Session], MagicMock]
    ) -> None:
        upgraded_ago(db, AFTER_ENCRYPTION, secret_key=OTHER_SECRET_KEY)

        with (
            patch.object(task, "SessionLocal", return_value=mock_session_local(db)),
            patch.object(task, "logger") as logger,
        ):
            task.apply_provider_token_encryption()
            task.apply_provider_token_encryption()

        logger.error.assert_called_once()
        logger.warning.assert_called_once()

    def test_skips_while_another_run_holds_the_lock(
        self, db: Session, mock_session_local: Callable[[Session], MagicMock]
    ) -> None:
        upgraded_ago(db, AFTER_ENCRYPTION)
        connection_id = plaintext_connection(db)
        holder = redis_lock.acquire(task._LOCK_KEY, 60)
        assert holder is not None

        try:
            with patch.object(task, "SessionLocal", return_value=mock_session_local(db)):
                task.apply_provider_token_encryption()
        finally:
            redis_lock.release(task._LOCK_KEY, holder)

        assert raw_tokens(db, connection_id) == ("access-secret", "refresh-secret")

    def test_releases_the_lock_after_a_run(
        self, db: Session, mock_session_local: Callable[[Session], MagicMock]
    ) -> None:
        upgraded_ago(db, AFTER_ENCRYPTION, secret_key=OTHER_SECRET_KEY)  # the run ends on SecretKeyMismatchError

        with patch.object(task, "SessionLocal", return_value=mock_session_local(db)):
            task.apply_provider_token_encryption()

        assert redis_lock.acquire(task._LOCK_KEY, 60) is not None

    def test_quiet_when_nothing_to_change(
        self, db: Session, mock_session_local: Callable[[Session], MagicMock]
    ) -> None:
        plaintext_connection(db)

        with (
            patch.object(task, "SessionLocal", return_value=mock_session_local(db)),
            patch.object(task, "logger") as logger,
        ):
            task.apply_provider_token_encryption()

        assert logger.mock_calls == []
