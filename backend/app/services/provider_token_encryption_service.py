"""Brings the stored provider tokens in line with the encryption schedule (``app.utils.token_encryption``).

Once encryption started, plaintext tokens are encrypted. Before that, and without the marker, any encrypted ones
are decrypted: a process that read the marker before a downgrade dropped it can still have encrypted a token, and
an earlier release would revoke that connection. The rows are updated as stored, past the model's EncryptedText,
and only while they still hold what was read, so a token refreshed in the meantime is never overwritten.
"""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from app.database import DbSession
from app.repositories.provider_token_encryption_repository import ProviderTokenEncryptionRepository
from app.utils.exceptions import TokenDecryptionError
from app.utils.token_encryption import (
    ENCRYPTED_PREFIX,
    decrypt_token,
    encrypt_token,
    encryption_started,
    read_encryption_start,
)

BATCH_SIZE = 500


class TokenSweep(StrEnum):
    ENCRYPT = "encrypt"
    DECRYPT = "decrypt"


@dataclass
class TokenSweepResult:
    sweep: TokenSweep
    updated: int = 0
    # Refreshed between the read and the update: left as they are, picked up on the next run if still due
    changed_meanwhile: int = 0
    # Encrypted with another SECRET_KEY: left as they are
    undecryptable: int = 0
    # The schedule changed during the run (a downgrade dropped the marker): the rest is left to the next run
    interrupted: bool = False


def _encrypt(value: str | None) -> str | None:
    return value if value is None or value.startswith(ENCRYPTED_PREFIX) else encrypt_token(value)


def _decrypt(value: str | None) -> str | None:
    return None if value is None else decrypt_token(value)


class ProviderTokenEncryptionService:
    def __init__(self) -> None:
        self.repo = ProviderTokenEncryptionRepository()

    def sweep_due(self, db: DbSession) -> TokenSweep:
        """Raises when the marker can't be read or was written with another SECRET_KEY: then nothing is changed."""
        started = encryption_started(read_encryption_start(db.connection()))
        return TokenSweep.ENCRYPT if started else TokenSweep.DECRYPT

    def run(self, db: DbSession, batch_size: int = BATCH_SIZE) -> TokenSweepResult:
        """Encrypt or decrypt the stored tokens, as the schedule says, committing each batch."""
        sweep = self.sweep_due(db)
        convert = _encrypt if sweep is TokenSweep.ENCRYPT else _decrypt
        result = TokenSweepResult(sweep)
        after_id: UUID | None = None
        while rows := self.repo.find_batch(
            db, encrypted=sweep is TokenSweep.DECRYPT, after_id=after_id, limit=batch_size
        ):
            # Checked again before every batch: each commit releases the marker, and a downgrade that drops it
            # meanwhile must not be followed by more encrypted tokens
            if after_id is not None and self.sweep_due(db) is not sweep:
                result.interrupted = True
                break
            for connection_id, access_token, refresh_token in rows:
                try:
                    replacement = (convert(access_token), convert(refresh_token))
                except TokenDecryptionError:
                    result.undecryptable += 1
                    continue
                if self.repo.replace_tokens(db, connection_id, (access_token, refresh_token), replacement):
                    result.updated += 1
                else:
                    result.changed_meanwhile += 1
            db.commit()
            after_id = rows[-1].connection_id
        return result


provider_token_encryption_service = ProviderTokenEncryptionService()
