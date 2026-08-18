#!/usr/bin/env python3
"""Null workout heart_rate_min values that actually hold the average heart rate.

Garmin activity payloads carry no minimum heart rate, but until PR #1121 the
Garmin workout normalizer wrote heart_rate_min = int(heart_rate_avg). Polar had
the same bug until PR #1041. Both providers therefore have workout_details rows
where heart_rate_min is a copy of the average, not a minimum.

Selection is deliberately narrow:
- Garmin averages are integers in the API, so every bogus row satisfies
  heart_rate_min = heart_rate_avg exactly. Exact equality also protects
  SDK-imported rows that were attributed to provider 'garmin' via source
  inference but carry a genuine HealthKit minimum.
- Polar averages may be fractional, so bogus rows satisfy
  heart_rate_min = floor(heart_rate_avg) (the int() truncation).

heart_rate_avg and heart_rate_max are genuine and stay untouched. Rows written
after the fixes have heart_rate_min NULL and are not matched.

Usage (inside Docker):
    docker compose exec app uv run python scripts/data_migrations/null_bogus_workout_heart_rate_min.py --dry-run
    docker compose exec app uv run python scripts/data_migrations/null_bogus_workout_heart_rate_min.py
"""

import argparse

from sqlalchemy import text

from app.database import SessionLocal

_PREDICATE = """
    wd.heart_rate_min IS NOT NULL
    AND wd.heart_rate_avg IS NOT NULL
    AND (
        (ds.provider = 'garmin' AND wd.heart_rate_min = wd.heart_rate_avg)
        OR (ds.provider = 'polar' AND wd.heart_rate_min = FLOOR(wd.heart_rate_avg))
    )
    AND er.category = 'workout'
"""

_AFFECTED_COUNT = text(f"""
    SELECT COUNT(*)
    FROM workout_details wd
    JOIN event_record er ON er.id = wd.record_id
    JOIN data_source ds ON ds.id = er.data_source_id
    WHERE {_PREDICATE}
""")

_SAMPLE_ROWS = text(f"""
    SELECT wd.record_id, ds.provider, wd.heart_rate_min, wd.heart_rate_avg, wd.heart_rate_max, er.start_datetime
    FROM workout_details wd
    JOIN event_record er ON er.id = wd.record_id
    JOIN data_source ds ON ds.id = er.data_source_id
    WHERE {_PREDICATE}
    ORDER BY er.start_datetime DESC
    LIMIT 20
""")

_UPDATE = text(f"""
    UPDATE workout_details wd
    SET heart_rate_min = NULL
    FROM event_record er
    JOIN data_source ds ON ds.id = er.data_source_id
    WHERE er.id = wd.record_id
      AND {_PREDICATE}
""")


def main(dry_run: bool) -> None:
    with SessionLocal() as db:
        count = db.execute(_AFFECTED_COUNT).scalar()

        if count == 0:
            print("No affected rows - nothing to do.")
            return

        print(f"Workout rows with heart_rate_min copied from the average: {count}")

        rows = db.execute(_SAMPLE_ROWS).fetchall()
        print(f"\n{'Record ID':<38} {'Provider':<10} {'Min':>5} {'Avg':>8} {'Max':>5}  Start")
        print("-" * 90)
        for row in rows:
            hr_max = row.heart_rate_max if row.heart_rate_max is not None else "-"
            print(
                f"{row.record_id!s:<38} {row.provider:<10} {row.heart_rate_min:>5} "
                f"{row.heart_rate_avg:>8.2f} {hr_max:>5}  {row.start_datetime}"
            )
        if count > 20:
            print(f"  ... and {count - 20} more")

        if dry_run:
            print("\nDry run - no changes made.")
            return

        result = db.execute(_UPDATE)
        db.commit()
        print(f"\nUpdated {result.rowcount} row(s).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Preview affected rows without updating")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
