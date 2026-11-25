#!/usr/bin/env python3
"""Queue the one-off aggregate backfill (a Celery task) unless it already completed here.

The backfill copies the history into series_aggregate and event_record_aggregate in the background, so
startup does not wait for it; beat queues it again every 15 minutes until it is done.
"""

from app.database import SessionLocal
from app.integrations.celery.core import create_celery
from app.integrations.celery.tasks.aggregate_backfill_task import run_aggregate_backfill
from app.services.aggregate_backfill_service import aggregate_backfill_service

if __name__ == "__main__":
    # Outside the app, the Celery app is not configured yet: without this .delay() goes to the default broker.
    create_celery()
    with SessionLocal() as db:
        done = aggregate_backfill_service.is_done(db)
    if done:
        print("aggregate_backfill: already completed, skipping.")
    else:
        run_aggregate_backfill.delay()
        print("aggregate_backfill: queued.")
