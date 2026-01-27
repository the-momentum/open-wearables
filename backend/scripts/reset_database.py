"""
Script to truncate all tables in the database.
This will delete all data but keep the schema intact.
"""

import sys

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import BaseDbModel, SessionLocal


def truncate_all_tables() -> None:
    """Truncate all tables in the database."""
    db: Session = SessionLocal()
    try:
        # Disable foreign key checks temporarily
        db.execute(text("SET session_replication_role = 'replica';"))

        # Get all table names
        inspector = BaseDbModel.metadata
        table_names = [table.name for table in inspector.sorted_tables]

        # Truncate all tables
        for table_name in table_names:
            db.execute(text(f'TRUNCATE TABLE "{table_name}" CASCADE;'))
            print(f"✓ Truncated table: {table_name}")

        # Re-enable foreign key checks
        db.execute(text("SET session_replication_role = 'origin';"))

        db.commit()
        print("\n✓ Database truncated successfully!")
    except Exception as e:
        db.rollback()
        print(f"\n✗ Error truncating database: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    print("⚠️  WARNING: This will delete ALL data from the database!")
    response = input("Are you sure you want to continue? (yes/no): ")

    if response.lower() != "yes":
        print("Operation cancelled.")
        sys.exit(0)

    truncate_all_tables()
