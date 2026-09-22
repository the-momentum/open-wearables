#!/usr/bin/env python3
"""Purge Google Health API energy rows written from the total-calories rollUp.

total-calories is a computed aggregate, not a measurement: it exists only in the
rollUp response union, Google evaluates it as a rate over whatever window is asked
for, and it mixes active with basal. It was stored in the energy series, which means
active energy, so the values were inflated by BMR. Worse, rollUp anchors its buckets
to the requested range start, so every historical sync wrote the same hour at a
different recorded_at and the unique constraint could not collapse them — a day with
four syncs summed to four times the real figure (#1577).

Ingestion now reads active-energy-burned (native intervals via reconcile/list) into
energy, and derives basal_energy per civil day as total-calories minus
active-energy-burned from dailyRollUp (google/health_api/metrics/derived.py). The new
energy rows carry an external_id (set in GoogleHealth247Data._sample), so in the live
table this purge deletes only the untagged legacy rows and leaves anything the current
code wrote alone.

Archive: data_point_series_archive holds one daily aggregate per (source, series, day)
and carries no per-row marker, so legacy and post-fix buckets cannot be told apart
there. Before this fix the only writer of Health API energy was total-calories, so
every archived Health API energy bucket is legacy by construction — the script deletes
them all. Run it right after deploying the fix and BEFORE re-running a historical sync;
if archival already ran over re-synced data, pass --skip-archive (or re-sync again
afterwards — the archive rebuilds itself from the live rows on the next archival run).

Scoped to source='google_health_api': Health Connect SDK rows carry the reporting app
as source, map active calories correctly, and must not be touched. Both the pre- and
post-split cloud provider slugs are matched, so the order against the provider split
migration does not matter.

Deletes are batched (--batch, default 50000) and committed per batch, so no single
long-running transaction holds row locks or produces one WAL burst. Idempotent: once
purged, no untagged rows match, so re-runs are no-ops. Not wired into startup — the
purge removes data that only a historical re-sync can bring back, and not every
deployment can afford one, so the operator decides when to run it. Re-run a historical
sync afterwards to backfill active and basal energy over the deleted range.

Usage (inside Docker):
    docker compose exec app uv run python scripts/data_migrations/purge_google_total_calories_energy.py --dry-run
    docker compose exec app uv run python scripts/data_migrations/purge_google_total_calories_energy.py
    docker compose exec app uv run python scripts/data_migrations/purge_google_total_calories_energy.py --skip-archive
"""

import argparse
from typing import TypedDict
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import TextClause

from app.database import SessionLocal
from app.schemas.enums import SeriesType, get_series_type_id

# Both spellings: the cloud path is google_health since the provider split, but this may
# run against a database the split has not reached yet. source pins it to the cloud path
# either way, so accepting both costs nothing and keeps the purge order-independent.
PROVIDERS = ("google_health", "google")
SOURCE = "google_health_api"
SERIES_ID = get_series_type_id(SeriesType.active_energy)
DEFAULT_BATCH = 50_000

_SOURCE_IDS = text("SELECT id FROM data_source WHERE provider = ANY(:providers) AND source = :source")

# Live rows: legacy = untagged. The predicate matches the leading columns of
# uq_data_point_series_source_type_time, so each batch is an index range scan.
_LIVE_PREDICATE = """
    data_source_id = ANY(:sources)
    AND series_type_definition_id = :series
    AND external_id IS NULL
"""
_LIVE_COUNT = text(f"SELECT COUNT(*) FROM data_point_series WHERE {_LIVE_PREDICATE}")
_LIVE_DELETE = text(f"""
    WITH batch AS (
        SELECT id FROM data_point_series WHERE {_LIVE_PREDICATE} LIMIT :batch
    )
    DELETE FROM data_point_series d USING batch WHERE d.id = batch.id
""")

# Archive rows: no marker, every Health API energy bucket is legacy (see module docstring).
_ARCHIVE_PREDICATE = """
    data_source_id = ANY(:sources)
    AND series_type_definition_id = :series
"""
_ARCHIVE_COUNT = text(f"SELECT COUNT(*) FROM data_point_series_archive WHERE {_ARCHIVE_PREDICATE}")
_ARCHIVE_DELETE = text(f"""
    WITH batch AS (
        SELECT id FROM data_point_series_archive WHERE {_ARCHIVE_PREDICATE} LIMIT :batch
    )
    DELETE FROM data_point_series_archive d USING batch WHERE d.id = batch.id
""")


class PurgeResult(TypedDict):
    series_deleted: int
    archive_deleted: int


def _delete_batched(db: Session, stmt: TextClause, params: dict, batch: int) -> int:
    """Run *stmt* until a batch comes back short, committing after each one."""
    total = 0
    while True:
        n = db.execute(stmt, {**params, "batch": batch}).rowcount  # ty: ignore[unresolved-attribute]
        db.commit()
        total += n
        if n < batch:
            return total


def run(db: Session, dry_run: bool, batch: int = DEFAULT_BATCH, include_archive: bool = True) -> PurgeResult:
    if batch <= 0:
        raise ValueError(f"batch must be a positive integer, got {batch}")

    sources: list[UUID] = list(db.execute(_SOURCE_IDS, {"providers": list(PROVIDERS), "source": SOURCE}).scalars())
    if not sources:
        print("No Google Health API data sources; nothing to purge.")
        return PurgeResult(series_deleted=0, archive_deleted=0)

    params = {"sources": sources, "series": SERIES_ID}
    stale_live = db.execute(_LIVE_COUNT, params).scalar_one()
    stale_archive = db.execute(_ARCHIVE_COUNT, params).scalar_one() if include_archive else 0
    if not stale_live and not stale_archive:
        print("No untagged Google Health API energy rows; nothing to purge.")
        return PurgeResult(series_deleted=0, archive_deleted=0)
    prefix = "[dry-run] would delete" if dry_run else "Deleting"
    print(f"{prefix} {stale_live} untagged Google Health API energy row(s) written from total-calories.")
    if include_archive:
        print(f"{prefix} {stale_archive} archived Google Health API energy bucket(s).")
    else:
        print("Skipping data_point_series_archive (--skip-archive).")
    if dry_run:
        return PurgeResult(series_deleted=stale_live, archive_deleted=stale_archive)

    series_deleted = _delete_batched(db, _LIVE_DELETE, params, batch) if stale_live else 0
    archive_deleted = _delete_batched(db, _ARCHIVE_DELETE, params, batch) if stale_archive else 0
    print(f"Deleted {series_deleted} live row(s) and {archive_deleted} archive bucket(s).")
    return PurgeResult(series_deleted=series_deleted, archive_deleted=archive_deleted)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="report what would be deleted and exit")
    parser.add_argument(
        "--batch", type=int, default=DEFAULT_BATCH, help=f"rows per DELETE batch (default {DEFAULT_BATCH})"
    )
    parser.add_argument(
        "--skip-archive",
        action="store_true",
        help="leave data_point_series_archive alone (archival already ran over re-synced data)",
    )
    args = parser.parse_args()
    if args.batch <= 0:
        parser.error("--batch must be a positive integer")
    with SessionLocal() as db:
        run(db, args.dry_run, batch=args.batch, include_archive=not args.skip_archive)


if __name__ == "__main__":
    main()
