#!/usr/bin/env python3
"""One-off: set ``event_record.type = 'sleep_session'`` on Google Health sleep rows saved without it.

The Google Health sleep handler left ``type`` NULL, so ``find_adjacent_sleep_record`` (which
filters on ``sleep_session``) never matched an existing Google session and every re-fetch
inserted a new row instead of updating it. New rows now carry the type; this fixes the old ones
so their next re-fetch updates them too.

Idempotent: a second run finds nothing to change. Safe to run on every startup until removed.

Usage (inside Docker):
    docker compose exec app uv run python scripts/data_migrations/backfill_google_sleep_type.py --dry-run
    docker compose exec app uv run python scripts/data_migrations/backfill_google_sleep_type.py
"""

import argparse
from typing import cast

from sqlalchemy import CursorResult, select, update
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import DataSource, EventRecord
from app.schemas.enums import ProviderName


def backfill_google_sleep_type(db: Session, *, dry_run: bool) -> int:
    """Set the type on untyped Google sleep rows. Does not commit — the caller owns the transaction."""
    google_sources = select(DataSource.id).where(DataSource.provider == ProviderName.GOOGLE_HEALTH.value)
    untyped = (
        EventRecord.category == "sleep",
        EventRecord.type.is_(None),
        EventRecord.data_source_id.in_(google_sources),
    )
    if dry_run:
        count = db.query(EventRecord).filter(*untyped).count()
        print(f"Would set type on {count} Google sleep row(s).\n\nDry run — no changes made.")
        return count
    stmt = update(EventRecord).where(*untyped).values(type="sleep_session")
    count = cast(CursorResult[tuple[()]], db.execute(stmt)).rowcount
    print(f"Set type on {count} Google sleep row(s).")
    return count


def main(dry_run: bool) -> None:
    with SessionLocal() as db:
        count = backfill_google_sleep_type(db, dry_run=dry_run)
        if dry_run:
            return
        if not count:
            print("Nothing to do — all Google sleep rows are typed.")
            return
        db.commit()
        print("Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Preview affected rows without modifying data")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
