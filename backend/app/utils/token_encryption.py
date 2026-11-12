"""Provider secrets (OAuth tokens, webhook secrets) encrypted with a key derived from SECRET_KEY.

Values starting with ``ENCRYPTED_MARK`` are encrypted, others plaintext; reads handle both. Writes stay plaintext for
``ENCRYPTION_DELAY`` after the migration: an earlier release would send a ciphertext to the provider and revoke the
connection, so it has that long to be updated or rolled back.
"""

import hmac
import threading
import time
from base64 import urlsafe_b64encode
from datetime import datetime, timedelta, timezone
from functools import cache
from typing import Any, NamedTuple

from cryptography.fernet import Fernet, InvalidToken
from psycopg.errors import UndefinedTable
from sqlalchemy import Connection, DateTime, Dialect, Engine, Integer, Text, column, create_engine, func, select, text
from sqlalchemy import table as table_clause
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.pool import NullPool
from sqlalchemy.types import TypeDecorator

from app.config import settings
from app.utils.config_utils import derive_secret
from app.utils.exceptions import SecretKeyMismatchError, TokenDecryptionError
from app.utils.structured_logging import get_logger

logger = get_logger(__name__)

# Starts every value stored encrypted, whatever the format. RFC 6749 (appendix A.12, A.17) allows only printable ASCII
# (VSCHAR) in access and refresh tokens, and Polar's webhook secret is a UUID, so no plaintext value starts with it.
ENCRYPTED_MARK = "\u00a7"  # "§"
# This release's format (Fernet). A later one changes the version and is refused, never taken for plaintext.
ENCRYPTED_PREFIX = f"{ENCRYPTED_MARK}enc:v1:"
KEY_PURPOSE = "provider-token-encryption"
# For the SECRET_KEY fingerprint in the marker: a process with another key doesn't encrypt, so no two keys get mixed
KEY_CHECK_PURPOSE = "provider-token-key-check"
# From the upgrade to this release until secrets are written encrypted
ENCRYPTION_DELAY = timedelta(days=7)
# How long a process trusts the marker it read, so how long it may keep encrypting after a downgrade
MARKER_CHECK_INTERVAL_SECONDS = 60.0
_MARKER_LOOKUP_TIMEOUT_SECONDS = 5


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
    """The token in ``value``: decrypted if it carries the mark, as it is if it's a plaintext one.

    A marked value that doesn't decrypt, or is in a later release's format, raises: it is never passed on as a
    token, or the provider would reject it and the connection would be revoked.
    """
    if not value.startswith(ENCRYPTED_MARK):
        return value
    if not value.startswith(ENCRYPTED_PREFIX):
        raise TokenDecryptionError(
            "A provider secret is stored in a format of a later Open Wearables release, which this one can't read. "
            "Run that release, or downgrade the database with it first."
        )
    try:
        return _fernet(settings.secret_key).decrypt(value.removeprefix(ENCRYPTED_PREFIX)).decode()
    # ValueError: base64 rejects non-ASCII before Fernet can turn it into InvalidToken
    except (InvalidToken, ValueError):
        raise TokenDecryptionError(
            "A provider secret can't be decrypted with the configured SECRET_KEY. "
            "The API, worker and beat must all run with the SECRET_KEY it was encrypted with."
        ) from None


def _now() -> datetime:
    return datetime.now(timezone.utc)


# The marker table (model ``ProviderTokenEncryption``), read without the model: the models' mappings import this module
_marker_table = table_clause(
    "provider_token_encryption",
    column("id", Integer),
    column("created_at", DateTime(timezone=True)),
    column("key_check", Text),
)
# A database the migration hasn't reached (or was downgraded from) has no table, which is no error
_MARKER_TABLE_EXISTS = select(func.to_regclass(_marker_table.name).is_not(None))
_MARKER = select(_marker_table.c.created_at, _marker_table.c.key_check).where(_marker_table.c.id == 1)


class EncryptionMarker(NamedTuple):
    created_at: datetime
    key_check: str


def read_marker(connection: Connection) -> EncryptionMarker | None:
    """The row the migration wrote, or None without it (or without its table)."""
    if not connection.execute(_MARKER_TABLE_EXISTS).scalar():
        return None
    try:
        # In a savepoint, so a failure here doesn't abort the caller's transaction
        with connection.begin_nested():
            row = connection.execute(_MARKER).one_or_none()
    except ProgrammingError as exc:
        # A downgrade dropped the table after the check above, while this waited for its lock
        if isinstance(exc.orig, UndefinedTable):
            return None
        raise
    return None if row is None else EncryptionMarker(*row)


def read_encryption_start(connection: Connection) -> datetime | None:
    """``encryption_start`` of the marker in the database; raises when it can't be read."""
    return encryption_start(read_marker(connection))


def encryption_start(marker: EncryptionMarker | None) -> datetime | None:
    """When tokens start being written encrypted, or None without the marker: plaintext for now.

    Raises SecretKeyMismatchError when this process' SECRET_KEY isn't the one the marker was written with.
    """
    if marker is None:
        return None
    if not hmac.compare_digest(marker.key_check, key_fingerprint(settings.secret_key)):
        raise SecretKeyMismatchError(
            "This process' SECRET_KEY differs from the one the API had when it applied the database migrations. "
            "The API, worker and beat must all run with the same SECRET_KEY; until then this process doesn't "
            "encrypt provider secrets."
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
    """Whether writes are encrypted, from the marker re-read every MARKER_CHECK_INTERVAL_SECONDS. Anything uncertain
    (no marker, failed lookup, another SECRET_KEY) means plaintext."""

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
                        "Could not read when provider secret encryption starts, writing secrets plaintext",
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
    """A provider secret column: decrypted on read, encrypted on write once encryption started.

    Ciphertexts differ on every write, so don't compare it with a value in SQL. The sweep finds it by this type; a new
    one needs a migration whose downgrade decrypts it (in its own ``_SECRET_COLUMNS``), never an edit of a released one.
    """

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect: Dialect) -> str | None:
        if value is None or not write_schedule.encrypt_writes():
            return value
        return encrypt_token(value)

    def process_result_value(self, value: Any, dialect: Dialect) -> str | None:
        return None if value is None else decrypt_token(value)
