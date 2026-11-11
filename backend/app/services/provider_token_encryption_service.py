"""Brings the stored provider secrets (OAuth tokens, webhook secrets) in line with the encryption schedule
(``app.utils.token_encryption``).

Once encryption started, plaintext values are encrypted; before that (or without the marker, after a downgrade)
encrypted ones are decrypted. A row is updated only while it still holds what was read, so a refresh wins.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.database import DbSession
from app.integrations.redis_client import get_redis_client
from app.repositories.provider_token_encryption_repository import SECRET_COLUMNS, ProviderTokenEncryptionRepository
from app.utils.exceptions import TokenDecryptionError
from app.utils.token_encryption import (
    ENCRYPTED_MARK,
    decrypt_token,
    encrypt_token,
    encryption_started,
)

BATCH_SIZE = 500
# After a run that found nothing, the same sweep skips its scan for this long. Only while the marker exists: after a
# downgrade a process can still write ciphertext for a minute, and the next run must decrypt it.
CLEAN_SKIP_SECONDS = 3600


class TokenSweep(StrEnum):
    ENCRYPT = "encrypt"
    DECRYPT = "decrypt"


def _clean_key(sweep: TokenSweep) -> str:
    return f"provider_token_encryption:clean:{sweep.value}"


@dataclass
class TokenSweepResult:
    sweep: TokenSweep
    updated: int = 0
    # Rows written between the read and the update: left as they are, picked up on the next run if still due
    changed_meanwhile: int = 0
    # Encrypted with another SECRET_KEY: left as they are
    undecryptable: int = 0
    # The schedule changed during the run (a downgrade dropped the marker): the rest is left to the next run
    interrupted: bool = False
    # A recent run of the same sweep found nothing to change, so this one didn't scan
    skipped: bool = False


def _sweep_for(start: datetime | None) -> TokenSweep:
    return TokenSweep.ENCRYPT if encryption_started(start) else TokenSweep.DECRYPT


def _encrypt(value: str | None) -> str | None:
    # A value in a later release's format is left to that release, never encrypted twice
    return value if value is None or value.startswith(ENCRYPTED_MARK) else encrypt_token(value)


def _decrypt(value: str | None) -> str | None:
    return None if value is None else decrypt_token(value)


class ProviderTokenEncryptionService:
    def __init__(self) -> None:
        self.repo = ProviderTokenEncryptionRepository()

    def run(self, db: DbSession, batch_size: int = BATCH_SIZE) -> TokenSweepResult:
        """Encrypt or decrypt the stored secrets, as the schedule says, committing each batch.

        Raises when the marker can't be read or was written with another SECRET_KEY: then nothing is changed.
        """
        start = self.repo.get_encryption_start(db)
        sweep = _sweep_for(start)
        result = TokenSweepResult(sweep)
        redis_client = get_redis_client()
        # Without the marker, not even a flag set before the downgrade (CLEAN_SKIP_SECONDS)
        if start is not None and redis_client.exists(_clean_key(sweep)):
            result.skipped = True
            return result
        convert = _encrypt if sweep is TokenSweep.ENCRYPT else _decrypt
        scanned = 0
        for columns in SECRET_COLUMNS:
            after_key = None
            while rows := self.repo.find_batch(
                db, columns, encrypted=sweep is TokenSweep.DECRYPT, after_key=after_key, limit=batch_size
            ):
                # Each commit releases the marker: a downgrade may have dropped it since
                if scanned and _sweep_for(self.repo.get_encryption_start(db)) is not sweep:
                    result.interrupted = True
                    return result
                scanned += len(rows)
                for key, stored in rows:
                    try:
                        replacement = tuple(convert(value) for value in stored)
                    except TokenDecryptionError:
                        result.undecryptable += 1
                        continue
                    if self.repo.replace_values(db, columns, key, stored, replacement):
                        result.updated += 1
                    else:
                        result.changed_meanwhile += 1
                db.commit()
                after_key = rows[-1].key
        # Without the marker, no flag (CLEAN_SKIP_SECONDS)
        if not scanned and self.repo.get_encryption_start(db) is not None:
            redis_client.set(_clean_key(sweep), 1, ex=CLEAN_SKIP_SECONDS)
        return result


provider_token_encryption_service = ProviderTokenEncryptionService()
