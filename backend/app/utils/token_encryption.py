"""Provider OAuth tokens in ``user_connection``, encrypted with a key derived from SECRET_KEY.

A value is encrypted when it carries ``ENCRYPTED_PREFIX``, plaintext otherwise. Reads handle both. Writes stay
plaintext until ``ENCRYPTION_DELAY`` after the upgrade to this release (the ``provider_token_encryption`` row its
migration writes). A replica, worker or beat still on an earlier release can't decrypt a token: it would send the
ciphertext to the provider, get a 401 and revoke the connection for good. The delay leaves a rolling update, a
component updated after the others or a rollback to the earlier release time to finish while every token is
still plaintext. Once it is over, writes are encrypted and a beat task (``provider_token_encryption_service``)
encrypts the rows already there. Going back to an earlier release after that takes the migration's downgrade first,
which decrypts every token.
"""

import hmac
import threading
import time
from base64 import urlsafe_b64encode
from datetime import datetime, timedelta, timezone
from functools import cache
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from psycopg.errors import UndefinedTable
from sqlalchemy import Connection, Dialect, Engine, Text, create_engine, text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.pool import NullPool
from sqlalchemy.types import TypeDecorator

from app.config import settings
from app.utils.config_utils import derive_secret
from app.utils.exceptions import SecretKeyMismatchError, TokenDecryptionError
from app.utils.structured_logging import get_logger

logger = get_logger(__name__)

# Marks an encrypted value; a value without it is a plaintext token
ENCRYPTED_PREFIX = "enc:v1:"
KEY_PURPOSE = "provider-token-encryption"
# The marker stores the fingerprint of the SECRET_KEY the API applied the migration with: a process with another key
# doesn't encrypt, so the tokens never end up encrypted with two keys
KEY_CHECK_PURPOSE = "provider-token-key-check"
# From the upgrade to this release until tokens are written encrypted
ENCRYPTION_DELAY = timedelta(days=7)
# How long a process goes by the marker it read. It bounds how long a process keeps encrypting writes after the
# migration's downgrade dropped the marker.
MARKER_CHECK_INTERVAL_SECONDS = 60.0
_MARKER_LOOKUP_TIMEOUT_SECONDS = 5

# to_regclass first: a database the migration hasn't reached (or was downgraded from) has no table, which is no error
_MARKER_TABLE_EXISTS = text("SELECT to_regclass('provider_token_encryption') IS NOT NULL")
_MARKER = text("SELECT created_at, key_check FROM provider_token_encryption WHERE id = 1")


@cache
def _fernet(secret_key: str) -> Fernet:
    # derive_secret is an HMAC-SHA256 hex digest: its 32 bytes, base64-encoded, are a Fernet key
    return Fernet(urlsafe_b64encode(bytes.fromhex(derive_secret(secret_key, KEY_PURPOSE))))


def key_fingerprint(secret_key: str) -> str:
    """Tells two SECRET_KEYs apart without revealing them (an HMAC, like the encryption key, for another purpose)."""
    return derive_secret(secret_key, KEY_CHECK_PURPOSE)


def encrypt_token(value: str) -> str:
    return ENCRYPTED_PREFIX + _fernet(settings.secret_key).encrypt(value.encode()).decode()


def decrypt_token(value: str) -> str:
    """The token in ``value``: decrypted if it carries the prefix, as it is if it's a plaintext one.

    A prefixed value that doesn't decrypt raises: it is never passed on as a token, or the provider would reject
    it and the connection would be revoked.
    """
    if not value.startswith(ENCRYPTED_PREFIX):
        return value
    try:
        return _fernet(settings.secret_key).decrypt(value.removeprefix(ENCRYPTED_PREFIX)).decode()
    # ValueError: base64 rejects non-ASCII before Fernet can turn it into InvalidToken
    except (InvalidToken, ValueError):
        raise TokenDecryptionError(
            "A provider token can't be decrypted with the configured SECRET_KEY. "
            "The API, worker and beat must all run with the SECRET_KEY the token was encrypted with."
        ) from None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def read_encryption_start(connection: Connection) -> datetime | None:
    """When tokens start being written encrypted here, or None without the marker: plaintext for now.

    Raises when the marker can't be read, and SecretKeyMismatchError when this process' SECRET_KEY isn't the one the
    marker was written with.
    """
    if not connection.execute(_MARKER_TABLE_EXISTS).scalar():
        return None
    try:
        # In a savepoint, so a failure here doesn't abort the caller's transaction
        with connection.begin_nested():
            marker = connection.execute(_MARKER).one_or_none()
    except ProgrammingError as exc:
        # A downgrade dropped the table after the check above, while this waited for its lock: no marker
        if isinstance(exc.orig, UndefinedTable):
            return None
        raise
    if marker is None:
        return None
    if not hmac.compare_digest(marker.key_check, key_fingerprint(settings.secret_key)):
        raise SecretKeyMismatchError(
            "This process' SECRET_KEY differs from the one the API had when it applied the database migrations. "
            "The API, worker and beat must all run with the same SECRET_KEY; until then this process doesn't "
            "encrypt provider tokens."
        )
    return marker.created_at + ENCRYPTION_DELAY


