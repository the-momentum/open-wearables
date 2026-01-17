"""
Automated verification script for Ultrahuman integration.

This script runs comprehensive checks on the Ultrahuman integration
and provides console output with test results.

Usage:
    cd backend
    uv run python scripts/verify_ultrahuman_integration.py

Requirements:
    - Set valid ULTRAHUMAN_CLIENT_ID, ULTRAHUMAN_CLIENT_SECRET in config/.env
    - At least one user with active Ultrahuman connection in database
"""

import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.getcwd()))

from app.database import SessionLocal
from app.models import DataPointSeries, EventRecord, ExternalDeviceMapping, SleepDetails, UserConnection
from app.services.providers.factory import ProviderFactory


class Colors:
    """ANSI color codes for console output."""

    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"


def print_header(text: str) -> None:
    """Print a header."""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{text}{Colors.ENDC}")
    print("=" * len(text))


def print_success(text: str) -> None:
    """Print a success message."""
    print(f"  {Colors.OKGREEN}✓{Colors.ENDC} {text}")


def print_failure(text: str) -> None:
    """Print a failure message."""
    print(f"  {Colors.FAIL}✗{Colors.ENDC} {text}")


def print_warning(text: str) -> None:
    """Print a warning message."""
    print(f"  {Colors.WARNING}⚠{Colors.ENDC} {text}")


def print_info(text: str) -> None:
    """Print an info message."""
    print(f"  {Colors.OKCYAN}ℹ{Colors.ENDC} {text}")


def check_provider_registered() -> bool:
    """Check if Ultrahuman is registered in ProviderFactory."""
    print_header("1. Provider Registration Check")

    try:
        factory = ProviderFactory()
        strategy = factory.get_provider("ultrahuman")

        if strategy is None:
            print_failure("Ultrahuman provider not found in factory")
            return False

        print_success("Ultrahuman provider registered in factory")
        print_info(f"   Provider name: {strategy.name}")
        print_info(f"   API base URL: {strategy.api_base_url}")

        if not strategy.data_247:
            print_failure("Ultrahuman provider does not have data_247 component")
            return False
        print_success("data_247 component present")

        if not strategy.oauth:
            print_failure("Ultrahuman provider does not have OAuth component")
            return False
        print_success("OAuth component present")

        return True

    except Exception as e:
        print_failure(f"Failed to check provider registration: {e}")
        return False


def check_oauth_configuration() -> bool:
    """Check Ultrahuman OAuth configuration."""
    print_header("2. OAuth Configuration Check")

    from app.config import settings

    if not settings.ultrahuman_client_id:
        print_warning("ULTRAHUMAN_CLIENT_ID not set")
        return False
    print_success("ULTRAHUMAN_CLIENT_ID is set")

    if not settings.ultrahuman_client_secret:
        print_warning("ULTRAHUMAN_CLIENT_SECRET not set")
        return False
    print_success("ULTRAHUMAN_CLIENT_SECRET is set")

    if not settings.ultrahuman_redirect_uri:
        print_warning("ULTRAHUMAN_REDIRECT_URI not set")
        return False
    print_success(f"ULTRAHUMAN_REDIRECT_URI is set: {settings.ultrahuman_redirect_uri}")

    if settings.ultrahuman_redirect_uri.startswith("http://"):
        print_warning("ULTRAHUMAN_REDIRECT_URI uses HTTP (Ultrahuman requires HTTPS)")

    return True


def check_connected_users() -> bool:
    """Check for Ultrahuman connected users."""
    print_header("3. Connected Users Check")

    db = SessionLocal()
    try:
        connections = db.query(UserConnection).filter(UserConnection.provider == "ultrahuman").all()

        if not connections:
            print_warning("No Ultrahuman connected users found")
            return False

        print_success(f"Found {len(connections)} Ultrahuman connected user(s)")

        for conn in connections:
            print_info(f"   User ID: {conn.user_id}")
            print_info(f"   Status: {conn.status}")
            print_info(f"   Last synced: {conn.last_synced_at}")

        return True

    except Exception as e:
        print_failure(f"Failed to check connected users: {e}")
        return False
    finally:
        db.close()


def check_database_schema() -> bool:
    """Check database schema for Ultrahuman-related tables."""
    print_header("4. Database Schema Check")

    db = SessionLocal()
    try:
        if db.query(EventRecord).first() is None:
            print_warning("event_record table is empty")
        else:
            print_success("event_record table exists")

        if db.query(SleepDetails).first() is None:
            print_warning("sleep_details table is empty")
        else:
            print_success("sleep_details table exists")

        if db.query(DataPointSeries).first() is None:
            print_warning("data_point_series table is empty")
        else:
            print_success("data_point_series table exists")

        if db.query(ExternalDeviceMapping).first() is None:
            print_warning("external_device_mapping table is empty")
        else:
            print_success("external_device_mapping table exists")

        return True

    except Exception as e:
        print_failure(f"Failed to check database schema: {e}")
        return False
    finally:
        db.close()


