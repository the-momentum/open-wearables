#!/usr/bin/env python3
"""Re-resolve ``data_source.device_type`` for rows stored as NULL or ``other``.

Device type inference (``app/constants/devices_map/device_types.py``) gained provider
defaults, Samsung model codes and more product keywords. Rows written before that stay
NULL or ``other`` until their owner syncs again; this script re-runs the inference on
the stored model and source and applies the same upgrade-only rule as ingestion, so a
concrete type is never overwritten.

The SDK-reported device type is not stored, so rows that only it could resolve (e.g.
Health Connect data without a model) are left for the next sync to fill.

Idempotent: upgraded rows become concrete and drop out of the filter, so re-runs only
re-check the remaining NULL/``other`` rows. Safe to run on every startup; newly added
mappings are picked up automatically.

Usage (inside Docker):
    docker compose exec app uv run python scripts/data_migrations/backfill_device_types.py --dry-run
    docker compose exec app uv run python scripts/data_migrations/backfill_device_types.py
"""

import argparse
from collections import Counter

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.constants.devices_map import infer_device_type
from app.database import SessionLocal
from app.models import DataSource
from app.repositories.data_source_repository import DataSourceRepository
from app.schemas.enums import DeviceType, ProviderName


def backfill_device_types(db: Session, *, dry_run: bool) -> Counter[str]:
    """Upgrade NULL/``other`` device types. Does not commit — the caller owns the transaction.

    Returns a count of upgrades keyed by ``"<provider>: <old> -> <new>"``.
    """
    rows = (
        db.query(DataSource)
        .filter(or_(DataSource.device_type.is_(None), DataSource.device_type == DeviceType.OTHER.value))
        .all()
    )
    changes: Counter[str] = Counter()
    for ds in rows:
        try:
            provider = ProviderName(ds.provider)
        except ValueError:
            continue
        resolved = infer_device_type(provider, ds.device_model, ds.original_source_name or ds.source)
        device_type = DataSourceRepository._upgraded_device_type(ds.device_type, resolved)
        if not device_type:
            continue
        changes[f"{provider.value}: {ds.device_type} -> {device_type.value}"] += 1
        if not dry_run:
            ds.device_type = device_type.value

    verb = "would upgrade" if dry_run else "upgraded"
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
            print("Nothing to do — no device types to upgrade.")
            return
        db.commit()
        print("Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Preview affected rows without modifying data")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
