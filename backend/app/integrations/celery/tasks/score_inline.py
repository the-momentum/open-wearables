"""Inline score computation used after an import when there is no Celery beat.

In inline mode (``task_execution_mode="inline"``) the periodic score-fill tasks
do not run, so sleep and resilience scores are computed for the importing user
right after their data lands. Best-effort: scoring failures are logged and never
fail the import itself.
"""

from logging import getLogger
from uuid import UUID

from sqlalchemy.orm import Session

from app.integrations.celery.tasks.fill_missing_resilience_scores_task import (
    fill_missing_resilience_scores_for_user,
)
from app.integrations.celery.tasks.fill_missing_sleep_scores_task import (
    fill_missing_sleep_scores_for_user,
)
from app.utils.sentry_helpers import log_and_capture_error

logger = getLogger(__name__)


def score_user_inline(db: Session, user_id: UUID) -> None:
    """Compute any missing sleep and resilience scores for one user."""
    for fn in (fill_missing_sleep_scores_for_user, fill_missing_resilience_scores_for_user):
        try:
            fn(db, user_id)
        except Exception as e:
            log_and_capture_error(
                e,
                logger,
                f"Inline scoring failed for user {user_id}",
                extra={"user_id": str(user_id), "scorer": fn.__name__},
            )
