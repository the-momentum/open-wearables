#!/usr/bin/env python3
"""Purge Google Health API energy rows written from the total-calories rollUp.

total-calories is a computed aggregate, not a measurement: it exists only in the
rollUp response union, Google evaluates it as a rate over whatever window is asked
for, and it mixes active with basal. It was stored in the energy series, which means
active energy, so the values were inflated by BMR. Worse, rollUp anchors its buckets
to the requested range start, so every historical sync wrote the same hour at a
different recorded_at and the unique constraint could not collapse them — a day with
four syncs summed to four times the real figure (#1577).

Ingestion now reads active-energy-burned and basal-energy-burned instead, which carry
real records with their own intervals. Those rows are tagged with an external_id
(see _TAGGED_SERIES in google/health_api/data_247.py), so this purge deletes only the
untagged legacy rows and leaves anything the current code wrote alone.

Scoped to source='google_health_api': Health Connect SDK rows map active calories
correctly and must not be touched.

Idempotent: once purged, no untagged rows match, so re-runs are no-ops. Safe to run on
every startup until removed. Re-run a historical sync afterwards to backfill active
energy over the deleted range.

Usage (inside Docker):
    docker compose exec app uv run python scripts/data_migrations/purge_google_total_calories_energy.py --dry-run
    docker compose exec app uv run python scripts/data_migrations/purge_google_total_calories_energy.py
"""

import argparse

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import SessionLocal

PROVIDER = "google"
SOURCE = "google_health_api"
SERIES_CODE = "energy"

_PARAMS = {"provider": PROVIDER, "source": SOURCE, "code": SERIES_CODE}

_WHERE = """
    FROM data_point_series dps
    JOIN series_type_definition std ON std.id = dps.series_type_definition_id
    JOIN data_source ds ON ds.id = dps.data_source_id
    WHERE ds.provider = :provider
      AND ds.source = :source
      AND std.code = :code
      AND dps.external_id IS NULL
"""

_COUNT = text(f"SELECT COUNT(*) {_WHERE}")

_DELETE = text(f"""
    DELETE FROM data_point_series
    WHERE id IN (SELECT dps.id {_WHERE})
""")


def run(db: Session, dry_run: bool) -> int:
    stale = db.execute(_COUNT, _PARAMS).scalar_one()
    if not stale:
        print("No untagged Google Health API energy rows; nothing to purge.")
        return 0
    if dry_run:
        print(f"[dry-run] would delete {stale} untagged Google Health API energy row(s).")
        return stale
    deleted = db.execute(_DELETE, _PARAMS).rowcount  # ty: ignore[unresolved-attribute]
    db.commit()
    print(f"Deleted {deleted} untagged Google Health API energy row(s) written from total-calories.")
    return deleted


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="report what would be deleted and exit")
    args = parser.parse_args()
    with SessionLocal() as db:
        run(db, args.dry_run)


if __name__ == "__main__":
    main()