def run_test_sync() -> bool:
    """Run a test sync for the first Ultrahuman user."""
    print_header("5. Test Sync Execution")

    db = SessionLocal()
    try:
        connection = (
            db.query(UserConnection)
            .filter(
                UserConnection.provider == "ultrahuman",
                UserConnection.status == "active",
            )
            .first()
        )

        if not connection:
            print_failure("No active Ultrahuman connection found for test sync")
            return False

        user_id = connection.user_id
        print_info(f"Running test sync for user: {user_id}")

        factory = ProviderFactory()
        strategy = factory.get_provider("ultrahuman")
        provider_impl = strategy.data_247

        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=2)

        print_info(f"Sync range: {start_time.date()} to {end_time.date()}")

        results = provider_impl.load_and_save_all(db, user_id, start_time=start_time, end_time=end_time)
        db.commit()

        print_success("Test sync completed")
        print_info(f"   Sleep sessions synced: {results.get('sleep_sessions_synced', 0)}")
        print_info(f"   Activity samples synced: {results.get('activity_samples', 0)}")
        print_info(f"   Recovery days synced: {results.get('recovery_days_synced', 0)}")

        return True

    except Exception as e:
        print_failure(f"Test sync failed: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        db.close()


def verify_sleep_records() -> bool:
    """Verify sleep records in database."""
    print_header("6. Sleep Records Verification")

    db = SessionLocal()
    try:
        connections = db.query(UserConnection).filter(UserConnection.provider == "ultrahuman").all()

        if not connections:
            print_warning("No Ultrahuman connections to verify")
            return False

        for conn in connections:
            records = (
                db.query(EventRecord)
                .join(ExternalDeviceMapping)
                .filter(
                    ExternalDeviceMapping.user_id == conn.user_id,
                    EventRecord.category == "sleep",
                )
                .order_by(EventRecord.start_datetime.desc())
                .limit(5)
                .all()
            )

            if not records:
                print_warning(f"No sleep records found for user {conn.user_id}")
                continue

            print_info(f"Found {len(records)} recent sleep record(s) for user {conn.user_id}")

            has_issues = False
            for record in records:
                details = db.query(SleepDetails).filter(SleepDetails.record_id == record.id).first()

                if not details:
                    print_failure(f"Sleep details not found for record {record.id}")
                    has_issues = True
                    continue

                if details.sleep_efficiency_score is None:
                    print_warning(f"Sleep efficiency is NULL for record {record.id}")
                    has_issues = True

                stage_total = (
                    details.sleep_deep_minutes
                    + details.sleep_light_minutes
                    + details.sleep_rem_minutes
                    + details.sleep_awake_minutes
                )

                if stage_total == 0:
                    print_failure(f"All sleep stages are 0 for record {record.id}")
                    has_issues = True
                elif stage_total < 0:
                    print_failure(f"Sleep stages total is negative for record {record.id}")
                    has_issues = True

            if not has_issues:
                print_success("Sleep records verification passed")

        return True

    except Exception as e:
        print_failure(f"Failed to verify sleep records: {e}")
        return False
    finally:
        db.close()


def verify_activity_samples() -> bool:
    """Verify activity samples in database."""
    print_header("7. Activity Samples Verification")

    db = SessionLocal()
    try:
        connections = db.query(UserConnection).filter(UserConnection.provider == "ultrahuman").all()

        if not connections:
            print_warning("No Ultrahuman connections to verify")
            return False

        for conn in connections:
            samples = db.query(DataPointSeries).filter(DataPointSeries.external_device_mapping_id.isnot(None)).all()

            if not samples:
                print_warning(f"No activity samples found for user {conn.user_id}")
                continue

            print_info(f"Found {len(samples)} activity samples")

            type_counts = {}
            for sample in samples:
                type_counts[sample.series_type_definition_id] = type_counts.get(sample.series_type_definition_id, 0) + 1

            print_success("Activity samples by type:")
            for type_id, count in type_counts.items():
                print_info(f"   Type ID {type_id}: {count} samples")

            hr_samples = [s for s in samples if s.series_type_definition_id == 1]
            if hr_samples:
                for sample in hr_samples[:5]:
                    value = float(sample.value)
                    if value < 40 or value > 200:
                        print_failure(f"Abnormal HR value {value} at {sample.recorded_at}")

        return True

    except Exception as e:
        print_failure(f"Failed to verify activity samples: {e}")
        return False
    finally:
        db.close()


def print_summary(results: dict[str, bool]) -> None:
    """Print summary of all checks."""
    print_header("VERIFICATION SUMMARY")

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    print(f"\n  Total checks: {total}")
    print(f"  {Colors.OKGREEN}Passed: {passed}{Colors.ENDC}")
    print(f"  {Colors.FAIL}Failed: {total - passed}{Colors.ENDC}\n")

    for name, result in results.items():
        status = f"{Colors.OKGREEN}PASS{Colors.ENDC}" if result else f"{Colors.FAIL}FAIL{Colors.ENDC}"
        print(f"  {status} - {name}")

    if all(results.values()):
        print(f"\n{Colors.OKGREEN}{Colors.BOLD}All checks passed!{Colors.ENDC}\n")
        sys.exit(0)
    else:
        print(f"\n{Colors.FAIL}{Colors.BOLD}Some checks failed.{Colors.ENDC}\n")
        sys.exit(1)


def main() -> None:
    """Main entry point."""
    print(f"{Colors.OKCYAN}{Colors.BOLD}")
    print("╔════════════════════════════════════════╗")
    print("║   Ultrahuman Integration Verification   ║")
    print("╚════════════════════════════════════════╝")
    print(f"{Colors.ENDC}\n")

    results = {}

    results["Provider Registration"] = check_provider_registered()
    results["OAuth Configuration"] = check_oauth_configuration()
    results["Connected Users"] = check_connected_users()
    results["Database Schema"] = check_database_schema()

    if results["Connected Users"]:
        results["Test Sync"] = run_test_sync()
        results["Sleep Records"] = verify_sleep_records()
        results["Activity Samples"] = verify_activity_samples()

    print_summary(results)


if __name__ == "__main__":
    main()
