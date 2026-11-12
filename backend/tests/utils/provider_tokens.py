"""Provider secrets as stored (tokens in ``user_connection``, webhook secrets in ``provider_settings``), and the marker
that schedules their encryption."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.utils.token_encryption import ENCRYPTION_DELAY, key_fingerprint, write_schedule

OTHER_SECRET_KEY = "b" * 64
# Encrypted once, with "k" * 64 as SECRET_KEY: pins the key derivation and the stored format, which rows
# encrypted by an earlier release (and the migration's own copy of this code) depend on
PINNED_SECRET_KEY = "k" * 64
PINNED_ENCRYPTED = (
    "\u00a7enc:v1:gAAAAABq7OWc0wodjZXooIzqXJDJ1NnUHDmPL7u336xfyRobMLZc643zGPIHUPWpdsd3TeSHFyezVwE-a7DH1H8BmNh9a2-gvQ=="
)
# A value a later release could store: the mark, then a format version this one doesn't know
LATER_FORMAT = "\u00a7enc:v2:not-for-this-release"

# Either side of the wait between the upgrade and encrypted writes
BEFORE_ENCRYPTION = ENCRYPTION_DELAY - timedelta(hours=1)
AFTER_ENCRYPTION = ENCRYPTION_DELAY + timedelta(minutes=1)


def raw_tokens(db: Session, connection_id: UUID) -> tuple[str | None, str | None]:
    """The token columns as stored, bypassing the model's decryption."""
    row = db.execute(
        text("SELECT access_token, refresh_token FROM user_connection WHERE id = :id"), {"id": connection_id}
    ).one()
    return row.access_token, row.refresh_token


def store_raw_tokens(db: Session, connection_id: UUID, access_token: str | None, refresh_token: str | None) -> None:
    """Write the token columns as given, bypassing the model's encryption."""
    db.execute(
        text("UPDATE user_connection SET access_token = :access, refresh_token = :refresh WHERE id = :id"),
        {"access": access_token, "refresh": refresh_token, "id": connection_id},
    )
    db.expire_all()


def upgraded_ago(db: Session, age: timedelta, secret_key: str | None = None) -> None:
    """The marker the migration writes, as if the upgrade ran ``age`` ago with ``secret_key`` (default: the configured
    one); the write schedule reads it afresh."""
    db.execute(
        text("INSERT INTO provider_token_encryption (id, created_at, key_check) VALUES (1, :at, :key_check)"),
        {"at": datetime.now(timezone.utc) - age, "key_check": key_fingerprint(secret_key or settings.secret_key)},
    )
    write_schedule.reset()


def raw_webhook_secret(db: Session, provider: str) -> str | None:
    """The provider's webhook secret as stored, bypassing the model's decryption."""
    return db.execute(
        text("SELECT webhook_secret FROM provider_settings WHERE provider = :provider"), {"provider": provider}
    ).scalar_one()


def store_raw_webhook_secret(db: Session, provider: str, secret: str | None) -> None:
    """Write the provider's webhook secret as given (creating its settings row), bypassing the model's encryption."""
    db.execute(
        text(
            "INSERT INTO provider_settings (provider, is_enabled, webhook_secret) VALUES (:provider, true, :secret) "
            "ON CONFLICT (provider) DO UPDATE SET webhook_secret = :secret"
        ),
        {"provider": provider, "secret": secret},
    )
    db.expire_all()
