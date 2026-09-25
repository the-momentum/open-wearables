#!/usr/bin/env python3
"""One-off: re-resolve ``data_source.device_type`` for rows written before the new mappings.

Applies the same rule as live sync (``DataSourceRepository.next_device_type``): cloud-provider
rows are recomputed outright, which also corrects types the old keywords got wrong (e.g. Garmin
Index BPM stored as scale); SDK-provider rows only upgrade NULL/``other`` to a concrete type.
Later mapping changes reach existing rows on their next sync, so this only needs to run once.

Idempotent: a second run finds nothing to change. Safe to run on every startup until removed.

Usage (inside Docker):
    docker compose exec app uv run python scripts/data_migrations/backfill_device_types.py --dry-run
    docker compose exec app uv run python scripts/data_migrations/backfill_device_types.py
"""

import argparse
from collections import Counter

from sqlalchemy.orm import Session

from app.constants.devices_map import infer_device_type
from app.database import SessionLocal
from app.models import DataSource
from app.repositories.data_source_repository import DataSourceRepository
from app.schemas.enums import ProviderName


def backfill_device_types(db: Session, *, dry_run: bool) -> Counter[str]:
    """Re-resolve device types. Does not commit — the caller owns the transaction.

    Returns a count of changes keyed by ``"<provider>: <old> -> <new>"``.
    """
    changes: Counter[str] = Counter()
    for ds in db.query(DataSource).all():
        try:
            provider = ProviderName(ds.provider)
        except ValueError:
            continue
        resolved = infer_device_type(provider, ds.device_model, ds.original_source_name or ds.source)
        new_type = DataSourceRepository.next_device_type(provider, ds.device_type, resolved)
        if new_type == ds.device_type:
            continue
        changes[f"{provider.value}: {ds.device_type} -> {new_type}"] += 1
        if not dry_run:
            ds.device_type = new_type

    verb = "would change" if dry_run else "changed"
    for change, count in sorted(changes.items()):
        print(f"{change:<40} {verb} {count} row(s)")
    if dry_run:
        print("\nDry run — no changes made.")
    return changes


def main(dry_run: bool) -> None:
    with SessionLocal() as db:
        changes = backfill_device_types(db, dry_run=dry_run)
        if dry_run:
            return
        if not changes:
            print("Nothing to do — all device types are current.")
            return
        db.commit()
        print("Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Preview affected rows without modifying data")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
