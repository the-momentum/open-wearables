#!/usr/bin/env python3
"""One-off: set ``event_record.type = 'sleep_session'`` on Google Health sleep rows saved without it.

The Google Health sleep handler left ``type`` NULL, so ``find_adjacent_sleep_record`` (which
filters on ``sleep_session``) never matched a stored Google night. A re-fetch of the same night
hit the existing row and sent ``sleep.created`` again with the old details; only a night whose
window had shifted was inserted as a duplicate row. New rows now carry the type; this types the
old ones so their next re-fetch updates them instead.

Reads Google sources first and updates their sleep rows a chunk of sources at a time through
``ix_event_record_source_category``, committing after each chunk. An instance without Google
sources stops after one lookup on ``data_source``. Cheap and unrecorded, so every startup also
types rows an old pod writes during a rolling deploy.

Usage (inside Docker):
    docker compose exec app uv run python scripts/data_migrations/backfill_google_sleep_type.py --dry-run
    docker compose exec app uv run python scripts/data_migrations/backfill_google_sleep_type.py
"""

import argparse
from typing import cast

from sqlalchemy import CursorResult, func, select, update
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import DataSource, EventRecord
from app.schemas.enums import EventCategory, ProviderName

SOURCES_PER_BATCH = 100


def backfill_google_sleep_type(db: Session, *, dry_run: bool, batch_size: int = SOURCES_PER_BATCH) -> int:
    """Type untyped Google sleep rows, committing after each chunk of sources unless dry_run."""
    source_ids = list(
        db.scalars(
            select(DataSource.id).where(DataSource.provider == ProviderName.GOOGLE_HEALTH.value).order_by(DataSource.id)
        )
    )
    total = 0
    for start in range(0, len(source_ids), batch_size):
        untyped = (
            EventRecord.data_source_id.in_(source_ids[start : start + batch_size]),
            EventRecord.category == EventCategory.SLEEP,
            EventRecord.type.is_(None),
        )
        if dry_run:
            total += db.scalar(select(func.count()).select_from(EventRecord).where(*untyped)) or 0
            continue
        stmt = update(EventRecord).where(*untyped).values(type="sleep_session")
        total += cast(CursorResult[tuple[()]], db.execute(stmt.execution_options(synchronize_session=False))).rowcount
        db.commit()

    verb = "Would set" if dry_run else "Set"
    print(f"{verb} type on {total} Google sleep row(s) across {len(source_ids)} Google source(s).")
    if dry_run:
        print("\nDry run — no changes made.")
    return total


def main(dry_run: bool) -> None:
    with SessionLocal() as db:
        backfill_google_sleep_type(db, dry_run=dry_run)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Preview affected rows without modifying data")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
