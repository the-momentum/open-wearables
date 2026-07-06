#!/usr/bin/env python3
"""Seed activity data: create users with comprehensive health data.

This script is a thin wrapper around the SeedDataService, kept for
backward compatibility with `make seed`. All generation logic lives
in app.services.seed_data.
"""

from app.database import SessionLocal
from app.schemas.utils.seed_data import SeedDataRequest, SeedProfileConfig
from app.services.seed_data import seed_data_service


def seed_activity_data() -> None:
    """Create 2 users with default health data (same as original behavior)."""
    request = SeedDataRequest(
        num_users=2,
        profile=SeedProfileConfig(),
    )
    with SessionLocal() as db:
        summary = seed_data_service.generate(db, request)

    print("✓ Successfully created:")
    print(f"  - {summary['users']} users")
    print(f"  - {summary['connections']} provider connections")
    print(f"  - {summary['workouts']} workouts")
    print(f"  - {summary['sleeps']} sleep records")
    print(f"  - {summary['time_series_samples']} time series samples")


if __name__ == "__main__":
    seed_activity_data()
