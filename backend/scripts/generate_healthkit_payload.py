#!/usr/bin/env python3
"""
CLI script to generate realistic HealthKit test payloads.

Usage:
    python scripts/generate_healthkit_payload.py output.json \
        --start-date 2025-01-01 \
        --end-date 2025-01-31 \
        --workouts 50 \
        --records 1000 \
        --sleep 30

    # With seed for reproducibility:
    python scripts/generate_healthkit_payload.py output.json \
        --start-date 2025-01-01 \
        --end-date 2025-01-31 \
        --workouts 100 \
        --records 5000 \
        --sleep 60 \
        --seed 42
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.tasks.fixtures.healthkit_payloads import generate_realistic_payload


def parse_date(date_str: str) -> datetime:
    """Parse date string (YYYY-MM-DD) to timezone-aware datetime."""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.replace(tzinfo=timezone.utc)
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid date format: {date_str}. Use YYYY-MM-DD")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate realistic HealthKit test payloads",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s output.json --start-date 2025-01-01 --end-date 2025-01-31 --workouts 50 --records 1000 --sleep 30
  %(prog)s large_payload.json -s 2024-01-01 -e 2024-12-31 -w 365 -r 10000 -l 365 --seed 42
        """,
    )

    parser.add_argument(
        "output",
        type=str,
        help="Output JSON file path",
    )
    parser.add_argument(
        "-s",
        "--start-date",
        type=parse_date,
        required=True,
        help="Start date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "-e",
        "--end-date",
        type=parse_date,
        required=True,
        help="End date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "-w",
        "--workouts",
        type=int,
        default=10,
        help="Number of workouts to generate (default: 10)",
    )
    parser.add_argument(
        "-r",
        "--records",
        type=int,
        default=100,
        help="Number of health records to generate (default: 100)",
    )
    parser.add_argument(
        "-l",
        "--sleep",
        type=int,
        default=10,
        help="Number of sleep sessions to generate (default: 10)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducibility (optional)",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output (larger file size)",
    )

    args = parser.parse_args()

    if args.end_date <= args.start_date:
        parser.error("end-date must be after start-date")

    print("Generating payload...")
    print(f"  Date range: {args.start_date.date()} to {args.end_date.date()}")
    print(f"  Workouts: {args.workouts}")
    print(f"  Records: {args.records}")
    print(f"  Sleep sessions: {args.sleep}")
    if args.seed is not None:
        print(f"  Seed: {args.seed}")

    payload = generate_realistic_payload(
        start_date=args.start_date,
        end_date=args.end_date,
        workouts_count=args.workouts,
        records_count=args.records,
        sleep_records_count=args.sleep,
        seed=args.seed,
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    indent = 2 if args.pretty else None
    with open(output_path, "w") as f:
        json.dump(payload, f, indent=indent)

    file_size = output_path.stat().st_size
    if file_size > 1024 * 1024:
        size_str = f"{file_size / (1024 * 1024):.2f} MB"
    elif file_size > 1024:
        size_str = f"{file_size / 1024:.2f} KB"
    else:
        size_str = f"{file_size} bytes"

    print(f"\nGenerated: {output_path} ({size_str})")
    print(f"  Workouts: {len(payload['data']['workouts'])}")
    print(f"  Records: {len(payload['data']['records'])}")
    print(f"  Sleep records: {len(payload['data']['sleep'])}")


if __name__ == "__main__":
    main()
