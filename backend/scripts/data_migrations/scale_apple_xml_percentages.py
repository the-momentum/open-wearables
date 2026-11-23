#!/usr/bin/env python3
"""Scale Apple Health XML percentages stored as 0-1 fractions to 0-100.

HealthKit exports its "%" values as fractions (0.97 for 97% blood oxygen), and the XML import stored
them as they came, while percent series hold 0-100. The import now scales them; this scales the
stored ones: the percent series HealthKit reports in "%", from Apple Health XML sources, at most 1.
Every value the import stored before is a fraction, so the bound only keeps a value already scaled
from being scaled twice; a walking percentage under 1% imported by the fixed code before this has
run would be, the one case it can't tell apart.

The changed days are queued for the rollup. Runs once per instance (data_migration), in one
transaction with the record of the run: scaling is not idempotent, so a run that fails commits
nothing and the next startup tries again.

Usage (inside Docker):
    docker compose exec app uv run python scripts/data_migrations/scale_apple_xml_percentages.py --dry-run
    docker compose exec app uv run python scripts/data_migrations/scale_apple_xml_percentages.py
"""

import argparse

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.constants.series_types.sdk.metric_types import APPLE_METRIC_TYPE_TO_SERIES_TYPE
from app.database import engine
from app.integrations.rollup_queue import mark_dirty_days
from app.repositories.local_day import sample_day_sql
from app.schemas.enums import get_series_type_id, get_series_type_unit
from app.services.data_migration_service import data_migration_service

XML_SOURCE = "apple_health_xml"

PERCENT_TYPE_IDS = sorted(
    {
        get_series_type_id(series_type)
        for series_type in APPLE_METRIC_TYPE_TO_SERIES_TYPE.values()
        if get_series_type_unit(series_type) == "percent"
    }
)

_FRACTIONS = """
    s.data_source_id IN (SELECT id FROM data_source WHERE source = :source)
    AND s.series_type_definition_id = ANY(:types)
    AND s.value <= 1
"""
_COUNT = text(f"SELECT count(*) FROM series_sample s WHERE {_FRACTIONS}")
_SCALE = text(f"""
    WITH scaled AS (
        UPDATE series_sample s SET value = s.value * 100
        WHERE {_FRACTIONS}
        RETURNING s.data_source_id, s.recorded_at, s.zone_offset
    )
    SELECT data_source_id, {sample_day_sql("scaled")} AS day, count(*) AS samples
    FROM scaled
    GROUP BY 1, 2
""")


def scale_apple_xml_percentages(db: Session, *, dry_run: bool) -> int:
    """Does not commit; the caller owns the transaction. Returns the number of samples scaled."""
    params = {"source": XML_SOURCE, "types": PERCENT_TYPE_IDS}
    if dry_run:
        found = db.execute(_COUNT, params).scalar() or 0
        print(f"Would scale {found} Apple Health XML percentage(s).\n\nDry run: no changes made.")
        return found
    days = db.execute(_SCALE, params).all()
    mark_dirty_days(db, [(row.data_source_id, row.day) for row in days])
    scaled = sum(row.samples for row in days)
    print(f"Scaled {scaled} Apple Health XML percentage(s) on {len(days)} day(s).")
    return scaled


def _migrate(db: Session, dry_run: bool) -> bool:
    scale_apple_xml_percentages(db, dry_run=dry_run)
    return not dry_run


def main(dry_run: bool) -> None:
    with engine.connect() as connection, Session(bind=connection) as db:
        data_migration_service.run(db, "scale_apple_xml_percentages", lambda: _migrate(db, dry_run), dry_run=dry_run)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Preview affected rows without modifying data")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
