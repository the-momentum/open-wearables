#!/usr/bin/env python3
"""Set the sleep stages of SDK nights without light/deep/rem segments to NULL.

SDK sleep imports used to save 0 min for stages a night never reported. A night qualifies when
deep, light and REM are all 0 and its hypnogram has no light/deep/rem segment (or there is none);
a 0 awake time is cleared too unless the hypnogram has an awake segment. Covers the SDK providers
and ``unknown``, where Apple XML sleep imports from writers without "apple" in their name land.
Cloud providers are left alone: without the raw payload a zero they reported cannot be told apart
from a missing value.

Runs once per instance (``data_migration``): one pass over the integer columns collects the
candidates, then committed batches check the hypnograms of only those rows.

Usage (inside Docker):
    docker compose exec app uv run python scripts/data_migrations/clear_sdk_unreported_sleep_stages.py --dry-run
    docker compose exec app uv run python scripts/data_migrations/clear_sdk_unreported_sleep_stages.py
"""

import argparse

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.constants.sdk_providers import SDK_PROVIDERS
from app.database import engine
from app.schemas.enums import ProviderName
from app.services.data_migration_service import data_migration_service

_BATCH_SIZE = 10_000

_PROVIDERS = sorted(SDK_PROVIDERS | {ProviderName.UNKNOWN.value})

_ZERO_PHASES = "sd.sleep_deep_minutes = 0 AND sd.sleep_light_minutes = 0 AND sd.sleep_rem_minutes = 0"
# Hypnograms may be a JSON scalar (legacy Garmin rows), so only arrays are searched
_NO_PHASE_SEGMENTS = """(
    sd.sleep_stages IS NULL
    OR jsonb_typeof(sd.sleep_stages) <> 'array'
    OR NOT jsonb_path_exists(
        sd.sleep_stages, '$[*] ? (@.stage == "light" || @.stage == "deep" || @.stage == "rem")'
    )
)"""
_HAS_AWAKE_SEGMENT = """COALESCE(
    jsonb_typeof(sd.sleep_stages) = 'array' AND jsonb_path_exists(sd.sleep_stages, '$[*] ? (@.stage == "awake")'),
    false
)"""

# Only integer columns, so collecting never detoasts a hypnogram
_ZEROS = f"""
    SELECT sd.record_id
    FROM sleep_details sd
    JOIN event_record e ON e.id = sd.record_id
    JOIN data_source ds ON ds.id = e.data_source_id
    WHERE {_ZERO_PHASES} AND ds.provider = ANY(:providers)
"""
_COUNT = text(f"""
    SELECT count(*)
    FROM sleep_details sd
    WHERE sd.record_id IN ({_ZEROS}) AND {_NO_PHASE_SEGMENTS}
""")
# Collected in one pass into a session temp table, so batches cost a key lookup each and not a
# rescan of sleep_details; the session must stay on one connection (see main)
_DROP = text("DROP TABLE IF EXISTS sdk_zero_sleep_stages")
_COLLECT = text(f"CREATE TEMP TABLE sdk_zero_sleep_stages AS {_ZEROS}")
_INDEX = text("CREATE INDEX ON sdk_zero_sleep_stages (record_id)")
_NEXT = text("SELECT record_id FROM sdk_zero_sleep_stages ORDER BY record_id LIMIT :batch_size")
# Rechecks the zeros: a sync may have rewritten the night since it was collected
_CLEAR = text(f"""
    UPDATE sleep_details sd
    SET sleep_deep_minutes = NULL,
        sleep_light_minutes = NULL,
        sleep_rem_minutes = NULL,
        sleep_awake_minutes = CASE
            WHEN sd.sleep_awake_minutes = 0 AND NOT {_HAS_AWAKE_SEGMENT} THEN NULL
            ELSE sd.sleep_awake_minutes
        END
    WHERE sd.record_id = ANY(:ids) AND {_ZERO_PHASES} AND {_NO_PHASE_SEGMENTS}
""")
_FORGET = text("DELETE FROM sdk_zero_sleep_stages WHERE record_id = ANY(:ids)")


def clear_sdk_unreported_sleep_stages(db: Session, *, dry_run: bool) -> int:
    """Commits per batch, so an interrupted run keeps what it cleared."""
    params = {"providers": _PROVIDERS}
    if dry_run:
        found = db.execute(_COUNT, params).scalar() or 0
        print(f"Would clear unreported sleep stages on {found} SDK night(s).\n\nDry run — no changes made.")
        return found

    db.execute(_DROP)
    db.execute(_COLLECT, params)
    db.execute(_INDEX)
    db.commit()
    cleared = 0
    while ids := list(db.execute(_NEXT, {"batch_size": _BATCH_SIZE}).scalars()):
        cleared += db.execute(_CLEAR, {"ids": ids}).rowcount  # ty: ignore[unresolved-attribute]
        db.execute(_FORGET, {"ids": ids})
        db.commit()
    db.execute(_DROP)
    db.commit()
    print(f"Cleared unreported sleep stages on {cleared} SDK night(s).")
    return cleared


def _migrate(db: Session, dry_run: bool) -> bool:
    clear_sdk_unreported_sleep_stages(db, dry_run=dry_run)
    return not dry_run


def main(dry_run: bool) -> None:
    with engine.connect() as connection, Session(bind=connection) as db:
        data_migration_service.run(
            db, "clear_sdk_unreported_sleep_stages", lambda: _migrate(db, dry_run), dry_run=dry_run
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Preview affected rows without modifying data")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
