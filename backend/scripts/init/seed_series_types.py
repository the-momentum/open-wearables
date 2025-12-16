#!/usr/bin/env python3
"""Initialize series_type_definition table with all available series types."""

from app.database import SessionLocal
from app.models import SeriesTypeDefinition
from app.schemas.series_types import SERIES_TYPE_DEFINITIONS


def seed_series_types() -> None:
    """Ensure all series types from SERIES_TYPE_DEFINITIONS exist in database."""
    with SessionLocal() as db:
        for type_id, series_type, unit in SERIES_TYPE_DEFINITIONS:
            # Check if this series type already exists
            existing = db.query(SeriesTypeDefinition).filter(SeriesTypeDefinition.id == type_id).first()

            if existing:
                # Update if code or unit changed
                if existing.code != series_type.value or existing.unit != unit:
                    existing.code = series_type.value
                    existing.unit = unit
                    print(f"✓ Updated series type {type_id}: {series_type.value} ({unit})")
                else:
                    print(f"  Series type {type_id}: {series_type.value} already exists, skipping.")
            else:
                # Create new series type
                new_type = SeriesTypeDefinition(
                    id=type_id,
                    code=series_type.value,
                    unit=unit,
                )
                db.add(new_type)
                print(f"✓ Created series type {type_id}: {series_type.value} ({unit})")

        db.commit()
        print(f"✓ Series type definitions initialized: {len(SERIES_TYPE_DEFINITIONS)} types")


if __name__ == "__main__":
    seed_series_types()
