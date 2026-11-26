#!/usr/bin/env python3
"""Backfill data_type_coverage from the data already in the database.

Coverage is maintained going forward by the write paths (DataPointSeriesRepository and
EventRecordRepository record spans in the same transaction as the data). This fills in
everything written before that existed. Without it, coverage starts at the first write after
the deploy, so a user with years of history reports it as starting that day.

Series coverage spans both the live table and the archive, where archival moves old samples
as daily aggregates: on an instance that archives, the oldest data is only there. An archive
bucket counts from the start of its day.

It runs on its own: a Celery beat task runs it once per instance (``data_migration``) in
the background, so this script is only needed for a dry run or to run it by hand. See
DataTypeCoverageRepository.backfill_from_held_data for how it stays cheap on large tables.

Usage (inside Docker), with --dry-run to count the spans it would record:
    docker compose exec app uv run python scripts/data_migrations/backfill_data_type_coverage.py
"""

import argparse

from app.integrations.celery.tasks.backfill_data_type_coverage_task import run_backfill

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Count the spans it would record without writing them")
    args = parser.parse_args()
    if found := run_backfill(dry_run=args.dry_run):
        verb = "Would record" if args.dry_run else "Recorded"
        for kind, spans in found.items():
            print(f"{verb} {spans} {kind} span(s).")
