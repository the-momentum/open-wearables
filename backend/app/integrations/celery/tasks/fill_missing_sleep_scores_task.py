from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from logging import getLogger
from uuid import UUID

from celery import shared_task
from sqlalchemy import text

from app.config import settings
from app.database import SessionLocal
from app.services.health_score_service import health_score_service
from app.services.scores.sleep_service import sleep_score_service
from app.utils.sentry_helpers import log_and_capture_error
from app.utils.structured_logging import log_structured

logger = getLogger(__name__)

# Find all non-nap sleep sessions that have no corresponding OW sleep score.
# The match is on event_record_id (direct FK) so each session gets exactly one
# score regardless of timezone-induced date collisions. wake_date (local end
# date) is used as the lookup key for get_sleep_scores_for_records and for
# result ordering. recorded_at is set to the session's exact local end datetime
# (local_end_datetime) so two sessions sharing the same wake date still produce
# distinct recorded_at values. Limited to sessions within the configured
# backfill window.
_MISSING_SCORES_QUERY = text("""
    SELECT DISTINCT
        ds.user_id,
        ds.id AS data_source_id,
        er.id AS record_id,
        (er.end_datetime + COALESCE(er.zone_offset, '+00:00')::interval)::date AS wake_date,
        (er.end_datetime + COALESCE(er.zone_offset, '+00:00')::interval) AS local_end_datetime
    FROM event_record er
    JOIN data_source ds   ON ds.id = er.data_source_id
    JOIN sleep_details sd ON sd.record_id = er.id
    LEFT JOIN health_score hs
           ON hs.event_record_id = er.id
          AND hs.category     = 'sleep'
          AND hs.provider     = 'internal'
    WHERE er.category = 'sleep'
      AND (sd.is_nap IS NULL OR sd.is_nap = false)
      AND sd.sleep_total_duration_minutes IS NOT NULL
      AND sd.sleep_total_duration_minutes > 0
      AND hs.id IS NULL
      AND er.start_datetime >= :cutoff
    ORDER BY ds.user_id, wake_date DESC
""")


@shared_task
def fill_missing_sleep_scores() -> dict:
    """Find sleep sessions without an OW sleep score and calculate them.

    Runs frequently (every few minutes) so scores appear shortly after any sync
    path (periodic pull, webhook, SDK upload). Uses a LEFT JOIN on event_record_id
    to guarantee idempotency — already-scored sessions are never re-processed.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.score_backfill_days)

    with SessionLocal() as db:
        rows = db.execute(_MISSING_SCORES_QUERY, {"cutoff": cutoff}).fetchall()

        if not rows:
            return {"saved": 0, "skipped": 0}

        # Group (record_id, wake_date, local_end_datetime) triples per user
        records_by_user: dict[UUID, list[tuple[UUID, UUID, date, datetime]]] = defaultdict(list)
        for user_id, data_source_id, record_id, wake_date, local_end in rows:
            records_by_user[user_id].append((record_id, data_source_id, wake_date, local_end))

        log_structured(
            logger,
            "info",
            f"Found {len(rows)} session(s) missing scores across {len(records_by_user)} user(s)",
            task="fill_missing_sleep_scores",
        )

        total_saved = 0
        total_skipped = 0

        for uid, record_wakes_extended in records_by_user.items():
            sessions = [(rid, dsid, local_end) for rid, dsid, _, local_end in record_wakes_extended]
            try:
                scores_to_save = sleep_score_service.build_internal_sleep_scores(db, uid, sessions)
            except Exception as e:
                total_skipped += len(sessions)
                log_and_capture_error(
                    e,
                    logger,
                    f"Failed to fetch sleep data for user {uid}",
                    extra={"user_id": str(uid), "task": "fill_missing_sleep_scores"},
                )
                continue

            if not scores_to_save:
                total_skipped += len(sessions)
                continue

            try:
                health_score_service.bulk_create(db, scores_to_save)
                db.commit()
                total_saved += len(scores_to_save)
                total_skipped += len(sessions) - len(scores_to_save)
            except Exception as e:
                db.rollback()
                total_skipped += len(sessions)
                log_and_capture_error(
                    e,
                    logger,
                    f"Failed to save sleep scores for user {uid}",
                    extra={"user_id": str(uid), "task": "fill_missing_sleep_scores"},
                )

        log_structured(
            logger,
            "info",
            f"Sleep score fill complete: {total_saved} saved, {total_skipped} skipped",
            task="fill_missing_sleep_scores",
            saved=total_saved,
            skipped=total_skipped,
        )

        return {"saved": total_saved, "skipped": total_skipped}
