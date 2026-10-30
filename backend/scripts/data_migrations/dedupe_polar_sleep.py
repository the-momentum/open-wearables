#!/usr/bin/env python3
"""Remove the copies that Polar sleep re-syncs appended to a night (#1539).

Polar sleep had no external_id, so each re-sync of a night still inside the sync window
went through the adjacent-session merge instead of replacing the session. The merge added
the night again: another copy of the stage timeline in sleep_details.sleep_stages, the time
in bed again, and, for a night without stages, its sleep and stage minutes again (a night
with stages has those recomputed from the merged timeline, so they are not inflated).
Polar sleep now carries external_id "sleep-<date>"; this script repairs the nights stored
before that:

- keeps one copy of each stage interval and sets sleep_time_in_bed_minutes back to the
  session length, which is what Polar sleep stores it as;
- for a night without stages, divides the sleep and stage minutes by the number of copies,
  read from how many times the session length its time in bed holds;
- sets external_id to "sleep-<local wake-up date>", the date Polar keys the night by, so a
  later re-sync replaces the night instead of merging into it. zone_offset isn't stored for
  Polar sleep, so the local date uses the offset of the stage timestamps. A night without
  stages has no offset to read, so it keeps no id: a re-sync of the night replaces it and
  gives it Polar's id, moved or not.

Not changed: internal sleep scores of the repaired nights, and stage timelines whose copies
differ (Polar moved the night between syncs), which are not exact duplicates.

The ids of the Polar nights are collected first, through the data source index, so the run
reads only Polar rows and not the whole event_record table. The nights are then read in batches
and each batch is committed. A night whose data can't be read is skipped and reported to Sentry,
so one bad row doesn't stop the rest. The run is still recorded: a row that can't be read now
won't be readable on the next startup either, and retrying would repeat the whole run each time.

Idempotent: a repaired night no longer matches or needs no change, so re-runs are no-ops.
Loading every Polar night to find there's nothing left is not free, so it runs once per
instance through data_migration_service. A copy an old pod appends during a rolling deploy, or
a night it writes without an id, needs no second run: the next re-sync of that night replaces
it.

Usage (inside Docker), with --dry-run to preview without changes:
    docker compose exec app uv run python scripts/data_migrations/dedupe_polar_sleep.py
"""

import argparse
from datetime import datetime, timezone
from logging import getLogger
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import engine
from app.models import DataSource, EventRecord, SleepDetails
from app.schemas.enums import ProviderName
from app.services.data_migration_service import data_migration_service
from app.utils.sentry_helpers import log_and_capture_error

logger = getLogger(__name__)

BATCH_SIZE = 200
MINUTE_FIELDS = (
    "sleep_total_duration_minutes",
    "sleep_deep_minutes",
    "sleep_light_minutes",
    "sleep_rem_minutes",
    "sleep_awake_minutes",
)


def _repaired_values(record: EventRecord, detail: SleepDetails) -> tuple[dict[str, Any], str | None]:
    """The detail fields to overwrite (empty when the night wasn't appended to) and the external_id to set, if any."""
    # A night without stages can hold a JSON null rather than a list.
    stages = detail.sleep_stages if isinstance(detail.sleep_stages, list) else []
    session_minutes = int((record.end_datetime - record.start_datetime).total_seconds()) // 60
    in_bed = detail.sleep_time_in_bed_minutes or 0
    unique_stages = sorted(
        {(s["stage"], s["start_time"], s["end_time"]): s for s in stages}.values(),
        key=lambda s: datetime.fromisoformat(s["start_time"]),
    )

    fields: dict[str, Any] = {}
    if len(unique_stages) < len(stages) or in_bed > session_minutes:
        fields["sleep_time_in_bed_minutes"] = session_minutes
        if stages:
            fields["sleep_stages"] = unique_stages
        elif session_minutes > 0 and (copies := round(in_bed / session_minutes)) > 1:
            for name in MINUTE_FIELDS:
                if (value := getattr(detail, name)) is not None:
                    fields[name] = round(value / copies)

    # Without stages there is no local offset to read the wake-up date with; a re-sync gives the id
    if not stages:
        return fields, None
    offset = datetime.fromisoformat(stages[0]["start_time"]).tzinfo
    wake_up = record.end_datetime.astimezone(offset or timezone.utc)
    return fields, f"sleep-{wake_up.date().isoformat()}"


def dedupe_polar_sleep(db: Session, *, dry_run: bool, batch_size: int = BATCH_SIZE) -> dict[str, int]:
    """Repair the Polar nights a re-sync appended to, committing after each batch unless dry_run."""
    counts = {"sessions_repaired": 0, "external_ids_set": 0, "sessions_skipped": 0}
    polar_nights = (
        select(EventRecord.id)
        .join(DataSource, DataSource.id == EventRecord.data_source_id)
        # Nights written since the fix carry an external_id and are replaced on re-sync
        .where(
            DataSource.provider == ProviderName.POLAR,
            EventRecord.category == "sleep",
            EventRecord.external_id.is_(None),
        )
        .order_by(EventRecord.id)
    )
    ids = list(db.scalars(polar_nights))
    for start in range(0, len(ids), batch_size):
        batch = (
            db.query(EventRecord, SleepDetails)
            .join(SleepDetails, SleepDetails.record_id == EventRecord.id)
            .filter(EventRecord.id.in_(ids[start : start + batch_size]))
            .all()
        )

        for record, detail in batch:
            try:
                fields, external_id = _repaired_values(record, detail)
            except (KeyError, TypeError, ValueError) as exc:
                counts["sessions_skipped"] += 1
                print(f"Skipped unreadable Polar sleep {record.id}")
                log_and_capture_error(
                    exc, logger, "Skipped unreadable Polar sleep", extra={"event_record_id": str(record.id)}
                )
                continue
            counts["sessions_repaired"] += bool(fields)
            counts["external_ids_set"] += external_id is not None
            if not dry_run:
                for name, value in fields.items():
                    setattr(detail, name, value)
                if external_id is not None:
                    record.external_id = external_id

        if not dry_run:
            db.commit()
        # Keeps memory flat: a night can hold thousands of stage copies
        for record, detail in batch:
            db.expunge(record)
            db.expunge(detail)

    verb = "Would repair" if dry_run else "Repaired"
    print(
        f"{verb} {counts['sessions_repaired']} Polar sleep session(s) and set {counts['external_ids_set']} "
        f"external id(s); skipped {counts['sessions_skipped']} unreadable session(s)"
    )
    if dry_run:
        print("\nDry run - no changes made.")
    return counts


def _migrate(db: Session, dry_run: bool) -> bool:
    dedupe_polar_sleep(db, dry_run=dry_run)
    if dry_run:
        return False
    print("Done.")
    return True


def main(dry_run: bool) -> None:
    with engine.connect() as connection, Session(bind=connection) as db:
        data_migration_service.run(db, "dedupe_polar_sleep", lambda: _migrate(db, dry_run), dry_run=dry_run)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Preview affected rows without modifying data")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
