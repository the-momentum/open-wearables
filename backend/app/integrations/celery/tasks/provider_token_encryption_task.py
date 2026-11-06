from celery import shared_task

from app.constants.celery_tasks import CeleryTask
from app.database import SessionLocal
from app.integrations.redis_client import get_redis_client
from app.services.provider_token_encryption_service import TokenSweep, provider_token_encryption_service
from app.utils.exceptions import SecretKeyMismatchError
from app.utils.structured_logging import get_logger

logger = get_logger(__name__)

# The task runs every 5 minutes: a problem that persists alerts once an hour, and is logged as a warning in between
ALERT_INTERVAL_SECONDS = 3600


def _alert_due(action: str) -> bool:
    """True once per ALERT_INTERVAL_SECONDS for ``action``, across worker processes."""
    return bool(get_redis_client().set(f"alerted:{action}", 1, nx=True, ex=ALERT_INTERVAL_SECONDS))


def _report(message: str, action: str, **fields: object) -> None:
    if _alert_due(action):
        logger.error(message, action=action, alert=True, **fields)
    else:
        logger.warning(message, action=action, **fields)


@shared_task(name=CeleryTask.APPLY_PROVIDER_TOKEN_ENCRYPTION, ignore_result=True)
def apply_provider_token_encryption() -> None:
    """Encrypt the stored provider tokens once encryption started, decrypt any encrypted early.

    Scheduled by beat; a run with nothing to change only reads. See ``provider_token_encryption_service``.
    """
    with SessionLocal() as db:
        try:
            result = provider_token_encryption_service.run(db)
        except SecretKeyMismatchError as exc:
            # Neither encrypts nor decrypts: with another key it would leave tokens no other process can read
            _report(exc.detail, "provider_token_encryption_key_mismatch")
            return

    if result.updated or result.changed_meanwhile or result.interrupted:
        logger.info(
            "Provider tokens encrypted" if result.sweep is TokenSweep.ENCRYPT else "Provider tokens decrypted",
            action="provider_token_encryption_sweep",
            sweep=result.sweep.value,
            updated=result.updated,
            changed_meanwhile=result.changed_meanwhile,
            interrupted=result.interrupted,
        )
    if result.undecryptable:
        _report(
            "Provider tokens can't be decrypted with the configured SECRET_KEY",
            "provider_token_encryption_undecryptable",
            sweep=result.sweep.value,
            undecryptable=result.undecryptable,
        )
