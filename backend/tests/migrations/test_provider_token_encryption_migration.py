"""The migration that schedules provider secret encryption, and the downgrade that decrypts every secret.

The test database is built from the models, so upgrade() and downgrade() run directly on the test connection.
"""

import importlib.util
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import cast
from unittest.mock import patch
from uuid import UUID

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import BaseDbModel
from app.repositories.provider_token_encryption_repository import SECRET_COLUMNS
from app.utils.token_encryption import (
    ENCRYPTION_DELAY,
    EncryptedText,
    encrypt_token,
    key_fingerprint,
    read_encryption_start,
)
from tests.factories import UserConnectionFactory
from tests.utils.provider_tokens import (
    AFTER_ENCRYPTION,
    LATER_FORMAT,
    OTHER_SECRET_KEY,
    PINNED_ENCRYPTED,
    PINNED_SECRET_KEY,
    raw_tokens,
    raw_webhook_secret,
    store_raw_tokens,
    store_raw_webhook_secret,
    upgraded_ago,
)

_VERSIONS = Path(__file__).resolve().parents[2] / "migrations/versions"


def _load_migration(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None
    assert spec.loader is not None
    module = cast(ModuleType, importlib.util.module_from_spec(spec))
    spec.loader.exec_module(module)
    return module


migration = _load_migration(_VERSIONS / "2026_11_05_2130-7045b6620672_provider_token_encryption.py")

Step = Callable[[Callable[[], None]], None]


@pytest.fixture
def run(db: Session) -> Step:
    def _run(step: Callable[[], None]) -> None:
        with Operations.context(MigrationContext.configure(connection=db.connection())):
            step()
        db.expire_all()

    return _run


def connection_with(db: Session, access: str | None, refresh: str | None) -> UUID:
    connection_id = UserConnectionFactory().id
    store_raw_tokens(db, connection_id, access, refresh)
    return connection_id


def marker_table_exists(db: Session) -> bool:
    return bool(db.execute(text("SELECT to_regclass('provider_token_encryption') IS NOT NULL")).scalar())


class TestUpgrade:
    def test_records_when_it_ran_and_leaves_tokens_alone(self, db: Session, run: Step) -> None:
        db.execute(text("DROP TABLE provider_token_encryption"))
        connection_id = connection_with(db, "access-secret", "refresh-secret")

        run(migration.upgrade)

        upgraded_at = db.execute(text("SELECT created_at FROM provider_token_encryption WHERE id = 1")).scalar_one()
        assert upgraded_at == db.execute(text("SELECT now()")).scalar_one()
        assert read_encryption_start(db.connection()) == upgraded_at + ENCRYPTION_DELAY
        assert raw_tokens(db, connection_id) == ("access-secret", "refresh-secret")

    def test_stores_the_fingerprint_of_the_secret_key_it_ran_with(self, db: Session, run: Step) -> None:
        db.execute(text("DROP TABLE provider_token_encryption"))

        with patch.object(settings, "secret_key", OTHER_SECRET_KEY):
            run(migration.upgrade)

        key_check = db.execute(text("SELECT key_check FROM provider_token_encryption WHERE id = 1")).scalar_one()
        assert key_check == key_fingerprint(OTHER_SECRET_KEY)
        assert OTHER_SECRET_KEY not in key_check


class TestDowngrade:
    def test_decrypts_the_webhook_secret(self, db: Session, run: Step) -> None:
        upgraded_ago(db, AFTER_ENCRYPTION)
        store_raw_webhook_secret(db, "polar", encrypt_token("polar-secret"))

        run(migration.downgrade)

        assert raw_webhook_secret(db, "polar") == "polar-secret"

    def test_decrypts_every_token_and_drops_the_marker(self, db: Session, run: Step) -> None:
        upgraded_ago(db, AFTER_ENCRYPTION)
        encrypted = [connection_with(db, encrypt_token(f"access-{i}"), encrypt_token(f"refresh-{i}")) for i in range(3)]
        mixed = connection_with(db, encrypt_token("access-secret"), "refresh-secret")
        plaintext = connection_with(db, "access-secret", None)
        empty = connection_with(db, None, None)

        with patch.object(migration, "BATCH_SIZE", 2):
            run(migration.downgrade)

        assert [raw_tokens(db, connection_id) for connection_id in encrypted] == [
            (f"access-{i}", f"refresh-{i}") for i in range(3)
        ]
        assert raw_tokens(db, mixed) == ("access-secret", "refresh-secret")
        assert raw_tokens(db, plaintext) == ("access-secret", None)
        assert raw_tokens(db, empty) == (None, None)
        assert not marker_table_exists(db)

    def test_reads_the_format_earlier_releases_wrote(self, db: Session, run: Step) -> None:
        connection_id = connection_with(db, PINNED_ENCRYPTED, None)

        with patch.object(settings, "secret_key", PINNED_SECRET_KEY):
            run(migration.downgrade)

        assert raw_tokens(db, connection_id) == ("access-secret", None)

    def test_token_changed_meanwhile_is_read_again_not_overwritten(self, db: Session, run: Step) -> None:
        connection_id = connection_with(db, encrypt_token("old-access"), encrypt_token("old-refresh"))
        refreshed = (encrypt_token("new-access"), encrypt_token("new-refresh"))
        decrypt = migration._decrypt
        calls = 0

        def refreshed_during_the_first_read(fernet: object, value: str | None) -> str | None:
            nonlocal calls
            calls += 1
            if calls == 1:
                # A process that still encrypts refreshes the token between the downgrade's read and its update
                store_raw_tokens(db, connection_id, *refreshed)
            return decrypt(fernet, value)

        with patch.object(migration, "_decrypt", refreshed_during_the_first_read):
            run(migration.downgrade)

        assert raw_tokens(db, connection_id) == ("new-access", "new-refresh")

    def test_stops_when_tokens_keep_being_encrypted(self, db: Session, run: Step) -> None:
        with (
            patch.object(migration, "_decrypt_pass", return_value=1),
            pytest.raises(RuntimeError, match="Stop the API"),
        ):
            run(migration.downgrade)

    def test_another_secret_key_fails_and_changes_nothing(self, db: Session, run: Step) -> None:
        upgraded_ago(db, AFTER_ENCRYPTION)
        connection_id = connection_with(db, encrypt_token("access-secret"), encrypt_token("refresh-secret"))
        stored = raw_tokens(db, connection_id)

        # A savepoint stands in for the migration's transaction, which the error rolls back
        with (
            patch.object(settings, "secret_key", OTHER_SECRET_KEY),
            pytest.raises(RuntimeError, match="SECRET_KEY") as exc_info,
            db.begin_nested(),
        ):
            run(migration.downgrade)

        assert "access-secret" not in str(exc_info.value)
        assert "refresh-secret" not in str(exc_info.value)
        assert raw_tokens(db, connection_id) == stored
        assert marker_table_exists(db)

    def test_later_format_fails_and_changes_nothing(self, db: Session, run: Step) -> None:
        upgraded_ago(db, AFTER_ENCRYPTION)
        encrypted = connection_with(db, encrypt_token("access-secret"), None)
        later = connection_with(db, LATER_FORMAT, None)
        stored = raw_tokens(db, encrypted)

        # A savepoint stands in for the migration's transaction, which the error rolls back
        with pytest.raises(RuntimeError, match="later release"), db.begin_nested():
            run(migration.downgrade)

        assert raw_tokens(db, encrypted) == stored
        assert raw_tokens(db, later) == (LATER_FORMAT, None)
        assert marker_table_exists(db)

    def test_upgrade_after_a_downgrade_restarts_the_wait(self, db: Session, run: Step) -> None:
        upgraded_ago(db, AFTER_ENCRYPTION)

        run(migration.downgrade)
        run(migration.upgrade)

        start = read_encryption_start(db.connection())
        assert start is not None
        assert start == db.execute(text("SELECT now()")).scalar_one() + ENCRYPTION_DELAY


def test_every_encrypted_column_is_swept_and_downgraded() -> None:
    """A column stored with EncryptedText that the sweep or every downgrade misses would stay encrypted after a
    downgrade, and an earlier release would take its ciphertext for the value. A later column is decrypted by the
    downgrade of the migration that starts encrypting it, never by editing a released one."""
    models = {
        (column.table.name, next(iter(column.table.primary_key)).name, column.name)
        for table in BaseDbModel.metadata.tables.values()
        for column in table.columns
        if isinstance(column.type, EncryptedText)
    }
    swept = {
        (columns.table.name, columns.key.name, value.name) for columns in SECRET_COLUMNS for value in columns.values
    }
    downgraded = {
        (table, key, value)
        for path in sorted(_VERSIONS.glob("*.py"))
        if "_SECRET_COLUMNS" in path.read_text()
        for table, key, *values in _load_migration(path)._SECRET_COLUMNS
        for value in values
    }

    assert models == swept == downgraded
    # Released: its downgrade runs after those of later migrations, which may drop their columns first
    assert migration._SECRET_COLUMNS == (
        ("user_connection", "id", "access_token", "refresh_token"),
        ("provider_settings", "provider", "webhook_secret"),
    )
