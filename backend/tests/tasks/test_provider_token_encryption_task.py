"""The beat task brings stored provider tokens in line with the encryption schedule."""

from collections.abc import Callable
from datetime import timedelta
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
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
    OTHER_SECRET_KEY,
    raw_tokens,
    store_raw_tokens,
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
        replace_tokens = provider_token_encryption_service.repo.replace_tokens

        def replace_then_downgrade(*args: object, **kwargs: object) -> bool:
            replaced = replace_tokens(*args, **kwargs)  # type: ignore[arg-type]
            db.execute(text("DELETE FROM provider_token_encryption"))
            return replaced

        with patch.object(provider_token_encryption_service.repo, "replace_tokens", side_effect=replace_then_downgrade):
            result = provider_token_encryption_service.run(db, batch_size=1)

        assert (result.updated, result.interrupted) == (1, True)
        assert sum(is_encrypted(raw_tokens(db, connection_id)[0]) for connection_id in ids) == 1

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
        replace_tokens = service.repo.replace_tokens

        def refreshed_first(db: Session, *args: object, **kwargs: object) -> bool:
            # Another worker refreshes the token between the sweep's read and its update
            store_raw_tokens(db, connection_id, "refreshed-access", "refreshed-refresh")
            return replace_tokens(db, *args, **kwargs)  # type: ignore[arg-type]

        with patch.object(service.repo, "replace_tokens", side_effect=refreshed_first):
            result = service.run(db)

        assert (result.updated, result.changed_meanwhile) == (0, 1)
        assert raw_tokens(db, connection_id) == ("refreshed-access", "refreshed-refresh")

    def test_unreadable_marker_changes_nothing(self, db: Session) -> None:
        upgraded_ago(db, AFTER_ENCRYPTION)
        connection_id = plaintext_connection(db)

        with (
            patch(
                "app.services.provider_token_encryption_service.read_encryption_start",
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
        assert "secret" not in str(logger.mock_calls)
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