def encryption_started(start: datetime | None) -> bool:
    return start is not None and _now() >= start


@cache
def _marker_engine() -> Engine:
    # Connections of its own: the lookup runs in the middle of a flush that holds one of the app pool's connections
    return create_engine(
        settings.db_uri, poolclass=NullPool, connect_args={"connect_timeout": _MARKER_LOOKUP_TIMEOUT_SECONDS}
    )


def _load_encryption_start() -> datetime | None:
    with _marker_engine().connect() as connection:
        # A downgrade holds the table locked until it commits: plaintext rather than a stalled write
        connection.execute(text(f"SET LOCAL statement_timeout = '{_MARKER_LOOKUP_TIMEOUT_SECONDS}s'"))
        return read_encryption_start(connection)


class _WriteSchedule:
    """Whether this process writes tokens encrypted, from the marker it reads at most once a minute.

    It keeps the start time rather than the answer, so writes switch to encrypted on time without another lookup.
    Anything uncertain (no marker, a failed lookup, a lookup running in another thread, a SECRET_KEY other than the
    marker's) writes plaintext, which every release and every process reads.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._start: datetime | None = None
        self._checked_at: float | None = None
        self._key_mismatch = False
        self._lookup_failing = False

    def encrypt_writes(self) -> bool:
        checked_at = self._checked_at
        if checked_at is None or time.monotonic() - checked_at >= MARKER_CHECK_INTERVAL_SECONDS:
            self._refresh()
        return encryption_started(self._start)

    def reset(self) -> None:
        with self._lock:
            self._start = None
            self._checked_at = None
            self._key_mismatch = False
            self._lookup_failing = False

    def _refresh(self) -> None:
        # Another thread is reading the marker: this write goes by what was read last
        if not self._lock.acquire(blocking=False):
            return
        try:
            key_mismatch = lookup_failing = False
            try:
                start = _load_encryption_start()
            except SecretKeyMismatchError as exc:
                start, key_mismatch = None, True
                # Once per process until it's fixed, not on every lookup
                if not self._key_mismatch:
                    logger.error(exc.detail, action="provider_token_encryption_key_mismatch", alert=True)
            except Exception as exc:
                start, lookup_failing = None, True
                # Alerts once until a lookup succeeds again: a lookup that keeps failing means encryption never starts
                if not self._lookup_failing:
                    logger.error(
                        "Could not read when provider token encryption starts, writing tokens plaintext",
                        action="provider_token_encryption_marker_unreadable",
                        exc_info=exc,
                        alert=True,
                    )
            if start != self._start:
                logger.info(
                    "Provider token encryption schedule loaded",
                    action="provider_token_encryption_schedule",
                    encrypt_writes_from=start.isoformat() if start else None,
                )
            self._start = start
            self._key_mismatch = key_mismatch
            self._lookup_failing = lookup_failing
            self._checked_at = time.monotonic()
        finally:
            self._lock.release()


write_schedule = _WriteSchedule()


class EncryptedText(TypeDecorator[str]):
    """A ``Text`` column holding a provider token, decrypted on read and encrypted on write once encryption started.

    Ciphertexts differ on every write, so the column can't be compared with a token in SQL.
    """

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect: Dialect) -> str | None:
        if value is None or not write_schedule.encrypt_writes():
            return value
        return encrypt_token(value)

    def process_result_value(self, value: Any, dialect: Dialect) -> str | None:
        return None if value is None else decrypt_token(value)
