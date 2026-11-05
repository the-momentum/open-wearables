"""Provider OAuth tokens in ``user_connection``, encrypted with a key derived from SECRET_KEY.

Rolled out over two releases, so that a replica or worker still on the previous release never reads a token it
can't decrypt (it would send the ciphertext to the provider, get a 401 and revoke the connection for good):

1. this release reads both encrypted and plaintext values, but still writes plaintext;
2. the next one writes encrypted values and encrypts the existing rows in a migration.
"""

from base64 import urlsafe_b64encode
from functools import cache
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import Dialect, Text
from sqlalchemy.types import TypeDecorator

from app.config import settings
from app.utils.config_utils import derive_secret
from app.utils.exceptions import TokenDecryptionError

# Marks an encrypted value; a value without it is a plaintext token written before encryption
ENCRYPTED_PREFIX = "enc:v1:"
KEY_PURPOSE = "provider-token-encryption"


@cache
def _fernet(secret_key: str) -> Fernet:
    # derive_secret is an HMAC-SHA256 hex digest: its 32 bytes, base64-encoded, are a Fernet key
    return Fernet(urlsafe_b64encode(bytes.fromhex(derive_secret(secret_key, KEY_PURPOSE))))


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


class EncryptedText(TypeDecorator[str]):
    """A ``Text`` column holding a provider token, decrypted on read."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect: Dialect) -> str | None:
        # Still plaintext (step 1 of the rollout): the previous release must be able to read what this one writes
        return value

    def process_result_value(self, value: Any, dialect: Dialect) -> str | None:
        return None if value is None else decrypt_token(value)
