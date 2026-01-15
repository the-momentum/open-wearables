import sys
import os
from datetime import datetime, timedelta, timezone
from uuid import UUID

# Add backend directory to python path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from app.database import SessionLocal
from app.services.providers.factory import ProviderFactory
from app.models import EventRecord, ExternalDeviceMapping
from sqlalchemy import select

# Configuration
USER_ID = UUID("3f708058-407a-4809-ab84-c84b50fd2e6b")
PROVIDER = "ultrahuman"


def main():
    print(f"--- Verifying Ultrahuman Integration for User {USER_ID} ---")

    # Use synchronous session
    db = SessionLocal()
    try:
        # 1. Initialize Provider
        factory = ProviderFactory()
        strategy = factory.get_provider(PROVIDER)

        if not strategy.data_247:
            print("Error: Ultrahuman provider does not support 24/7 data.")
            return

        # 2. Define sync range (last 7 days)
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=7)

        print(f"\nSyncing data from {start_time.date()} to {end_time.date()}...")

        # 3. Run Sync
        provider_impl = strategy.data_247

        try:
            results = provider_impl.load_and_save_all(db, USER_ID, start_time=start_time, end_time=end_time)
            print("\nSync Results:")
            print(results)

            db.commit()

        except Exception as e:
            print(f"\nSync Failed: {e}")
            import traceback

            traceback.print_exc()
            return

        # 4. Verify Database
        print("\n--- Verifying Database Records ---")

        # Check Sleep Records using Join
        records = (
            db.query(EventRecord)
            .join(ExternalDeviceMapping)
            .filter(
                ExternalDeviceMapping.user_id == USER_ID,
                ExternalDeviceMapping.provider_name == PROVIDER,
                EventRecord.category == "sleep",
                EventRecord.start_datetime >= start_time,
            )
            .order_by(EventRecord.start_datetime.desc())
            .all()
        )

        print(f"\nFound {len(records)} sleep records in DB:")
        for record in records:
            duration_str = f"{record.duration_seconds // 60}m" if record.duration_seconds else "N/A"
            print(f"- {record.start_datetime} to {record.end_datetime} | Duration: {duration_str}")

        if not records:
            print("\nWARNING: No sleep records found in DB after sync!")
        else:
            print("\nSUCCESS: Sleep records successfully synced and saved.")

    finally:
        db.close()


if __name__ == "__main__":
    main()
